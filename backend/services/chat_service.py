# backend/services/chat_service.py
from typing import Dict, Any, Optional, List, AsyncGenerator
import json
import logging
from opentelemetry import trace

from services.ai_service import AIService
from services.query_executor import QueryExecutor

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class ChatService:
    """Service for handling chat interactions, coordinating AI and query execution."""

    def __init__(self, ai_service: AIService, query_executor: QueryExecutor):
        self.ai_service = ai_service
        self.query_executor = query_executor

    async def stream_chat_response(
        self,
        messages: List[Dict[str, Any]],
        mode: str,
        schema_context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generates a streaming chat response, handling different modes.
        """
        with tracer.start_as_current_span("chat_service.stream_chat_response") as span:
            span.set_attributes({
                "chat.mode": mode,
                "chat.conversation_id": conversation_id or "unknown",
            })

            system_prompt = self._build_system_prompt(mode, schema_context)
            enhanced_messages = [{"role": "system", "content": system_prompt}] + messages

            response_stream = await self.ai_service.generate_chat(
                enhanced_messages,
                model=model,
                temperature=temperature,
                stream=True,
                conversation_id=conversation_id,
            )

            async for event in self._handle_response_stream(response_stream, enhanced_messages, model, temperature, conversation_id):
                yield event

    def _build_system_prompt(self, mode: str, schema_context: Optional[Dict[str, Any]]) -> str:
        if mode == "elasticsearch":
            return self._build_elasticsearch_chat_system_prompt(schema_context)
        return "You are a helpful AI assistant. Provide clear, accurate, and helpful responses."

    async def _handle_response_stream(
        self,
        response_stream: AsyncGenerator[Dict[str, Any], None],
        messages: List[Dict[str, Any]],
        model: Optional[str],
        temperature: float,
        conversation_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Handles the AI response stream, including query execution."""
        initial_response_text = ""
        async for event in response_stream:
            if event['type'] == 'content':
                initial_response_text += event['delta']
            yield event
            if event['type'] == 'done':
                break

        if self.query_executor and "execute_elasticsearch_query" in initial_response_text:
            logger.info("Query execution detected in AI response.")
            execution_result = await self.query_executor.execute_query_from_ai_response(
                initial_response_text, conversation_id
            )

            if execution_result.get("executed"):
                query_results_message = self._format_query_results_for_ai(execution_result)
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
                error_message = f"I tried to execute a query, but it failed with the following error: {execution_result.get('error', 'Unknown error')}. Please check the query and try again."
                yield {"type": "content", "delta": error_message}
                yield {"type": "done"}

    def _build_elasticsearch_chat_system_prompt(self, schema_context: Dict[str, Any]) -> str:
        """Builds the system prompt for Elasticsearch-enabled chat."""
        prompt = """You are an AI assistant with access to Elasticsearch data. You can help users understand their data, generate queries, and analyze results.

When you need to execute an Elasticsearch query, use the `execute_elasticsearch_query` function like this:
```
execute_elasticsearch_query({
  "index": "index_name",
  "query": { ... }
})
```

**IMPORTANT QUERY GUIDELINES:**
1. For counting documents, use `"size": 0`.
2. Ensure the query structure is valid JSON. Do not nest "query" inside "query".
3. Use efficient query types like `match_all`, `bool`, `match`, etc.

The function will be executed by the backend, and you will receive the results to analyze. NEVER say you don't have access to Elasticsearch.
"""
        if schema_context:
            prompt += "\nAvailable Elasticsearch indices and their schemas:\n\n"
            for index_name, schema in schema_context.items():
                prompt += f"Index: {index_name}\n"
                if isinstance(schema, dict) and "properties" in schema:
                    prompt += f"Fields: {', '.join(schema['properties'].keys())}\n\n"
                else:
                    prompt += f"Schema: {json.dumps(schema, indent=2)}\n\n"
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
