# backend/services/chat_service.py
from typing import Dict, Any, Optional, List, AsyncGenerator
import os
import json
import logging
from opentelemetry import trace

from services.ai_service import AIService
from services.query_executor import QueryExecutor
from services.intelligent_mode_service import IntelligentModeDetector, ModeDetectionResult
from services.ai_tools import get_elasticsearch_tools, parse_function_arguments, validate_elasticsearch_query

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class ChatService:
    """Service for handling chat interactions, coordinating AI and query execution."""

    def __init__(self, ai_service: AIService, query_executor: QueryExecutor, intelligent_mode_detector: Optional[IntelligentModeDetector] = None):
        self.ai_service = ai_service
        self.query_executor = query_executor
        self.intelligent_mode_detector = intelligent_mode_detector

    async def stream_chat_response(
        self,
        messages: List[Dict[str, Any]],
        mode: str,
        index_name: Optional[str] = None,
        schema_context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        conversation_id: Optional[str] = None,
        debug: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generates a streaming chat response, handling different modes with intelligent detection.
        """
        with tracer.start_as_current_span("chat_service.stream_chat_response") as span:
            span.set_attributes({
                "chat.mode": mode,
                "chat.conversation_id": conversation_id or "unknown",
                "chat.index_name": index_name or "none",
            })

            # Handle intelligent mode detection for "auto" mode
            actual_mode = mode
            detection_result = None
            
            if mode == "auto" and self.intelligent_mode_detector:
                try:
                    detection_result = await self.intelligent_mode_detector.detect_mode(
                        messages, index_name
                    )
                    actual_mode = detection_result.suggested_mode
                    
                    span.set_attributes({
                        "chat.detected_mode": actual_mode,
                        "chat.detection_confidence": detection_result.confidence,
                        "chat.query_intent": detection_result.intent.value,
                        "chat.relevant_indices_count": len(detection_result.relevant_indices)
                    })
                    
                    # Send mode detection info to client
                    yield {
                        "type": "mode_detected",
                        "mode": actual_mode,
                        "confidence": detection_result.confidence,
                        "intent": detection_result.intent.value,
                        "reasoning": detection_result.reasoning,
                        "relevant_indices": detection_result.relevant_indices
                    }
                    
                    logger.info(f"Intelligent mode detection: {actual_mode} (confidence: {detection_result.confidence:.2f})")
                    
                except Exception as e:
                    logger.warning(f"Mode detection failed, falling back to free mode: {e}")
                    actual_mode = "free"
                    yield {
                        "type": "mode_detected",
                        "mode": "free",
                        "confidence": 0.5,
                        "intent": "general_conversation",
                        "reasoning": f"Mode detection failed: {str(e)}",
                        "relevant_indices": []
                    }

            # If we detected elasticsearch mode but have no suitable index, provide context
            if actual_mode == "elasticsearch" and detection_result:
                if detection_result.relevant_indices and not index_name:
                    # Suggest the best index from detection
                    suggested_index = detection_result.relevant_indices[0]
                    yield {
                        "type": "index_suggestion",
                        "suggested_index": suggested_index,
                        "available_indices": detection_result.relevant_indices[:5]
                    }
                    # Use the suggested index for this conversation
                    index_name = suggested_index

            # Build enhanced schema context for elasticsearch mode
            enhanced_schema_context = schema_context
            if actual_mode == "elasticsearch" and detection_result and detection_result.relevant_indices:
                enhanced_schema_context = await self._build_enhanced_schema_context(
                    detection_result.relevant_indices, index_name
                )

            system_prompt = self._build_system_prompt(actual_mode, enhanced_schema_context, detection_result)
            enhanced_messages = [{"role": "system", "content": system_prompt}] + messages

            # Development helper: optionally simulate an AI-generated
            # `execute_elasticsearch_query` call for local testing. This is
            # gated by the environment variable `ENABLE_SIMULATED_EXECUTE` to
            # avoid accidentally shipping a special token in production.
            simulate = False
            try:
                enabled = os.getenv('ENABLE_SIMULATED_EXECUTE', 'false').lower() in ('1', 'true', 'yes')
                if enabled:
                    for m in messages:
                        if isinstance(m, dict) and '__SIMULATE_EXECUTE_QUERY__' in str(m.get('content', '')):
                            simulate = True
                            break
            except Exception:
                simulate = False

            if simulate:
                async def _simulated_response():
                    # Craft a simple execute_elasticsearch_query payload
                    index_to_use = messages[0].get('meta', {}).get('index_name') if messages else None
                    index_to_use = index_name or index_to_use or 'test-index'
                    payload = (
                        'execute_elasticsearch_query({"index": "' + index_to_use + '", "query": {"match_all": {}}, "size": 0})'
                    )
                    # stream a content chunk that contains the function call
                    yield {"type": "content", "delta": payload}

                    # Simulate a successful query execution: construct fake results
                    fake_results = [
                        {
                            "success": True,
                            "attempt": 1,
                            "result": {
                                "hits": {
                                    "total": {"value": 42},
                                    "hits": [
                                        {"_id": "1", "_source": {"message": "sample"}}
                                    ]
                                }
                            }
                        }
                    ]

                    # Add telemetry event to current span indicating results will be sent
                    try:
                        current_span = trace.get_current_span()
                        if current_span is not None:
                            current_span.add_event("query_results_sent", {"executed": True, "query_count": 1, "successful_attempt": 1})
                    except Exception:
                        logger.debug("Failed to add telemetry event for simulated query_results_sent")

                    yield {
                        "type": "query_results",
                        "message": "Query execution completed. 42 documents matched. Sample: [{\"_id\": \"1\", \"_source\": {\"message\": \"sample\"}}]",
                        "results": fake_results,
                        "query_count": 1,
                        "query_execution_metadata": {"successful_attempt": 1}
                    }

                    # finally done
                    yield {"type": "done"}

                response_stream = _simulated_response()
            else:
                # Get tools for function calling in elasticsearch mode
                tools = None
                if actual_mode == "elasticsearch":
                    tools = get_elasticsearch_tools()
                
                response_stream = await self.ai_service.generate_chat(
                    enhanced_messages,
                    model=model,
                    temperature=temperature,
                    stream=True,
                    conversation_id=conversation_id,
                    tools=tools,
                )

            async for event in self._handle_response_stream(response_stream, enhanced_messages, model, temperature, conversation_id, debug):
                yield event

    def _build_system_prompt(self, mode: str, schema_context: Optional[Dict[str, Any]], detection_result: Optional[ModeDetectionResult] = None) -> str:
        if mode == "elasticsearch":
            return self._build_elasticsearch_chat_system_prompt(schema_context, detection_result)
        return "You are a helpful AI assistant. Provide clear, accurate, and helpful responses."

    async def _handle_response_stream(
        self,
        response_stream: AsyncGenerator[Dict[str, Any], None],
        messages: List[Dict[str, Any]],
        model: Optional[str],
        temperature: float,
        conversation_id: Optional[str],
        debug: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Handles the AI response stream, including query execution via function calls or text parsing."""
        initial_response_text = ""
        function_calls = []
        
        async for event in response_stream:
            if event['type'] == 'content':
                initial_response_text += event['delta']
                yield event
            elif event['type'] == 'tool_call':
                # Handle function call during streaming
                function_calls.append(event['tool_call'])
                logger.info(f"Function call detected: {event['tool_call']['function']['name']}")
                
                # Execute the function call immediately
                if event['tool_call']['function']['name'] == 'execute_elasticsearch_query':
                    try:
                        # Parse and validate function arguments
                        args_str = event['tool_call']['function']['arguments']
                        query_args = parse_function_arguments(args_str)
                        query_args = validate_elasticsearch_query(query_args)
                        
                        # Execute the query using the query executor directly
                        execution_result = await self.query_executor.execute_elasticsearch_query(
                            **query_args, conversation_id=conversation_id
                        )
                        
                        if execution_result.get("executed"):
                            # Format results for the AI and send to client
                            query_results_message = self._format_query_results_for_ai(execution_result)

                            # Add telemetry event
                            try:
                                current_span = trace.get_current_span()
                                if current_span is not None:
                                    current_span.add_event("query_results_sent", {
                                        "executed": True,
                                        "query_count": execution_result.get("query_count", 0),
                                        "successful_attempt": execution_result.get("successful_attempt"),
                                        "via_function_call": True
                                    })
                            except Exception:
                                logger.debug("Failed to add telemetry event for query_results_sent")

                            # Send structured query results
                            yield {
                                "type": "query_results",
                                "message": query_results_message,
                                "results": execution_result.get("results", []),
                                "query_count": execution_result.get("query_count", 0),
                                "query_execution_metadata": {
                                    "successful_attempt": execution_result.get("successful_attempt"),
                                    "via_function_call": True
                                }
                            }
                        else:
                            # Handle execution error
                            error_message = f"Query execution failed: {execution_result.get('error', 'Unknown error')}"
                            logger.error(error_message)
                            yield {
                                "type": "content", 
                                "delta": f"\n\n{error_message}. Please check the query and try again."
                            }
                            
                    except Exception as e:
                        error_message = f"Function call execution failed: {str(e)}"
                        logger.error(error_message)
                        yield {
                            "type": "content",
                            "delta": f"\n\n{error_message}"
                        }
            else:
                yield event
                
            if event['type'] == 'done':
                break

        # Fallback: check for text-based query execution if no function calls were made
        if not function_calls and self.query_executor and "execute_elasticsearch_query" in initial_response_text:
            logger.info("Query execution detected in AI response text (fallback parsing).")
            execution_result = await self.query_executor.execute_query_from_ai_response(
                initial_response_text, conversation_id
            )

            if execution_result.get("executed"):
                # Format results for the AI and send to client
                query_results_message = self._format_query_results_for_ai(execution_result)

                # Add telemetry event
                try:
                    current_span = trace.get_current_span()
                    if current_span is not None:
                        current_span.add_event("query_results_sent", {
                            "executed": True,
                            "query_count": execution_result.get("query_count", 0),
                            "successful_attempt": execution_result.get("successful_attempt"),
                            "via_function_call": False
                        })
                except Exception:
                    logger.debug("Failed to add telemetry event for query_results_sent")

                # Send structured query results
                yield {
                    "type": "query_results",
                    "message": query_results_message,
                    "results": execution_result.get("results", []),
                    "query_count": execution_result.get("query_count", 0),
                    "query_execution_metadata": {
                        "successful_attempt": execution_result.get("successful_attempt"),
                        "via_function_call": False
                    }
                }

                # Request follow-up analysis from AI if we have results
                if function_calls or initial_response_text.strip():
                    follow_up_messages = messages + [
                        {"role": "assistant", "content": initial_response_text},
                        {"role": "system", "content": query_results_message},
                    ]

                    follow_up_stream = await self.ai_service.generate_chat(
                        follow_up_messages,
                        model=model,
                        temperature=temperature,
                        stream=True,
                        conversation_id=conversation_id,
                    )
                    async for event in follow_up_stream:
                        yield event
            else:
                error_message = f"Query execution failed: {execution_result.get('error', 'Unknown error')}. Please check the query and try again."
                yield {"type": "content", "delta": error_message}
                yield {"type": "done"}

    def _build_elasticsearch_chat_system_prompt(self, schema_context: Optional[Dict[str, Any]], detection_result: Optional[ModeDetectionResult] = None) -> str:
        """Builds the system prompt for Elasticsearch-enabled chat."""
        prompt = """You are an AI assistant with direct access to Elasticsearch data through function calling. You can help users understand their data, generate queries, and analyze results.

When you need to execute an Elasticsearch query, call the `execute_elasticsearch_query` function with proper parameters:

**Function Parameters:**
- `query` (required): The Elasticsearch query DSL object
- `size`: Number of documents to return (default: 10, max: 10000)
- `from`: Starting offset for pagination (default: 0)
- `sort`: Sort order specification (optional)
- `aggs`: Aggregations to perform (optional)
- `_source`: Fields to include/exclude (optional)

**Example function calls:**
- Search documents: `execute_elasticsearch_query({"query": {"match": {"title": "search term"}}, "size": 10})`
- Count documents: `execute_elasticsearch_query({"query": {"match_all": {}}, "size": 0})`
- Aggregation: `execute_elasticsearch_query({"query": {"match_all": {}}, "size": 0, "aggs": {"avg_price": {"avg": {"field": "price"}}}})`

**IMPORTANT GUIDELINES:**
1. Always use proper Elasticsearch query DSL syntax
2. For counting only, set `"size": 0`
3. Use efficient queries like `match_all`, `bool`, `match`, `range`, etc.
4. The system will automatically select the best available index if not specified
5. Function calls are executed directly - no need for text formatting

You will receive the actual query results and can analyze them for the user. NEVER say you don't have access to Elasticsearch - you have direct function calling access.
"""
        
        # Add intelligent context from mode detection
        if detection_result:
            prompt += f"\n**QUERY CONTEXT:**\n"
            prompt += f"- Detected intent: {detection_result.intent.value}\n"
            if detection_result.relevant_indices:
                prompt += f"- Most relevant indices: {', '.join(detection_result.relevant_indices[:3])}\n"
            prompt += f"- Confidence level: {detection_result.confidence:.1%}\n\n"
        
        if schema_context:
            prompt += "\n**AVAILABLE ELASTICSEARCH INDICES AND SCHEMAS:**\n\n"
            for index_name, schema in schema_context.items():
                prompt += f"### Index: {index_name}\n"
                if isinstance(schema, dict) and "properties" in schema:
                    # Show key fields with types for better context
                    properties = schema['properties']
                    field_info = []
                    for field, config in list(properties.items())[:20]:  # Limit to prevent prompt overflow
                        field_type = config.get('type', 'unknown')
                        field_info.append(f"{field} ({field_type})")
                    prompt += f"Key fields: {', '.join(field_info)}\n"
                    if len(properties) > 20:
                        prompt += f"... and {len(properties) - 20} more fields\n"
                else:
                    prompt += f"Schema: {json.dumps(schema, indent=2)}\n"
                prompt += "\n"
        return prompt

    def _format_query_results_for_ai(self, execution_result: Dict[str, Any]) -> str:
        """Formats query execution results for the AI to consume."""
        if not execution_result.get("executed", False):
            return "Query execution failed. Please try a different approach."
        
        results = execution_result.get("results", [])
        if not results:
            return "No query results to process."
        
        formatted_results = []
        for i, result in enumerate(results):
            if result.get("success", False):
                query_result = result.get("result", {})
                hits = query_result.get("hits", {})
                total_hits = hits.get("total", {}).get("value", 0)
                
                formatted_results.append(f"Query {i+1} Results:\n- Total matching documents: {total_hits}\n- Sample documents:\n{json.dumps(hits.get('hits', [])[:3], indent=2)}")
            else:
                formatted_results.append(f"Query {i+1} Error:\n- Error: {result.get('error', 'Unknown error')}")
        
        return f"Query execution completed. Here are the results:\n\n{''.join(formatted_results)}\n\nPlease analyze these results and provide insights to the user."
    
    async def _build_enhanced_schema_context(self, relevant_indices: List[str], current_index: Optional[str]) -> Dict[str, Any]:
        """Build enhanced schema context focusing on relevant indices"""
        schema_context = {}
        
        # Prioritize current index if specified
        indices_to_process = []
        if current_index and current_index in relevant_indices:
            indices_to_process.append(current_index)
        
        # Add other relevant indices
        for index in relevant_indices:
            if index not in indices_to_process:
                indices_to_process.append(index)
        
        # Limit to prevent prompt overflow
        for index_name in indices_to_process[:5]:
            try:
                # This would need to be implemented - getting mapping from the mapping cache
                # For now, we'll leave this as a placeholder
                schema_context[index_name] = {"properties": {}}
            except Exception as e:
                logger.warning(f"Failed to get schema for index {index_name}: {e}")
        
        return schema_context
