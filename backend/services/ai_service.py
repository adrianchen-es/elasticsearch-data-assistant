from typing import Dict, Any, Optional
from openai import AsyncAzureOpenAI, AsyncOpenAI
from opentelemetry import trace
import json
import logging

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class AIService:
    def __init__(self, azure_api_key: str, azure_endpoint: str, azure_deployment: str, azure_version: Optional[str] = None, openai_api_key: Optional[str] = None):
        self.azure_api_key = azure_api_key
        self.azure_endpoint = azure_endpoint
        self.azure_deployment = azure_deployment
        self.azure_version = azure_version        
        self.openai_api_key = openai_api_key
        
        if azure_api_key and azure_endpoint:
            self.azure_client = AsyncAzureOpenAI(
                api_key=azure_api_key,
                azure_endpoint=azure_endpoint,
                api_version="2024-12-01-preview"
            )
        elif azure_api_key and azure_endpoint and azure_version:
            self.azure_client = AsyncAzureOpenAI(
                api_key=azure_api_key,
                azure_endpoint=azure_endpoint,
                api_version=azure_version
            )
        else:
            self.azure_client = None
            
        if openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        else:
            self.openai_client = None

    @tracer.start_as_current_span("ai_generate_query")
    async def generate_elasticsearch_query(
        self, 
        user_prompt: str, 
        mapping_info: Dict[str, Any],
        provider: str = "azure"
    ) -> Dict[str, Any]:
        """Generate Elasticsearch query from user prompt"""
        
        system_prompt = self._build_system_prompt(mapping_info)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate an Elasticsearch query for: {user_prompt}"}
        ]
        
        try:
            if provider == "azure" and self.azure_client:
                response = await self.azure_client.chat.completions.create(
                    model=azure_deployment,
                    messages=messages,
                    temperature=0.1
                )
            elif provider == "openai" and self.openai_client:
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    temperature=0.1
                )
            else:
                raise ValueError(f"AI provider {provider} not available")
            
            query_text = response.choices[0].message.content
            return json.loads(query_text)
            
        except Exception as e:
            logger.error(f"Error generating query: {e}")
            raise

    @tracer.start_as_current_span("ai_summarize_results")
    async def summarize_results(
        self, 
        query_results: Dict[str, Any], 
        original_prompt: str,
        provider: str = "azure"
    ) -> str:
        """Summarize Elasticsearch query results"""
        
        system_prompt = """You are an expert at summarizing Elasticsearch query results.
        Provide a clear, concise summary of the key findings from the search results.
        Focus on the most relevant information that answers the user's question.
        If there are no results, explain that clearly."""
        
        user_content = f"""
        Original question: {original_prompt}
        
        Query results:
        {json.dumps(query_results, indent=2)}
        
        Please summarize these results in a helpful way.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            if provider == "azure" and self.azure_client:
                response = await self.azure_client.chat.completions.create(
                    model=azure_deployment,
                    messages=messages,
                    temperature=0.3
                )
            elif provider == "openai" and self.openai_client:
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    temperature=0.3
                )
            else:
                raise ValueError(f"AI provider {provider} not available")
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error summarizing results: {e}")
            raise

    def _build_system_prompt(self, mapping_info: Dict[str, Any]) -> str:
        """Build system prompt with mapping information"""
        return f"""You are an expert Elasticsearch query generator.
        Generate valid Elasticsearch queries based on user requests.
        
        Available index mappings:
        {json.dumps(mapping_info, indent=2)}
        
        Guidelines:
        - Return only valid JSON query syntax
        - Use appropriate field names from the mapping
        - Consider field types when building queries
        - Use relevant aggregations when summarizing data is needed
        - Default to returning top 10 results unless specified
        - Use appropriate query types (match, term, range, etc.)
        
        Return only the JSON query, no additional text or formatting."""