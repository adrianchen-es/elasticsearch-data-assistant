# backend/services/elasticsearch_service.py
from typing import Dict, Any, Optional, List
from elasticsearch import AsyncElasticsearch, ConnectionTimeout, RequestError
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from middleware.enhanced_telemetry import get_security_tracer, trace_async_function, DataSanitizer
from config.settings import settings
import json
import logging
import os  # Import os to read environment variables
import asyncio
import time


logger = logging.getLogger(__name__)
tracer = get_security_tracer(__name__)

# Initialize data sanitizer for enhanced security
sanitizer = DataSanitizer()

class ElasticsearchService:
    # Expose 'client' attribute at class level so tests that create Mock(spec=ElasticsearchService)
    # will allow setting `.client` without raising AttributeError
    client = None
    def __init__(self, url: str, api_key: Optional[str] = None):
        initialization_start_time = time.time()
        logger.info(f"🔍 Initializing Elasticsearch service for {self._mask_url(url)}")

        self.url = url
        self.api_key = api_key

        # Performance monitoring
        self._connection_stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0,
            "last_ping": None,
            "connection_pool_size": 0,
            "initialization_time": 0
        }

        # Use environment variable to determine if we should verify SSL certificates
        # Default to True if not set
        verify_certs = os.getenv("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"

        # Configure timeouts and connection settings with performance optimizations
        request_timeout = float(os.getenv("ELASTICSEARCH_REQUEST_TIMEOUT", "30"))
        max_retries = int(os.getenv("ELASTICSEARCH_MAX_RETRIES", "3"))
        retry_on_timeout = os.getenv("ELASTICSEARCH_RETRY_ON_TIMEOUT", "true").lower() == "true"

        # Enhanced connection pool settings for better performance
        pool_maxsize = int(os.getenv("ELASTICSEARCH_POOL_MAXSIZE", "50"))  # Increased from 20

        logger.info("🔧 Elasticsearch configuration:")
        logger.info(f"   • URL: {self._mask_url(url)}")
        logger.info(f"   • SSL Verification: {verify_certs}")
        logger.info(f"   • Request Timeout: {request_timeout}s")
        logger.info(f"   • Max Retries: {max_retries}")
        logger.info(f"   • Pool Max Size: {pool_maxsize}")
        logger.info(f"   • API Key: {'configured' if api_key else 'not configured'}")

        with tracer.start_as_current_span(
            "elasticsearch.initialize",
            attributes={"db.operation": "initialize"},
        ):
            try:
                client_creation_start = time.time()

                connection_params = {
                    "verify_certs": verify_certs,
                    "request_timeout": request_timeout,
                    "max_retries": max_retries,
                    "retry_on_timeout": retry_on_timeout,
                    "http_compress": True,  # Enable compression to reduce network overhead
                    "headers": {
                        "Connection": "keep-alive",  # Keep connections alive for reuse
                        "Accept-Encoding": "gzip, deflate",  # Enable compression
                    }
                }

                # Store pool size for monitoring
                self._connection_stats["connection_pool_size"] = pool_maxsize

                if api_key:
                    logger.debug("🔐 Creating Elasticsearch client with API key authentication")
                    self.client = AsyncElasticsearch(url, api_key=api_key, **connection_params)
                else:
                    logger.debug("🔓 Creating Elasticsearch client without authentication")
                    self.client = AsyncElasticsearch(url, **connection_params)

                client_creation_time = time.time() - client_creation_start
                initialization_time = time.time() - initialization_start_time

                self._connection_stats["initialization_time"] = initialization_time

                logger.info("✅ Elasticsearch client created successfully")
                logger.info("📊 Initialization performance:")
                logger.info(f"   • Client creation: {client_creation_time:.3f}s")
                logger.info(f"   • Total initialization: {initialization_time:.3f}s")

            except Exception as e:
                initialization_time = time.time() - initialization_start_time
                logger.error(f"❌ Failed to initialize Elasticsearch client after {initialization_time:.3f}s: {e}")
                raise

    def _mask_url(self, url: str) -> str:
        """Mask sensitive parts of the URL for logging"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.password:
                # Mask password in URL
                masked_url = url.replace(parsed.password, "***")
            else:
                masked_url = url
            return masked_url
        except Exception:
            # If URL parsing fails, just show the scheme and host
            return f"{url.split('://')[0]}://***" if '://' in url else "***"

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics for monitoring"""
        return self._connection_stats.copy()

    async def _update_stats(self, success: bool, response_time: float):
        """Update connection statistics"""
        self._connection_stats["total_requests"] += 1
        if not success:
            self._connection_stats["failed_requests"] += 1

        # Update rolling average response time
        current_avg = self._connection_stats["avg_response_time"]
        total_requests = self._connection_stats["total_requests"]
        self._connection_stats["avg_response_time"] = (
            (current_avg * (total_requests - 1) + response_time) / total_requests
        )

    @trace_async_function("elasticsearch.get_index_mapping", include_args=True)
    async def get_index_mapping(self, index_name: str) -> Dict[str, Any]:
        """Get mapping for a specific index with timeout and retry handling"""
        import time
        start_time = time.time()

        with tracer.start_as_current_span(
            "elasticsearch.get_mapping",
            attributes={"db.operation": "get_mapping", "db.elasticsearch.index": index_name},
        ):
            max_attempts = int(os.getenv("ELASTICSEARCH_MAPPING_MAX_ATTEMPTS", "3"))
            base_delay = float(os.getenv("ELASTICSEARCH_MAPPING_BASE_DELAY", "1.0"))

            for attempt in range(max_attempts):
                try:
                    logger.debug(f"Attempting to get mapping for index {index_name} (attempt {attempt + 1}/{max_attempts})")

                    # Use asyncio.wait_for to add an additional timeout layer
                    mapping_timeout = float(os.getenv("ELASTICSEARCH_MAPPING_TIMEOUT", "15"))
                    response = await asyncio.wait_for(
                        self.client.indices.get_mapping(index=index_name),
                        timeout=mapping_timeout
                    )

                    # Update performance statistics
                    response_time = time.time() - start_time
                    await self._update_stats(success=True, response_time=response_time)

                    logger.debug(f"Successfully retrieved mapping for index {index_name} in {response_time:.2f}s")
                    return response

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout getting mapping for index {index_name} (attempt {attempt + 1}/{max_attempts})")
                    if attempt == max_attempts - 1:
                        response_time = time.time() - start_time
                        await self._update_stats(success=False, response_time=response_time)
                        logger.error(f"Final timeout getting mapping for index {index_name} after {max_attempts} attempts")
                        raise ConnectionTimeout(f"Timeout getting mapping for index {index_name} after {max_attempts} attempts")

                except ConnectionTimeout as e:
                    logger.warning(f"Connection timeout getting mapping for index {index_name} (attempt {attempt + 1}/{max_attempts}): {e}")
                    if attempt == max_attempts - 1:
                        response_time = time.time() - start_time
                        await self._update_stats(success=False, response_time=response_time)
                        logger.error(f"Final connection timeout getting mapping for index {index_name}: {e}")
                        raise

                except RequestError as e:
                    # Don't retry on request errors (e.g., index not found)
                    logger.error(f"Request error getting mapping for index {index_name}: {e}")
                    raise

                except Exception as e:
                    logger.warning(f"Unexpected error getting mapping for index {index_name} (attempt {attempt + 1}/{max_attempts}): {e}")
                    if attempt == max_attempts - 1:
                        logger.error(f"Final error getting mapping for index {index_name}: {e}")
                        raise

                # Exponential backoff before retry
                if attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.debug(f"Waiting {delay} seconds before retry")
                    await asyncio.sleep(delay)

    async def list_indices(self) -> List[str]:
        """List all indices with timeout handling and configurable filtering"""
        with tracer.start_as_current_span("elasticsearch.list_indices", attributes={"db.operation": "list_indices"}):
            try:
                # Add timeout for listing indices
                indices_timeout = float(os.getenv("ELASTICSEARCH_INDICES_TIMEOUT", "10"))
                response = await asyncio.wait_for(
                    self.client.cat.indices(format="json"),
                    timeout=indices_timeout
                )

                # Apply configurable filtering
                filtered_indices = []
                for idx in response:
                    index_name = idx['index']

                    # Check if it's a data stream first (before system index filtering)
                    is_data_stream = self._is_data_stream_index(index_name)

                    # Skip data streams if not enabled
                    if not settings.show_data_streams and is_data_stream:
                        logger.debug(f"Filtering out data stream index: {index_name}")
                        continue

                    # Skip system indices (starting with .) if filtering is enabled,
                    # but allow data streams even if they start with dot
                    if settings.filter_system_indices and index_name.startswith('.') and not is_data_stream:
                        logger.debug(f"Filtering out system index: {index_name}")
                        continue

                    # Skip monitoring indices if filtering is enabled
                    if settings.filter_monitoring_indices and self._is_monitoring_index(index_name):
                        logger.debug(f"Filtering out monitoring index: {index_name}")
                        continue

                    # Skip closed indices if filtering is enabled
                    if settings.filter_closed_indices and idx.get('status') == 'close':
                        logger.debug(f"Filtering out closed index: {index_name}")
                        continue

                    filtered_indices.append(index_name)

                logger.debug(f"Found {len(filtered_indices)} indices out of {len(response)} total indices")
                logger.debug(f"Filtering settings: system={settings.filter_system_indices}, monitoring={settings.filter_monitoring_indices}, closed={settings.filter_closed_indices}, data_streams={settings.show_data_streams}")
                return filtered_indices

            except asyncio.TimeoutError:
                logger.error("Timeout listing indices")
                raise ConnectionTimeout("Timeout listing indices")
            except Exception as e:
                logger.error(f"Error listing indices: {e}")
                raise

    def _is_monitoring_index(self, index_name: str) -> bool:
        """Check if an index is a monitoring/system index that should typically be filtered"""
        monitoring_patterns = [
            '.monitoring-',         # Elasticsearch monitoring indices
            '.ds-.monitoring-',     # Data stream monitoring indices
            '.watcher-history-',    # Watcher history indices (more specific)
            '.ml-anomalies-',       # Machine learning anomalies indices
            '.ml-config',           # Machine learning config indices
            '.ml-notifications',    # Machine learning notifications
            '.ml-state',            # Machine learning state indices
        ]

        # Check for exact monitoring patterns, not general .security- or .kibana patterns
        # Those should be handled by system index filtering instead
        return any(index_name.startswith(pattern) for pattern in monitoring_patterns)

    def _is_data_stream_index(self, index_name: str) -> bool:
        """Check if an index is likely a data stream backing index"""
        # Data stream backing indices often have patterns like:
        # - .ds-<data-stream-name>-<timestamp>-<generation>
        # - partial-.ds-<data-stream-name>-<timestamp>-<generation>
        return ('.ds-' in index_name and
                not self._is_monitoring_index(index_name))

    @trace_async_function("elasticsearch.execute_query", include_args=True)
    async def execute_query(self, index_name: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a search query with timeout handling"""
        with tracer.start_as_current_span("elasticsearch.execute_query", attributes={"db.operation": "search", "db.elasticsearch.index": index_name}):
            span = trace.get_current_span()
            try:
                # Add sanitized query as db.statement (per semantic conventions)
                try:
                    sanitized_query = sanitizer.sanitize_value(query)
                    # Ensure the attribute is a string (OTel attribute types are limited)
                    if not isinstance(sanitized_query, str):
                        try:
                            sanitized_query = json.dumps(sanitized_query)
                        except Exception:
                            sanitized_query = str(sanitized_query)
                    span.set_attribute("db.statement", sanitized_query)
                    # Attach event with stringified query to avoid invalid attribute types
                    span.add_event("db.query", {"query": sanitized_query})
                except Exception:
                    span.set_attribute("db.statement", "<unavailable>")

                # Add timeout for search queries
                search_timeout = float(os.getenv("ELASTICSEARCH_SEARCH_TIMEOUT", "30"))
                response = await asyncio.wait_for(
                    self.client.search(index=index_name, body=query),
                    timeout=search_timeout
                )
                # Mark span as successful
                try:
                    span.set_status(Status(StatusCode.OK))
                except Exception:
                    # Older/newer SDKs may accept different signatures
                    try:
                        span.set_status(StatusCode.OK)
                    except Exception:
                        pass
                return response
            except asyncio.TimeoutError:
                logger.error(f"Timeout executing query on index {index_name}")
                logger.error(f"Query timeout executing query on index {index_name}")
                logger.debug(f"Sanitized query: {sanitizer.sanitize_data(query)}")
                raise ConnectionTimeout(f"Timeout executing query on index {index_name}")
            except Exception as e:
                logger.error(f"Error executing query on index {index_name}: {e}")
                logger.debug(f"Sanitized query: {sanitizer.sanitize_data(query)}")
                raise

    async def search(self, index: str, body: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Backward compatibility method for search queries.
        
        Args:
            index: The index name to search
            body: The query body
            timeout: Optional timeout (not used as we have global timeouts)
            
        Returns:
            The search response
        """
        return await self.execute_query(index_name=index, query=body)

    @trace_async_function("elasticsearch.validate_query", include_args=True)
    async def validate_query(self, index_name: str, query: Dict[str, Any]) -> bool:
        """Validate a query without executing it with timeout handling"""
        with tracer.start_as_current_span("elasticsearch.validate_query", attributes={"db.operation": "validate_query", "db.elasticsearch.index": index_name}):
            try:
                # Add timeout for query validation
                validation_timeout = float(os.getenv("ELASTICSEARCH_VALIDATION_TIMEOUT", "10"))
                await asyncio.wait_for(
                    self.client.indices.validate_query(index=index_name, body={"query": query.get("query", {})}),
                    timeout=validation_timeout
                )
                return True
            except asyncio.TimeoutError:
                logger.error(f"Timeout validating query for index {index_name}")
                return False
            except Exception as e:
                logger.error(f"Query validation failed: {e}")
                return False

    async def close(self):
        """Close the Elasticsearch client"""
        close_start_time = time.time()
        logger.info("🔌 Closing Elasticsearch connections...")

        with tracer.start_as_current_span("elasticsearch.close_client", attributes={"db.operation": "close_client"}):
            try:
                if hasattr(self, 'client') and self.client:
                    await self.client.close()

                    close_duration = time.time() - close_start_time
                    logger.info(f"✅ Elasticsearch connections closed successfully in {close_duration:.3f}s")

                    # Log final connection statistics
                    stats = self.get_connection_stats()
                    logger.info("📊 Final connection statistics:")
                    logger.info(f"   • Total requests: {stats['total_requests']}")
                    logger.info(f"   • Failed requests: {stats['failed_requests']}")
                    logger.info(f"   • Average response time: {stats['avg_response_time']:.3f}s")
                    logger.info(f"   • Success rate: {((stats['total_requests'] - stats['failed_requests']) / max(stats['total_requests'], 1) * 100):.1f}%")
                else:
                    logger.info("🔌 Elasticsearch client was not initialized or already closed")

            except Exception as e:
                close_duration = time.time() - close_start_time
                logger.error(f"❌ Error closing Elasticsearch connections after {close_duration:.3f}s: {e}")
                # Don't re-raise the exception during shutdown
                logger.info("🔄 Continuing with shutdown despite connection close error")
