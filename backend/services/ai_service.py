# backend/services/ai_service.py
from typing import Dict, Any, Optional, Tuple
from openai import AsyncAzureOpenAI, AsyncOpenAI
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
    # Add/adjust return_debug in your methods
import json, logging, os

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class AIService:
    def __init__(self,
                 azure_api_key: Optional[str] = None,
                 azure_endpoint: Optional[str] = None,
                 azure_deployment: Optional[str] = None,
                 azure_version: Optional[str] = None,
                 openai_api_key: Optional[str] = None,
                 openai_model: Optional[str] = None
    ):
        self.azure_api_key = azure_api_key or os.getenv('AZURE_OPENAI_API_KEY')
        self.azure_endpoint = azure_endpoint or os.getenv('AZURE_OPENAI_ENDPOINT')
        self.azure_deployment = azure_deployment or os.getenv('AZURE_OPENAI_DEPLOYMENT')
        self.azure_version = azure_version or os.getenv('AZURE_OPENAI_API_VERSION', '2024-05-01-preview')
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        self.openai_model = openai_model or os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

        self.azure_client = None
        if self.azure_api_key and self.azure_endpoint and self.azure_deployment:
            self.azure_client = AsyncAzureOpenAI(api_key=self.azure_api_key, azure_endpoint=self.azure_endpoint, api_version=self.azure_version)

        self.openai_client = None
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)

    @tracer.start_as_current_span("ai_generate_query", kind=SpanKind.CLIENT)
    async def generate_elasticsearch_query(self, user_prompt: str, mapping_info: Dict[str, Any], provider: str = "azure") -> Dict[str, Any]:
        current_span = trace.get_current_span()
        current_span.set_attributes({
            "ai.provider": provider,
            "ai.model": (self.azure_deployment if provider == "azure" else self.openai_model),
            "ai.prompt.length": len(user_prompt),
            "ai.mapping.indices": str(list(mapping_info.keys()))
        })
        system_prompt = self._build_system_prompt(mapping_info)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate an Elasticsearch query for: {user_prompt}"}
        ]
        try:
            if provider == "azure" and self.azure_client:
                response = await self.azure_client.chat.completions.create(model=self.azure_deployment, messages=messages, temperature=0.1)
            elif provider == "openai" and self.openai_client:
                response = await self.openai_client.chat.completions.create(model=self.openai_model, messages=messages, temperature=0.1)
            else:
                raise ValueError(f"AI provider {provider} not available")
            query_text = response.choices[0].message.content
            if not query_text:
                raise ValueError("query_text is empty")
            current_span.set_attribute("ai.response.length", len(query_text))
            return json.loads(query_text)
        except Exception as e:
            current_span.set_status(Status(StatusCode.ERROR))
            current_span.record_exception(e)
            logger.exception("Error generating query")
            query_json = json.loads(query_text) if query_text else None
            dbg = { 'messages': messages, 'raw': response.model_dump() if hasattr(response, 'model_dump') else response } if return_debug else {}
            return query_json, dbg
            #raise

    @tracer.start_as_current_span("ai_summarize_results")
    async def summarize_results(self, query_results: Dict[str, Any], original_prompt: str, provider: str = "azure") -> str:
        system_prompt = (
            "You are an expert at summarizing Elasticsearch query results.\n"
            "Provide a clear, concise summary of the key findings from the search results.\n"
            "If there are no results, explain that clearly."
        )
        user_content = f"""
        Original question: {original_prompt}

        Query results:
        {query_results}

        Please summarize these results in a helpful way.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        try:
            if provider == "azure" and self.azure_client:
                response = await self.azure_client.chat.completions.create(model=self.azure_deployment, messages=messages, temperature=0.3)
            elif provider == "openai" and self.openai_client:
                response = await self.openai_client.chat.completions.create(model=self.openai_model, messages=messages, temperature=0.3)
            else:
                raise ValueError(f"AI provider {provider} not available")
            return response.choices[0].message.content
        except Exception:
            logger.exception("Error summarizing results")
            dbg = { 'messages': messages, 'raw': response.model_dump() if hasattr(response, 'model_dump') else response } if return_debug else {}
            return dbg
            #raise

    def _build_system_prompt(self, mapping_info: Dict[str, Any]) -> str:
        return (
            "You are an expert Elasticsearch query generator.\n"
            "Generate valid Elasticsearch queries based on user requests.\n\n"
            f"Available index mappings:\n{mapping_info}\n\n"
            "Guidelines:\n"
            "- Return only valid JSON query syntax\n"
            "- Use appropriate field names from the mapping\n"
            "- Consider field types when building queries\n"
            "- Use relevant aggregations when summarizing data is needed\n"
            "- Default to returning top 10 results unless specified\n"
            "- Use appropriate query types (match, term, range, etc.)\n\n"
            "Return only the JSON query, no additional text or formatting."
        )

    @tracer.start_as_current_span("ai_free_chat", kind=SpanKind.CLIENT)
    async def free_chat(self, user_prompt: str, provider: str = "azure", return_debug: bool = False, 
                       context_info: Optional[Dict[str, Any]] = None, 
                       conversation_id: Optional[str] = None) -> Tuple[str, dict]:
        """
        Free chat mode that doesn't require Elasticsearch context
        """
        current_span = trace.get_current_span()
        current_span.set_attributes({
            "ai.provider": provider,
            "ai.model": (self.azure_deployment if provider == "azure" else self.openai_model),
            "ai.prompt.length": len(user_prompt),
            "ai.mode": "free_chat",
            "ai.conversation_id": conversation_id or "unknown"
        })
        
        # Build system prompt for free chat
        system_prompt = "You are a helpful AI assistant. Provide clear, accurate, and helpful responses."
        
        # Add context information if available
        if context_info:
            system_prompt += f"\n\nAvailable context: {json.dumps(context_info, indent=2)}"
            system_prompt += "\nNote: You can reference this context in your responses if relevant, but don't automatically query or analyze the data unless specifically asked."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            if provider == "azure" and self.azure_client:
                response = await self.azure_client.chat.completions.create(
                    model=self.azure_deployment, 
                    messages=messages, 
                    temperature=0.7,  # Slightly higher temperature for more creative responses
                    max_tokens=2000
                )
            elif provider == "openai" and self.openai_client:
                response = await self.openai_client.chat.completions.create(
                    model=self.openai_model, 
                    messages=messages, 
                    temperature=0.7,
                    max_tokens=2000
                )
            else:
                raise ValueError(f"AI provider {provider} not available or not configured")
            
            text = response.choices[0].message.content
            if not text:
                raise ValueError("Empty response from AI provider")
                
            current_span.set_attribute("ai.response.length", len(text))
            current_span.set_status(Status(StatusCode.OK))
            
            # Debug information
            debug_info = {}
            if return_debug:
                debug_info = {
                    'messages': messages,
                    'provider': provider,
                    'model': self.azure_deployment if provider == "azure" else self.openai_model,
                    'temperature': 0.7,
                    'context_provided': context_info is not None,
                    'conversation_id': conversation_id,
                    'raw_response': response.model_dump() if hasattr(response, 'model_dump') else {
                        'choices': [{
                            'message': {'content': text},
                            'finish_reason': response.choices[0].finish_reason if response.choices else 'unknown'
                        }],
                        'usage': getattr(response, 'usage', {})
                    }
                }
            
            return text, debug_info
            
        except Exception as e:
            current_span.set_status(Status(StatusCode.ERROR))
            current_span.record_exception(e)
            logger.error(f"Error in free chat: {e}")
            
            # Return error information
            error_response = f"I apologize, but I encountered an error while processing your request: {str(e)}"
            debug_info = {
                'error': str(e),
                'messages': messages,
                'provider': provider
            } if return_debug else {}
            
            return error_response, debug_info