import os
import socket
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    # Elasticsearch settings
    elasticsearch_url: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    elasticsearch_api_key: Optional[str] = os.getenv("ELASTICSEARCH_API_KEY")
    
    # Azure AI settings
    azure_ai_api_key: str = os.getenv("AZURE_AI_API_KEY", "")
    azure_ai_endpoint: str = os.getenv("AZURE_AI_ENDPOINT", "")
    azure_ai_deployment: str = os.getenv("AZURE_AI_DEPLOYMENT", "")
    azure_ai_model: str = os.getenv("AZURE_AI_MODEL", "gpt-4")
    azure_ai_version: Optional[str] = os.getenv("AZURE_AI_VERSION", "2024-12-01-preview")
    
    # Alternative AI providers
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # OpenTelemetry settings
    otel_exporter_otlp_protocol: bool = (os.getenv('OTEL_EXPORTER_OTLP_PROTOCOL', '')).lower() == 'otlp'
    otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "elasticsearch-ai-backend")
    otel_exporter_otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    otel_exporter_otlp_traces_endpoint: Optional[str] = os.getenv("OTEL_EXPORTER_GRPC_TRACES_ENDPOINT", "http://otel-collector:4318/v1/traces")
    otel_exporter_otlp_metrics_endpoint: Optional[str] = os.getenv("OTEL_EXPORTER_GRPC_METRICS_ENDPOINT", "http://otel-collector:4318/v1/metrics")
    otel_exporter_grpc_traces_endpoint: Optional[str] = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://otel-collector:4317")
    otel_exporter_grpc_metrics_endpoint: Optional[str] = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://otel-collector:4317")
    #otel_exporter_otlp_headers: dict = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    environment: str = os.getenv('NODE_ENV', 'development')
    version: str = "1.0.0"
    host_name: str = socket.gethostname()
    container_name: str = os.environ.get("CONTAINER_NAME", "unknown")
    
    # Cache settings
    mapping_cache_interval_minutes: int = int(os.getenv("MAPPING_CACHE_INTERVAL_MINUTES", "30"))
    
    class Config:
        env_file = ".env"

settings = Settings()