# backend/services/ai_service.py
from typing import Dict, Any, Optional, Tuple, Generator, Iterable, List
from openai import AsyncAzureOpenAI, AsyncOpenAI
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
import json, logging, math, os, time

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
        logger.info("⚡ Initializing AIService (fast startup)...")
        
        # Load configuration from parameters or environment
        self.azure_api_key = azure_api_key or os.getenv('AZURE_OPENAI_API_KEY')
        self.azure_endpoint = azure_endpoint or os.getenv('AZURE_OPENAI_ENDPOINT')
        self.azure_deployment = azure_deployment or os.getenv('AZURE_OPENAI_DEPLOYMENT')
        self.azure_version = azure_version or os.getenv('AZURE_OPENAI_API_VERSION', '2024-05-01-preview')
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        self.openai_model = openai_model or os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

        # Initialize client connections (lazy)
        self.azure_client = None
        self.openai_client = None
        
        # Track initialization status for debugging
        self._initialization_status = {
            "azure_configured": False,
            "openai_configured": False,
            "clients_created": False,
            "errors": []
        }
        
        # Quick configuration validation (don't create clients yet)
        self._validate_configuration()
        
        logger.info(f"✅ AIService initialized (providers will be created on first use)")
    
    def _validate_configuration(self):
        """Validate configuration without creating clients"""
        # Check Azure configuration
        if self.azure_api_key and self.azure_endpoint and self.azure_deployment:
            self._initialization_status["azure_configured"] = True
            logger.debug(f"Azure OpenAI configuration valid - Endpoint: {self._mask_sensitive_data(self.azure_endpoint)}, Deployment: {self.azure_deployment}")
        else:
            missing_fields = []
            if not self.azure_api_key:
                missing_fields.append("AZURE_OPENAI_API_KEY")
            if not self.azure_endpoint:
                missing_fields.append("AZURE_OPENAI_ENDPOINT")
            if not self.azure_deployment:
                missing_fields.append("AZURE_OPENAI_DEPLOYMENT")
            
            if missing_fields:
                warning_msg = f"Azure OpenAI not configured - Missing: {', '.join(missing_fields)}"
                self._initialization_status["errors"].append(warning_msg)
                logger.debug(f"⚠️  {warning_msg}")

        # Check OpenAI configuration
        if self.openai_api_key:
            self._initialization_status["openai_configured"] = True
            logger.debug(f"OpenAI configuration valid - Model: {self.openai_model}")
        else:
            warning_msg = "OpenAI not configured - Missing: OPENAI_API_KEY"
            self._initialization_status["errors"].append(warning_msg)
            logger.debug(f"⚠️  {warning_msg}")
        
        # Check if we have at least one provider configured
        if not self._initialization_status["azure_configured"] and not self._initialization_status["openai_configured"]:
            error_msg = "❌ No AI providers configured. Please set up either Azure OpenAI or OpenAI credentials."
            logger.error(error_msg)
            raise ValueError("No AI providers configured. Please set up either Azure OpenAI or OpenAI credentials.")
        else:
            providers = []
            if self._initialization_status["azure_configured"]:
                providers.append("Azure OpenAI")
            if self._initialization_status["openai_configured"]:
                providers.append("OpenAI")
            logger.info(f"🚀 AI providers available: {', '.join(providers)}")
    
    def _ensure_clients_initialized(self):
        """Lazy initialization of clients on first use"""
        if self._initialization_status["clients_created"]:
            logger.debug("🔄 AI clients already initialized, skipping creation")
            return
            
        logger.info("🚀 Creating AI client connections...")
        initialization_start_time = time.time()
        
        azure_success = False
        openai_success = False
        
        # Initialize Azure OpenAI client
        if self._initialization_status["azure_configured"] and not self.azure_client:
            try:
                azure_start_time = time.time()
                logger.info("☁️ Initializing Azure OpenAI client...")
                
                self.azure_client = AsyncAzureOpenAI(
                    api_key=self.azure_api_key, 
                    azure_endpoint=self.azure_endpoint, 
                    api_version=self.azure_version
                )
                
                azure_duration = time.time() - azure_start_time
                azure_success = True
                logger.info(f"✅ Azure OpenAI client created successfully in {azure_duration:.3f}s")
                logger.info(f"   • Endpoint: {self._mask_sensitive_data(self.azure_endpoint)}")
                logger.info(f"   • Deployment: {self.azure_deployment}")
                logger.info(f"   • API Version: {self.azure_version}")
                
            except Exception as e:
                azure_duration = time.time() - azure_start_time if 'azure_start_time' in locals() else 0
                error_msg = f"Failed to create Azure OpenAI client after {azure_duration:.3f}s: {str(e)}"
                self._initialization_status["errors"].append(error_msg)
                logger.error(f"❌ {error_msg}")

        # Initialize OpenAI client  
        if self._initialization_status["openai_configured"] and not self.openai_client:
            try:
                openai_start_time = time.time()
                logger.info("🤖 Initializing OpenAI client...")
                
                self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
                
                openai_duration = time.time() - openai_start_time
                openai_success = True
                logger.info(f"✅ OpenAI client created successfully in {openai_duration:.3f}s")
                logger.info(f"   • Model: {self.openai_model}")
                
            except Exception as e:
                openai_duration = time.time() - openai_start_time if 'openai_start_time' in locals() else 0
                error_msg = f"Failed to create OpenAI client after {openai_duration:.3f}s: {str(e)}"
                self._initialization_status["errors"].append(error_msg)
                logger.error(f"❌ {error_msg}")
        
        self._initialization_status["clients_created"] = True
        
        # Final validation
        if not self.azure_client and not self.openai_client:
            total_duration = time.time() - initialization_start_time
            error_msg = f"❌ Failed to create any AI clients despite valid configuration (after {total_duration:.3f}s)"
            logger.error(error_msg)
            raise ValueError("Failed to initialize AI clients")
        
        # Success summary
        total_duration = time.time() - initialization_start_time
        providers = []
        if self.azure_client:
            providers.append("Azure OpenAI")
        if self.openai_client:
            providers.append("OpenAI")
            
        configured_providers = []
        if self._initialization_status.get('azure_configured', False):
            configured_providers.append('Azure')
        if self._initialization_status.get('openai_configured', False):
            configured_providers.append('OpenAI')
            
        success_count = sum([azure_success, openai_success])
        total_configured = len(configured_providers)
            
        logger.info(f"🎉 AI client initialization completed in {total_duration:.3f}s")
        logger.info(f"🚀 Ready providers: {', '.join(providers)}")
        logger.info(f"📊 Success rate: {success_count}/{total_configured} providers initialized")
    
    def _mask_sensitive_data(self, data: str, show_chars: int = 4) -> str:
        """Mask sensitive data for logging, showing only first few characters"""
        if not data or len(data) <= show_chars:
            return "***"
        return f"{data[:show_chars]}***"
    
    def get_initialization_status(self) -> Dict[str, Any]:
        """Get initialization status for debugging"""
        return {
            "azure_configured": self._initialization_status["azure_configured"],
            "openai_configured": self._initialization_status["openai_configured"],
            "clients_created": self._initialization_status["clients_created"],
            "available_providers": self._get_available_providers(),
            "errors": self._initialization_status["errors"],
            "azure_deployment": self.azure_deployment if self._initialization_status["azure_configured"] else None,
            "openai_model": self.openai_model if self._initialization_status["openai_configured"] else None
        }
    
    def _get_available_providers(self) -> List[str]:
        """Get list of available AI providers"""
        providers = []
        if self._initialization_status["azure_configured"]:
            providers.append("azure")
        if self._initialization_status["openai_configured"]:
            providers.append("openai")
        return providers
    
    def _validate_provider(self, provider: str) -> None:
        """Validate that the requested provider is available"""
        # Ensure clients are initialized before validation
        self._ensure_clients_initialized()
        
        if provider == "azure" and not self.azure_client:
            raise ValueError(
                f"Azure OpenAI provider not available. "
                f"Initialization status: {self._initialization_status}. "
                f"Please check AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT environment variables."
            )
        elif provider == "openai" and not self.openai_client:
            raise ValueError(
                f"OpenAI provider not available. "
                f"Initialization status: {self._initialization_status}. "
                f"Please check OPENAI_API_KEY environment variable."
            )
        elif provider not in ["azure", "openai"]:
            available = self._get_available_providers()
            raise ValueError(f"Invalid provider '{provider}'. Available providers: {available}")
    
    def _get_default_provider(self) -> str:
        """Get the default provider (prefer Azure, fallback to OpenAI)"""
        # Ensure clients are initialized before getting default
        self._ensure_clients_initialized()
        
        if self.azure_client:
            return "azure"
        elif self.openai_client:
            return "openai"
        else:
            raise ValueError("No AI providers available")

    async def generate_elasticsearch_query(self, user_prompt: str, mapping_info: Dict[str, Any], provider: str = "auto", return_debug: bool = False) -> Dict[str, Any]:
        # Auto-select provider if not specified
        if provider == "auto":
            provider = self._get_default_provider()
            
        # Validate provider availability
        self._validate_provider(provider)
        
        with tracer.start_as_current_span(
            "ai_generate_query", kind=SpanKind.CLIENT,
            attributes={
                "ai.provider": provider,
                "ai.model": (self.azure_deployment if provider == "azure" else self.openai_model),
                "ai.prompt.length": len(user_prompt),
                "ai.mapping.indices": str(list(mapping_info.keys()))
            },
        ):
            system_prompt = self._build_system_prompt(mapping_info)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate an Elasticsearch query for: {user_prompt}"}
            ]
            
            logger.debug(f"Generating Elasticsearch query using {provider} provider")
            
            try:
                if provider == "azure":
                    response = await self.azure_client.chat.completions.create(
                        model=self.azure_deployment, 
                        messages=messages, 
                        temperature=0.1
                    )
                else:  # openai
                    response = await self.openai_client.chat.completions.create(
                        model=self.openai_model, 
                        messages=messages, 
                        temperature=0.1
                    )
                
                query_text = response.choices[0].message.content
                if not query_text:
                    raise ValueError(f"Empty response from {provider} API")
                
                try:
                    query_json = json.loads(query_text)
                    logger.debug(f"Successfully generated Elasticsearch query using {provider}")
                    return query_json
                except json.JSONDecodeError as json_err:
                    error_msg = f"Invalid JSON response from {provider}: {query_text[:200]}..."
                    logger.error(error_msg)
                    raise ValueError(error_msg) from json_err
                    
            except Exception as e:
                current_span = trace.get_current_span()
                current_span.set_status(Status(StatusCode.ERROR))
                current_span.record_exception(e)
                
                error_context = {
                    "provider": provider,
                    "model": self.azure_deployment if provider == "azure" else self.openai_model,
                    "prompt_length": len(user_prompt),
                    "mapping_indices": list(mapping_info.keys()),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                
                logger.error(f"Error generating Elasticsearch query: {error_context}")
                
                if return_debug:
                    error_context.update({
                        'messages': messages,
                        'initialization_status': self.get_initialization_status()
                    })
                
                raise ValueError(f"Failed to generate query using {provider}: {str(e)}") from e

    async def summarize_results(self, query_results: Dict[str, Any], original_prompt: str, provider: str = "auto", return_debug: bool = False) -> str:
        # Auto-select provider if not specified
        if provider == "auto":
            provider = self._get_default_provider()
            
        # Validate provider availability
        self._validate_provider(provider)
        
        with tracer.start_as_current_span(
            "ai_summarize_results", kind=SpanKind.CLIENT,
            attributes={
                "ai.provider": provider,
                "ai.prompt.length": len(original_prompt),
                "ai.results.count": len(query_results.get("hits", {}).get("hits", []))
            },
        ):
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
            
            logger.debug(f"Summarizing results using {provider} provider")
            
            try:
                if provider == "azure":
                    response = await self.azure_client.chat.completions.create(
                        model=self.azure_deployment, 
                        messages=messages, 
                        temperature=0.3
                    )
                else:  # openai
                    response = await self.openai_client.chat.completions.create(
                        model=self.openai_model, 
                        messages=messages, 
                        temperature=0.3
                    )
                
                summary = response.choices[0].message.content
                if not summary:
                    raise ValueError(f"Empty summary response from {provider} API")
                
                logger.debug(f"Successfully generated summary using {provider}")
                return summary
                
            except Exception as e:
                current_span = trace.get_current_span()
                current_span.set_status(Status(StatusCode.ERROR))
                current_span.record_exception(e)
                
                error_context = {
                    "provider": provider,
                    "model": self.azure_deployment if provider == "azure" else self.openai_model,
                    "prompt_length": len(original_prompt),
                    "results_count": len(query_results.get("hits", {}).get("hits", [])),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                
                logger.error(f"Error summarizing results: {error_context}")
                
                if return_debug:
                    error_context.update({
                        'messages': messages,
                        'initialization_status': self.get_initialization_status()
                    })
                
                raise ValueError(f"Failed to summarize results using {provider}: {str(e)}") from e

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

    async def free_chat(self, user_prompt: str, provider: str = "auto", return_debug: bool = False, 
                       context_info: Optional[Dict[str, Any]] = None, 
                       conversation_id: Optional[str] = None) -> Tuple[str, dict]:
        """
        Free chat mode that doesn't require Elasticsearch context
        """
        # Auto-select provider if not specified
        if provider == "auto":
            provider = self._get_default_provider()
            
        # Validate provider availability
        self._validate_provider(provider)
        
        with tracer.start_as_current_span("ai_free_chat", kind=SpanKind.CLIENT):
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
            
            logger.debug(f"Starting free chat using {provider} provider")
            
            try:
                if provider == "azure":
                    response = await self.azure_client.chat.completions.create(
                        model=self.azure_deployment, 
                        messages=messages, 
                        temperature=0.7,  # Slightly higher temperature for more creative responses
                        max_tokens=2000
                    )
                else:  # openai
                    response = await self.openai_client.chat.completions.create(
                        model=self.openai_model, 
                        messages=messages, 
                        temperature=0.7,
                        max_tokens=2000
                    )
                
                text = response.choices[0].message.content
                if not text:
                    raise ValueError(f"Empty response from {provider} API")
                    
                current_span.set_attribute("ai.response.length", len(text))
                current_span.set_status(Status(StatusCode.OK))
                
                logger.debug(f"Free chat completed successfully using {provider}")
                
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
                        'initialization_status': self.get_initialization_status(),
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
                
                error_context = {
                    "provider": provider,
                    "model": self.azure_deployment if provider == "azure" else self.openai_model,
                    "prompt_length": len(user_prompt),
                    "conversation_id": conversation_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                
                logger.error(f"Error in free chat: {error_context}")
                
                # Return error information
                error_response = f"I apologize, but I encountered an error while processing your request: {str(e)}"
                debug_info = {
                    'error': str(e),
                    'error_context': error_context,
                    'messages': messages,
                    'provider': provider,
                    'initialization_status': self.get_initialization_status()
                } if return_debug else {}
                
                return error_response, debug_info

    async def generate_chat(self, messages: List[Dict], *, model: Optional[str] = None, 
                          temperature: float = 0.2, stream: bool = False, 
                          conversation_id: Optional[str] = None, provider: str = "auto"):
        """Generate chat response with optional streaming support"""
        # Auto-select provider if not specified
        if provider == "auto":
            provider = self._get_default_provider()
            
        # Validate provider availability
        self._validate_provider(provider)
        
        with tracer.start_as_current_span("ai_generate_chat") as current_span:
            current_span.set_attributes({
                "ai.provider": provider,
                "ai.model": model or (self.azure_deployment if provider == "azure" else self.openai_model),
                "ai.stream": stream,
                "ai.conversation_id": conversation_id or "unknown",
                "ai.message_count": len(messages)
            })
            
            logger.debug(f"Generating chat response using {provider} provider (streaming: {stream})")
            
            try:
                if stream:
                    return self._stream_chat_response(messages, model, temperature, provider)
                else:
                    return await self._get_chat_response(messages, model, temperature, provider)
                    
            except Exception as e:
                current_span.set_status(Status(StatusCode.ERROR))
                current_span.record_exception(e)
                
                error_context = {
                    "provider": provider,
                    "model": model or (self.azure_deployment if provider == "azure" else self.openai_model),
                    "stream": stream,
                    "conversation_id": conversation_id,
                    "message_count": len(messages),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                
                logger.error(f"Error in generate_chat: {error_context}")
                raise ValueError(f"Failed to generate chat response using {provider}: {str(e)}") from e

    async def _stream_chat_response(self, messages: List[Dict], model: Optional[str], 
                                  temperature: float, provider: str):
        """Stream chat response"""
        logger.debug(f"Starting stream chat response using {provider}")
        
        try:
            if provider == "azure":
                response = await self.azure_client.chat.completions.create(
                    model=model or self.azure_deployment,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                    max_tokens=2000
                )
                
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        yield {
                            "type": "content",
                            "delta": chunk.choices[0].delta.content
                        }
                        
            else:  # openai
                response = await self.openai_client.chat.completions.create(
                    model=model or self.openai_model,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                    max_tokens=2000
                )
                
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        yield {
                            "type": "content",
                            "delta": chunk.choices[0].delta.content
                        }
            
            logger.debug(f"Stream completed successfully using {provider}")
            yield {"type": "done"}
            
        except Exception as e:
            error_context = {
                "provider": provider,
                "model": model or (self.azure_deployment if provider == "azure" else self.openai_model),
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            logger.error(f"Error in stream chat response: {error_context}")
            yield {
                "type": "error",
                "error": {
                    "code": "stream_failed", 
                    "message": str(e),
                    "provider": provider,
                    "initialization_status": self.get_initialization_status()
                }
            }

    async def _get_chat_response(self, messages: List[Dict], model: Optional[str], 
                               temperature: float, provider: str) -> Dict:
        """Get non-streaming chat response"""
        logger.debug(f"Getting chat response using {provider}")
        
        try:
            if provider == "azure":
                response = await self.azure_client.chat.completions.create(
                    model=model or self.azure_deployment,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=2000
                )
            else:  # openai
                response = await self.openai_client.chat.completions.create(
                    model=model or self.openai_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=2000
                )
            
            text = response.choices[0].message.content or ""
            if not text:
                logger.warning(f"Empty response from {provider} API")
            
            logger.debug(f"Chat response completed successfully using {provider}")
            
            return {
                "text": text,
                "usage": response.usage.model_dump() if response.usage else None
            }
            
        except Exception as e:
            error_context = {
                "provider": provider,
                "model": model or (self.azure_deployment if provider == "azure" else self.openai_model),
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            logger.error(f"Error getting chat response: {error_context}")
            raise ValueError(f"Failed to get chat response using {provider}: {str(e)}") from e

    async def generate_elasticsearch_chat(self, messages: List[Dict], schema_context: Dict[str, Any],
                                        model: Optional[str] = None, temperature: float = 0.7,
                                        conversation_id: Optional[str] = None,
                                        return_debug: bool = False, provider: str = "auto") -> Any:
        """Generate context-aware chat response with Elasticsearch schema"""
        # Auto-select provider if not specified
        if provider == "auto":
            provider = self._get_default_provider()
            
        # Validate provider availability
        self._validate_provider(provider)
        
        with tracer.start_as_current_span("ai_elasticsearch_chat") as current_span:
            current_span.set_attributes({
                "ai.provider": provider,
                "ai.model": model or (self.azure_deployment if provider == "azure" else self.openai_model),
                "ai.conversation_id": conversation_id or "unknown",
                "ai.schema_indices": list(schema_context.keys()) if schema_context else []
            })
            
            # Build enhanced system prompt with schema context
            system_prompt = self._build_elasticsearch_chat_system_prompt(schema_context)
            
            # Ensure we have a system message at the beginning
            enhanced_messages = [{"role": "system", "content": system_prompt}]
            enhanced_messages.extend(messages)
            
            logger.debug(f"Generating Elasticsearch chat using {provider} provider")
            
            try:
                if provider == "azure":
                    response = await self.azure_client.chat.completions.create(
                        model=model or self.azure_deployment,
                        messages=enhanced_messages,
                        temperature=temperature,
                        max_tokens=2000
                    )
                else:  # openai
                    response = await self.openai_client.chat.completions.create(
                        model=model or self.openai_model,
                        messages=enhanced_messages,
                        temperature=temperature,
                        max_tokens=2000
                    )
                
                text = response.choices[0].message.content or ""
                if not text:
                    logger.warning(f"Empty response from {provider} API")
                
                current_span.set_status(Status(StatusCode.OK))
                logger.debug(f"Elasticsearch chat completed successfully using {provider}")
                
                if return_debug:
                    debug_info = {
                        "messages": enhanced_messages,
                        "response": response.model_dump() if hasattr(response, 'model_dump') else str(response),
                        "schema_context": schema_context,
                        "provider": provider,
                        "model": model or (self.azure_deployment if provider == "azure" else self.openai_model),
                        "initialization_status": self.get_initialization_status()
                    }
                    return text, debug_info
                else:
                    return text
                    
            except Exception as e:
                current_span.set_status(Status(StatusCode.ERROR))
                current_span.record_exception(e)
                
                error_context = {
                    "provider": provider,
                    "model": model or (self.azure_deployment if provider == "azure" else self.openai_model),
                    "conversation_id": conversation_id,
                    "schema_indices": list(schema_context.keys()) if schema_context else [],
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                
                logger.error(f"Error in elasticsearch_chat: {error_context}")
                raise ValueError(f"Failed to generate Elasticsearch chat using {provider}: {str(e)}") from e

    def _build_elasticsearch_chat_system_prompt(self, schema_context: Dict[str, Any]) -> str:
        """Build system prompt with Elasticsearch schema context"""
        prompt = """You are an AI assistant with access to Elasticsearch data. You can help users understand their data, generate queries, and analyze results.

Available capabilities:
1. Answer questions about data structure and schema
2. Generate Elasticsearch queries when requested
3. Explain query results and data patterns
4. Provide general assistance and guidance

"""
        
        if schema_context:
            prompt += "Available Elasticsearch indices and their schemas:\n\n"
            for index_name, schema in schema_context.items():
                prompt += f"Index: {index_name}\n"
                if isinstance(schema, dict) and "properties" in schema:
                    prompt += f"Fields: {', '.join(schema['properties'].keys())}\n\n"
                else:
                    prompt += f"Schema: {json.dumps(schema, indent=2)}\n\n"
        
        prompt += """Important: Only generate actual Elasticsearch queries when the user specifically asks for a query. For general questions about the data or schema, provide informative responses without automatically creating queries."""
        
        return prompt

    async def generate_elasticsearch_chat_stream(self, messages: List[Dict], schema_context: Dict[str, Any],
                                               model: Optional[str] = None, temperature: float = 0.7,
                                               conversation_id: Optional[str] = None, provider: str = "auto"):
        """Stream context-aware chat response with Elasticsearch schema"""
        # Auto-select provider if not specified
        if provider == "auto":
            provider = self._get_default_provider()
            
        # Validate provider availability  
        self._validate_provider(provider)
        
        logger.debug(f"Starting Elasticsearch chat stream using {provider} provider")
        
        # Build enhanced system prompt with schema context
        system_prompt = self._build_elasticsearch_chat_system_prompt(schema_context)
        
        # Ensure we have a system message at the beginning
        enhanced_messages = [{"role": "system", "content": system_prompt}]
        enhanced_messages.extend(messages)
        
        # Use the streaming method with enhanced messages
        async for chunk in self._stream_chat_response(enhanced_messages, model, temperature, provider):
            yield chunk