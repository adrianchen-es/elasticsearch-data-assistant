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
                # Extract queries from the AI response
                queries = self._extract_queries_from_response(ai_response)
                
                if not queries:
                    return {
                        "executed": False,
                        "error": "No valid Elasticsearch queries found in AI response",
                        "error_type": "no_queries_found",
                        "results": []
                    }
                
                # Allow the AI to provide multiple iterations of the query.
                # We'll attempt up to 3 extracted queries (in order) and stop on the first successful execution.
                all_results = []
                max_attempts = min(3, len(queries))
                successful_attempt = None
                for i in range(max_attempts):
                    query_data = queries[i]
                    # Add context for better query optimization and tracing
                    query_data["_context"] = ai_response
                    single_result = await self._execute_single_query(query_data, conversation_id)
                    # Annotate attempt index (1-based) for observability
                    single_result["attempt"] = i + 1
                    all_results.append(single_result)
                    # Log which attempt succeeded
                    if single_result.get("success"):
                        successful_attempt = i + 1
                        try:
                            logger.info(f"QueryExecutor: successful attempt {successful_attempt} for conversation {conversation_id}, index={single_result.get('index')}")
                        except Exception:
                            pass
                        # Set span attribute indicating which attempt succeeded
                        try:
                            span.set_attribute("query_executor.successful_attempt", successful_attempt)
                        except Exception:
                            pass
                        break

                final_result = {
                    "executed": any(r.get("success") for r in all_results),
                    "query_count": len(all_results),
                    "results": all_results,
                    "successful_attempt": successful_attempt
                }
                
                span.set_attributes({
                    "success": final_result["executed"],
                    "query_count": final_result["query_count"]
                })
                
                return final_result
                
            except Exception as e:
                logger.error(f"Error processing AI response: {e}")
                span.set_attributes({
                    "success": False,
                    "error": str(e)
                })
                return {
                    "executed": False,
                    "error": f"Failed to process AI response: {str(e)}",
                    "error_type": type(e).__name__,
                    "results": []
                }

    def _extract_queries_from_response(self, response: str) -> List[Dict[str, Any]]:
        """Extract execute_elasticsearch_query function calls from AI response"""
        return self._extract_query_calls(response)

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
                
                # Apply safety limits and detect query type
                safe_query = self._apply_safety_limits(query_data)
                
                # Execute the query
                index = safe_query["index"]
                query_body = safe_query["query"]
                use_count_api = safe_query.get("_use_count_api", False)
                
                logger.info(f"Executing {'count' if use_count_api else 'search'} query on index '{index}' (execution_id: {execution_id})")
                
                # Choose the appropriate Elasticsearch API
                if use_count_api:
                    # Use count API for better performance
                    count_body = {}
                    if "query" in query_body and query_body["query"]:
                        count_body["query"] = query_body["query"]
                    elif any(key in query_body for key in ["match_all", "match", "term", "range", "bool"]):
                        # The query_body is actually the query part
                        count_body["query"] = query_body
                    
                    result = await self.es_service.count(
                        index=index,
                        body=count_body if count_body else None
                    )
                    
                    # Transform count result to look like search result for consistency
                    result = {
                        "hits": {
                            "total": {"value": result.get("count", 0), "relation": "eq"},
                            "hits": []
                        },
                        "took": result.get("took", 0),
                        "_shards": result.get("_shards", {}),
                        "timed_out": result.get("timed_out", False)
                    }
                else:
                    # Use search API
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
        # Allow count-only requests that omit a top-level `query` object
        # e.g., { "index": "my-index", "size": 0 } should be treated as a count request
        # Also allow shorthand top-level query forms like {"match_all": {}} or {"term": {...}}
        query_keys = ["match_all", "match", "term", "range", "bool"]
        if "query" not in query_data:
            # If size==0 (explicit count request) allow it
            if "size" in query_data and query_data.get("size") == 0:
                return
            # If any well-known query key is present at top-level, allow it
            if any(k in query_data for k in query_keys):
                return
            # Otherwise it's invalid
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
        """Apply safety limits to query and fix query structure"""
        safe_query = query_data.copy()
        
        # Extract the query body - fix nested query structure
        if "query" in safe_query and isinstance(safe_query["query"], dict):
            query_body = safe_query["query"].copy()
        else:
            # If no explicit 'query' key, but common query keys exist at top-level, extract them
            query_keys = ["match_all", "match", "term", "range", "bool"]
            found = {k: safe_query[k] for k in query_keys if k in safe_query}
            if found:
                query_body = found
            else:
                # If no query specified, default to match_all
                query_body = {"match_all": {}}
        
        # Check if this is a count-only request
        is_count_request = self._is_count_request(query_data)
        
        # For count requests, prefer the count API
        if is_count_request:
            safe_query["_use_count_api"] = True
            # Remove size parameter for count API
            if "size" in query_body:
                del query_body["size"]
        else:
            # Ensure size limit for search requests
            if "size" not in query_body:
                query_body["size"] = min(100, self.max_size)  # Default to 100 docs
            else:
                query_body["size"] = min(int(query_body.get("size", self.max_size)), self.max_size)
        
        # Add timeout if not present
        if "timeout" not in query_body:
            query_body["timeout"] = self.timeout
        
        safe_query["query"] = query_body
        return safe_query
    
    def _is_count_request(self, query_data: Dict[str, Any]) -> bool:
        """Determine if the request is for a count total"""
        # Check for size 0 in the query
        if query_data.get("size") == 0:
            return True
        
        # Check for size 0 in the nested query body
        if isinstance(query_data.get("query"), dict) and query_data["query"].get("size") == 0:
            return True
            
        # Check for keywords in the context
        return self._is_count_question(query_data.get("_context", ""))
    
    def _is_count_question(self, context: str) -> bool:
        """Determine if the user is asking for a count/total"""
        count_keywords = [
            "how many", "count", "total", "number of", 
            "records are", "documents are", "entries are",
            "available", "exist", "present"
        ]
        return any(keyword in context.lower() for keyword in count_keywords)
    
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
