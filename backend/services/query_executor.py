# backend/services/query_executor.py
from typing import Dict, Any, Optional, List
import json
import re
import logging
from datetime import datetime
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from services.elasticsearch_service import ElasticsearchService
from services.security_service import SecurityService

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class QueryExecutionError(Exception):
    """Custom exception for query execution errors"""
    def __init__(self, message: str, query: Dict[str, Any] = None, error_type: str = "execution_error"):
        super().__init__(message)
        self.query = query
        self.error_type = error_type

class QueryExecutor:
    """Service for safely executing Elasticsearch queries from AI responses"""
    
    def __init__(self, elasticsearch_service: ElasticsearchService, security_service: SecurityService):
        self.es_service = elasticsearch_service
        self.security_service = security_service
        self.execution_history: List[Dict] = []
        
        # Query safety patterns - block potentially dangerous operations
        self.blocked_operations = [
            r'_delete_by_query',
            r'_update_by_query',
            r'DELETE\s+/',
            r'PUT\s+/',
            r'POST\s+.*/_delete',
            r'_reindex',
            r'_clone',
            r'_split',
            r'_shrink'
        ]
        
        # Resource limits
        self.max_size = 1000  # Maximum documents to return
        self.timeout = "30s"  # Query timeout
        
    async def execute_query_from_ai_response(self, ai_response: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Extract and execute Elasticsearch queries from AI response"""
        with tracer.start_as_current_span("query_executor_execute") as span:
            span.set_attributes({
                "conversation_id": conversation_id or "unknown",
                "response_length": len(ai_response)
            })
            
            try:
                # Extract query function calls from AI response
                queries = self._extract_query_calls(ai_response)
                
                if not queries:
                    return {
                        "executed": False,
                        "message": "No query execution requests found in response",
                        "original_response": ai_response
                    }
                
                results = []
                for query_data in queries:
                    result = await self._execute_single_query(query_data, conversation_id)
                    results.append(result)
                
                span.set_attributes({
                    "queries_executed": len(results),
                    "success": all(r.get("success", False) for r in results)
                })
                
                return {
                    "executed": True,
                    "query_count": len(results),
                    "results": results,
                    "original_response": ai_response,
                    "conversation_id": conversation_id
                }
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR)
                logger.error(f"Query execution failed: {e}")
                
                return {
                    "executed": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "original_response": ai_response
                }
    
    def _extract_query_calls(self, response: str) -> List[Dict[str, Any]]:
        """Extract execute_elasticsearch_query function calls from AI response"""
        # Pattern to match execute_elasticsearch_query function calls
        # Use a more flexible approach to handle nested JSON structures
        pattern = r'execute_elasticsearch_query\s*\(\s*(\{.*?\})\s*\)'
        
        queries = []
        
        # Find all potential matches
        for match in re.finditer(pattern, response, re.DOTALL | re.IGNORECASE):
            try:
                query_str = match.group(1)
                
                # Try to parse the JSON, handling nested braces
                # Use a simple brace counter to find the complete JSON object
                json_content = self._extract_complete_json(response, match.start(1))
                
                if json_content:
                    query_data = json.loads(json_content)
                    queries.append(query_data)
                    logger.debug(f"Successfully extracted query: {query_data}")
                else:
                    # Fallback to the original match
                    query_str = self._clean_query_string(query_str)
                    query_data = json.loads(query_str)
                    queries.append(query_data)
                    logger.debug(f"Extracted query using fallback: {query_data}")
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse query JSON: {e}, content: {match.group(1)[:100]}...")
                continue
        
        logger.info(f"Extracted {len(queries)} queries from AI response")
        return queries
    
    def _extract_complete_json(self, text: str, start_pos: int) -> Optional[str]:
        """Extract a complete JSON object starting from the given position"""
        if start_pos >= len(text) or text[start_pos] != '{':
            return None
        
        brace_count = 0
        i = start_pos
        
        while i < len(text):
            char = text[i]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found the end of the JSON object
                    return text[start_pos:i+1]
            i += 1
        
        return None
    
    def _clean_query_string(self, query_str: str) -> str:
        """Clean and normalize query string for JSON parsing"""
        # Remove comments
        query_str = re.sub(r'//.*$', '', query_str, flags=re.MULTILINE)
        
        # Fix common JSON issues
        query_str = query_str.strip()
        if not query_str.startswith('{'):
            query_str = '{' + query_str
        if not query_str.endswith('}'):
            query_str = query_str + '}'
        
        return query_str
    
    async def _execute_single_query(self, query_data: Dict[str, Any], conversation_id: Optional[str]) -> Dict[str, Any]:
        """Execute a single Elasticsearch query with safety checks"""
        with tracer.start_as_current_span("query_executor_single_query") as span:
            execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.execution_history)}"
            
            span.set_attributes({
                "execution_id": execution_id,
                "conversation_id": conversation_id or "unknown",
                "index": query_data.get("index", "unknown")
            })
            
            try:
                # Validate query structure
                self._validate_query_structure(query_data)
                
                # Security checks
                security_result = await self._security_check_query(query_data)
                if not security_result["safe"]:
                    raise QueryExecutionError(
                        f"Query failed security check: {security_result['reason']}",
                        query_data,
                        "security_violation"
                    )
                
                # Apply safety limits
                safe_query = self._apply_safety_limits(query_data)
                
                # Execute the query
                index = safe_query["index"]
                query_body = safe_query["query"]
                
                logger.info(f"Executing query on index '{index}' (execution_id: {execution_id})")
                
                # Use the elasticsearch service to execute the query
                result = await self.es_service.search(
                    index=index,
                    body=query_body,
                    timeout=self.timeout
                )
                
                # Process and sanitize results
                processed_result = self._process_query_result(result)
                
                # Record execution history
                execution_record = {
                    "execution_id": execution_id,
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id,
                    "index": index,
                    "query": query_body,
                    "success": True,
                    "result_count": processed_result.get("hits", {}).get("total", {}).get("value", 0),
                    "execution_time_ms": processed_result.get("took", 0)
                }
                self.execution_history.append(execution_record)
                
                span.set_attributes({
                    "success": True,
                    "result_count": execution_record["result_count"],
                    "execution_time_ms": execution_record["execution_time_ms"]
                })
                
                return {
                    "success": True,
                    "execution_id": execution_id,
                    "index": index,
                    "result": processed_result,
                    "metadata": {
                        "execution_time_ms": execution_record["execution_time_ms"],
                        "result_count": execution_record["result_count"],
                        "timestamp": execution_record["timestamp"]
                    }
                }
                
            except Exception as e:
                # Record failed execution
                execution_record = {
                    "execution_id": execution_id,
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id,
                    "index": query_data.get("index", "unknown"),
                    "query": query_data.get("query", {}),
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                self.execution_history.append(execution_record)
                
                span.record_exception(e)
                span.set_status(StatusCode.ERROR)
                
                return {
                    "success": False,
                    "execution_id": execution_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "query_data": query_data
                }
    
    def _validate_query_structure(self, query_data: Dict[str, Any]) -> None:
        """Validate that query has required structure"""
        if not isinstance(query_data, dict):
            raise QueryExecutionError("Query data must be a dictionary")
        
        if "index" not in query_data:
            raise QueryExecutionError("Query must specify an index")
        
        if "query" not in query_data:
            raise QueryExecutionError("Query must contain a query object")
        
        index = query_data["index"]
        if not isinstance(index, str) or not index.strip():
            raise QueryExecutionError("Index must be a non-empty string")
    
    async def _security_check_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform security checks on the query"""
        query_str = json.dumps(query_data)
        
        # Check for blocked operations
        for pattern in self.blocked_operations:
            if re.search(pattern, query_str, re.IGNORECASE):
                return {
                    "safe": False,
                    "reason": f"Query contains blocked operation pattern: {pattern}"
                }
        
        # Check for potential data exfiltration attempts
        from routers.chat import ChatMessage
        
        fake_message = ChatMessage(role="system", content=query_str)
        security_result = self.security_service.detect_threats([fake_message])
        
        if security_result and security_result.threats_detected:
            high_risk_threats = [
                t for t in security_result.threats_detected 
                if t.threat_level.value in ["critical", "high"]
            ]
            
            if high_risk_threats:
                return {
                    "safe": False,
                    "reason": f"Query contains security threats: {[t.threat_type for t in high_risk_threats]}"
                }
        
        return {"safe": True}
    
    def _apply_safety_limits(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply safety limits to query"""
        safe_query = query_data.copy()
        query_body = safe_query["query"].copy()
        
        # Ensure size limit
        if "size" not in query_body:
            query_body["size"] = min(100, self.max_size)  # Default to 100 docs
        else:
            query_body["size"] = min(query_body["size"], self.max_size)
        
        # Add timeout if not present
        if "timeout" not in query_body:
            query_body["timeout"] = self.timeout
        
        safe_query["query"] = query_body
        return safe_query
    
    def _process_query_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process and sanitize query results"""
        processed = result.copy()
        
        # Remove potentially sensitive metadata
        sensitive_keys = ["_version", "_seq_no", "_primary_term"]
        
        if "hits" in processed and "hits" in processed["hits"]:
            for hit in processed["hits"]["hits"]:
                for key in sensitive_keys:
                    hit.pop(key, None)
                
                # Limit source field size for large documents
                if "_source" in hit and isinstance(hit["_source"], dict):
                    source_str = json.dumps(hit["_source"])
                    if len(source_str) > 10000:  # 10KB limit per document
                        hit["_source"] = {
                            "_truncated": True,
                            "_original_size": len(source_str),
                            "_message": "Document truncated due to size"
                        }
        
        return processed
    
    def get_execution_history(self, conversation_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get recent query execution history"""
        history = self.execution_history
        
        if conversation_id:
            history = [h for h in history if h.get("conversation_id") == conversation_id]
        
        return history[-limit:] if limit else history
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        total_executions = len(self.execution_history)
        successful_executions = len([h for h in self.execution_history if h.get("success", False)])
        
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": successful_executions / total_executions if total_executions > 0 else 0,
            "recent_executions": self.execution_history[-10:] if self.execution_history else []
        }
