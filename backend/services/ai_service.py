# backend/services/ai_service.py
from typing import Dict, Any, Optional, Tuple, Generator, Iterable, List
from openai import AsyncAzureOpenAI, AsyncOpenAI
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
    # Add/adjust return_debug in your methods
import json, logging, math, os

try:
    import tiktoken  # robust token counting when available
except Exception:
    tiktoken = None


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class TokenLimitError(Exception):
    def __init__(self, message: str, *, model: str, limit: int, prompt_tokens: int, reserved_for_output: int):
        super().__init__(message)
        self.model = model
        self.limit = limit
        self.prompt_tokens = prompt_tokens
        self.reserved_for_output = reserved_for_output

    def to_dict(self) -> Dict:
        return {
            "error": {
                "code": "token_limit_exceeded",
                "message": str(self),
                "details": {
                    "model": self.model,
                    "context_window": self.limit,
                    "prompt_tokens": self.prompt_tokens,
                    "reserved_for_output": self.reserved_for_output,
                    "available_for_prompt": max(self.limit - self.reserved_for_output, 0),
                },
            }
        }


# Reasonable defaults. Adjust if your deployment uses different model names.
MAX_CONTEXT_TOKENS = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 4_096,
    # fallback key for unknown models
    "__default__": 128_000,
}

# Keep some space for the model to respond
RESERVED_COMPLETION_TOKENS = 2_048


def _get_context_window(model: Optional[str]) -> int:
    if not model:
        return MAX_CONTEXT_TOKENS["__default__"]
    return MAX_CONTEXT_TOKENS.get(model, MAX_CONTEXT_TOKENS["__default__"])


def _approx_token_count_from_text(text: str) -> int:
    # Simple heuristic: ~4 chars per token in English
    return max(1, math.ceil(len(text) / 4))


def _count_tokens_with_tiktoken(messages: List[Dict], model: Optional[str]) -> int:
    # Use message-aware counting if possible
    if tiktoken is None:
        # Fallback: concatenate visible text
        joined = "\n".join(
            f"{m.get('role','user')}: {m.get('content','') if isinstance(m.get('content'), str) else json.dumps(m.get('content'))}"
            for m in messages
        )
        return _approx_token_count_from_text(joined)

    # Choose encoding by model if known; else pick a common base
    try:
        enc = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")

    # Approximate message token format (role + content)
    # This is close enough for pre-checks; exact tokenization depends on model rules.
    tokens = 0
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            # If your app uses structured content (images, tool calls), refine this as needed
            try:
                content = " ".join(
                    part.get("text", "") if isinstance(part, dict) else str(part) for part in content
                )
            except Exception:
                content = json.dumps(content)
        tokens += len(enc.encode(role)) + len(enc.encode(str(content))) + 4  # +4 overhead per message (rough)
    return tokens


def count_prompt_tokens(messages: List[Dict], model: Optional[str]) -> int:
    return _count_tokens_with_tiktoken(messages, model)


def ensure_token_budget(messages: List[Dict], model: Optional[str]) -> Tuple[int, int, int]:
    prompt_tokens = count_prompt_tokens(messages, model)
    limit = _get_context_window(model)
    if prompt_tokens > (limit - RESERVED_COMPLETION_TOKENS):
        raise TokenLimitError(
            f"Your message is too long for the selected model. Limit {limit} tokens, "
            f"received {prompt_tokens}. Try shortening your input.",
            model=model or "unknown",
            limit=limit,
            prompt_tokens=prompt_tokens,
            reserved_for_output=RESERVED_COMPLETION_TOKENS,
        )
    return prompt_tokens, RESERVED_COMPLETION_TOKENS, limit


def _chunk_text(text: str, chunk_size: int = 500) -> Iterable[str]:
    # Simple chunker to simulate streaming when provider doesn't support it
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


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

    def generate_chat(
        self,
        messages: List[Dict],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        stream: bool = False,
    ):
        """
        Returns either a dict {text, usage} when stream=False, or a generator of NDJSON-ready dicts when stream=True.
        """
        # Token guard
        prompt_tokens, reserved_for_output, _limit = ensure_token_budget(messages, model)

        # Prefer using underlying client's streaming if available, otherwise simulate.
        if stream:
            # Try native streaming on the underlying client if it exists in your original implementation.
            try:
                # stream_resp = self.client.chat.completions.create(
                #     model=model,
                #     messages=messages,
                #     temperature=temperature,
                #     stream=True,
                # )
                # for event in stream_resp:
                #     delta = event.choices[0].delta.content or ""
                #     if delta:
                #         yield {"type": "message", "delta": delta}
                # usage after stream end is often provided separately, fall back to None if unknown
                # yield {"type": "final", "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": None, "total_tokens": None}}
                raise NotImplementedError  # remove if you wire native streaming
            except NotImplementedError:
                # Fallback: get full response and chunk it
                # resp = self.client.chat.completions.create(
                #     model=model,
                #     messages=messages,
                #     temperature=temperature,
                # )
                # full_text = resp.choices[0].message.content or ""
                full_text = ""  # replace with actual text from your existing code
                completion_tokens = count_prompt_tokens([{"role": "assistant", "content": full_text}], model)
                for delta in _chunk_text(full_text):
                    yield {"type": "message", "delta": delta}
                yield {
                    "type": "final",
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                    },
                }
        else:
            # resp = self.client.chat.completions.create(
            #     model=model,
            #     messages=messages,
            #     temperature=temperature,
            # )
            # text = resp.choices[0].message.content or ""
            text = ""  # replace with actual text from your existing code
            completion_tokens = count_prompt_tokens([{"role": "assistant", "content": text}], model)
            return {
                "text": text,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            }