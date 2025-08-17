# backend/services/enhanced_search_service.py
"""
Enhanced search service with intelligent query optimization, semantic analysis,
and comprehensive error handling with detailed logging.
"""

import json
import logging
import asyncio
import re
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode

from .elasticsearch_service import ElasticsearchService
from .ai_service import AIService
from middleware.enhanced_telemetry import get_security_tracer, trace_async_function, DataSanitizer

logger = logging.getLogger(__name__)
tracer = get_security_tracer(__name__)

class QueryComplexity(Enum):
    """Query complexity levels for optimization decisions."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    ADVANCED = "advanced"

class SearchOptimization(Enum):
    """Search optimization strategies."""
    PERFORMANCE = "performance"
    ACCURACY = "accuracy"
    BALANCED = "balanced"

@dataclass
class QueryAnalysis:
    """Comprehensive query analysis results."""
    complexity: QueryComplexity
    estimated_docs: int
    field_usage: Dict[str, int]
    query_types: List[str]
    suggestions: List[str]
    performance_score: float
    semantic_fields: List[str]
    aggregation_complexity: int
    index_coverage: float
    optimization_opportunities: List[str]

@dataclass
class SearchMetrics:
    """Search operation metrics for monitoring."""
    query_time_ms: int
    total_hits: int
    max_score: float
    shard_info: Dict[str, Any]
    cache_usage: Dict[str, Any]
    memory_usage_mb: float
    cpu_usage_percent: float

@dataclass
class EnhancedSearchResult:
    """Enhanced search results with metadata and insights."""
    hits: List[Dict[str, Any]]
    total_hits: int
    max_score: float
    took_ms: int
    timed_out: bool
    shards_info: Dict[str, Any]
    aggregations: Dict[str, Any]
    analysis: QueryAnalysis
    metrics: SearchMetrics
    suggestions: List[str]
    related_queries: List[str]

class EnhancedSearchService:
    """Enhanced search service with intelligent optimization and analysis."""
    
    def __init__(self, es_service: ElasticsearchService, ai_service: AIService):
        self.es_service = es_service
        self.ai_service = ai_service
        self.sanitizer = DataSanitizer()
        self.query_cache = {}
        self.performance_history = {}
        
    @trace_async_function("search.execute_enhanced", include_args=True)
    async def execute_enhanced_search(self,
                                     index_name: str,
                                     query: Dict[str, Any],
                                     optimization: SearchOptimization = SearchOptimization.BALANCED,
                                     explain: bool = False,
                                     profile: bool = False) -> EnhancedSearchResult:
        """Execute search with comprehensive analysis and optimization."""
        
        with tracer.start_span("enhanced_search.execute") as span:
            span.set_attribute("search.index", index_name)
            span.set_attribute("search.optimization", optimization.value)
            span.set_attribute("search.explain", explain)
            span.set_attribute("search.profile", profile)
            
            try:
                # Pre-process and analyze query
                analysis = await self._analyze_query(index_name, query)
                span.set_attribute("search.complexity", analysis.complexity.value)
                span.set_attribute("search.estimated_docs", analysis.estimated_docs)
                
                # Optimize query based on analysis and strategy
                optimized_query = await self._optimize_query(query, analysis, optimization)
                
                # Execute the search with enhanced options
                search_params = {
                    "index": index_name,
                    "body": optimized_query,
                    "timeout": "30s",
                    "allow_partial_search_results": True
                }
                
                if explain:
                    search_params["explain"] = True
                    
                if profile:
                    search_params["profile"] = True
                
                # Execute search with timing
                start_time = asyncio.get_event_loop().time()
                response = await self.es_service.client.search(**search_params)
                execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                # Extract metrics
                metrics = self._extract_metrics(response, execution_time)
                span.set_attribute("search.took_ms", metrics.query_time_ms)
                span.set_attribute("search.total_hits", metrics.total_hits)
                
                # Generate suggestions and related queries
                suggestions = await self._generate_suggestions(index_name, query, analysis, response)
                related_queries = await self._generate_related_queries(index_name, query, response)
                
                # Build enhanced result
                result = EnhancedSearchResult(
                    hits=response.get("hits", {}).get("hits", []),
                    total_hits=response.get("hits", {}).get("total", {}).get("value", 0),
                    max_score=response.get("hits", {}).get("max_score", 0.0),
                    took_ms=response.get("took", 0),
                    timed_out=response.get("timed_out", False),
                    shards_info=response.get("_shards", {}),
                    aggregations=response.get("aggregations", {}),
                    analysis=analysis,
                    metrics=metrics,
                    suggestions=suggestions,
                    related_queries=related_queries
                )
                
                # Update performance history
                await self._update_performance_history(index_name, query, metrics, analysis)
                
                span.set_status(Status(StatusCode.OK))
                return result
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                logger.error(f"Enhanced search failed for index {index_name}: {e}")
                raise

    @trace_async_function("search.analyze_query")
    async def _analyze_query(self, index_name: str, query: Dict[str, Any]) -> QueryAnalysis:
        """Analyze query complexity and characteristics."""
        
        with tracer.start_span("query_analysis") as span:
            try:
                # Get index mapping for analysis
                mapping = await self.es_service.get_index_mapping(index_name)
                properties = mapping.get(index_name, {}).get("mappings", {}).get("properties", {})
                
                # Analyze query structure
                query_types = self._extract_query_types(query)
                field_usage = self._analyze_field_usage(query, properties)
                complexity = self._determine_complexity(query, query_types)
                
                # Estimate document count impact
                estimated_docs = await self._estimate_affected_documents(index_name, query)
                
                # Identify semantic fields
                semantic_fields = self._identify_semantic_fields(properties, field_usage)
                
                # Analyze aggregations
                agg_complexity = self._analyze_aggregations(query.get("aggs", {}))
                
                # Calculate index coverage
                index_coverage = self._calculate_index_coverage(field_usage, properties)
                
                # Generate optimization opportunities
                optimization_opportunities = self._identify_optimization_opportunities(
                    query, query_types, field_usage, properties
                )
                
                # Calculate performance score
                performance_score = self._calculate_performance_score(
                    complexity, estimated_docs, agg_complexity, index_coverage
                )
                
                # Generate suggestions
                suggestions = self._generate_query_suggestions(
                    query, query_types, field_usage, optimization_opportunities
                )
                
                analysis = QueryAnalysis(
                    complexity=complexity,
                    estimated_docs=estimated_docs,
                    field_usage=field_usage,
                    query_types=query_types,
                    suggestions=suggestions,
                    performance_score=performance_score,
                    semantic_fields=semantic_fields,
                    aggregation_complexity=agg_complexity,
                    index_coverage=index_coverage,
                    optimization_opportunities=optimization_opportunities
                )
                
                span.set_attribute("analysis.complexity", complexity.value)
                span.set_attribute("analysis.performance_score", performance_score)
                span.set_attribute("analysis.field_count", len(field_usage))
                
                return analysis
                
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Query analysis failed: {e}")
                raise

    def _extract_query_types(self, query: Dict[str, Any]) -> List[str]:
        """Extract all query types used in the query."""
        query_types = []
        
        def extract_from_dict(d: Dict[str, Any], path: str = ""):
            for key, value in d.items():
                if key in ["match", "term", "range", "bool", "wildcard", "regexp", 
                          "fuzzy", "prefix", "exists", "nested", "has_child", "has_parent",
                          "function_score", "dis_max", "constant_score", "boosting"]:
                    query_types.append(key)
                
                if isinstance(value, dict):
                    extract_from_dict(value, f"{path}.{key}" if path else key)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            extract_from_dict(item, f"{path}.{key}" if path else key)
        
        query_body = query.get("query", {})
        if query_body:
            extract_from_dict(query_body)
        
        return list(set(query_types))

    def _analyze_field_usage(self, query: Dict[str, Any], properties: Dict[str, Any]) -> Dict[str, int]:
        """Analyze which fields are used and how often."""
        field_usage = {}
        
        def analyze_dict(d: Dict[str, Any]):
            for key, value in d.items():
                # Check if this is a field reference
                if key in properties:
                    field_usage[key] = field_usage.get(key, 0) + 1
                
                # Look for field references in common query structures
                if isinstance(value, dict):
                    # Check for field references in nested structures
                    for nested_key in value.keys():
                        if nested_key in properties:
                            field_usage[nested_key] = field_usage.get(nested_key, 0) + 1
                    analyze_dict(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            analyze_dict(item)
        
        analyze_dict(query)
        return field_usage

    def _determine_complexity(self, query: Dict[str, Any], query_types: List[str]) -> QueryComplexity:
        """Determine overall query complexity."""
        complexity_score = 0
        
        # Base complexity from query types
        simple_queries = ["match", "term", "range", "exists"]
        medium_queries = ["bool", "wildcard", "fuzzy", "prefix"]
        complex_queries = ["nested", "has_child", "has_parent", "function_score"]
        
        for q_type in query_types:
            if q_type in simple_queries:
                complexity_score += 1
            elif q_type in medium_queries:
                complexity_score += 2
            elif q_type in complex_queries:
                complexity_score += 4
        
        # Additional complexity factors
        if query.get("aggs"):
            complexity_score += 2
        
        if query.get("sort"):
            complexity_score += 1
        
        if query.get("highlight"):
            complexity_score += 1
        
        # Determine final complexity
        if complexity_score <= 2:
            return QueryComplexity.SIMPLE
        elif complexity_score <= 5:
            return QueryComplexity.MEDIUM
        elif complexity_score <= 10:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.ADVANCED

    async def _estimate_affected_documents(self, index_name: str, query: Dict[str, Any]) -> int:
        """Estimate number of documents that would be affected."""
        try:
            # Use count API for estimation
            count_query = {"query": query.get("query", {"match_all": {}})}
            response = await self.es_service.client.count(index=index_name, body=count_query)
            return response.get("count", 0)
        except Exception as e:
            logger.debug(f"Failed to estimate document count: {e}")
            return 0

    def _identify_semantic_fields(self, properties: Dict[str, Any], field_usage: Dict[str, int]) -> List[str]:
        """Identify fields that are likely semantic (text) fields."""
        semantic_fields = []
        
        for field_name, field_config in properties.items():
            if field_name in field_usage:
                field_type = field_config.get("type", "")
                if field_type == "text" or (field_type == "" and "analyzer" in field_config):
                    semantic_fields.append(field_name)
        
        return semantic_fields

    def _analyze_aggregations(self, aggs: Dict[str, Any]) -> int:
        """Analyze aggregation complexity."""
        if not aggs:
            return 0
        
        complexity = 0
        
        def analyze_agg(agg_def: Dict[str, Any]):
            nonlocal complexity
            # agg_def is typically a dict mapping agg_name -> agg_body
            for name, body in agg_def.items():
                if not isinstance(body, dict):
                    continue
                # Body may contain the specific aggregation type as a key
                for agg_type, agg_config in body.items():
                    if agg_type in ["terms", "date_histogram", "histogram"]:
                        complexity += 1
                    elif agg_type in ["nested", "reverse_nested"]:
                        complexity += 2
                    elif agg_type in ["percentiles", "percentile_ranks", "stats", "extended_stats"]:
                        complexity += 1
                    # sub-aggregations are usually under 'aggs' or 'aggregations'
                    if isinstance(agg_config, dict):
                        if 'aggs' in agg_config and isinstance(agg_config['aggs'], dict):
                            analyze_agg(agg_config['aggs'])
                        if 'aggregations' in agg_config and isinstance(agg_config['aggregations'], dict):
                            analyze_agg(agg_config['aggregations'])
                # Also check for nested structure where agg_def directly contains agg types
                # (already handled above)

        analyze_agg(aggs)
        return complexity

    def _calculate_index_coverage(self, field_usage: Dict[str, int], properties: Dict[str, Any]) -> float:
        """Calculate what percentage of index fields are being used."""
        if not properties:
            return 0.0
        
        used_fields = len(field_usage)
        total_fields = len(properties)
        
        return (used_fields / total_fields) * 100.0 if total_fields > 0 else 0.0

    def _identify_optimization_opportunities(self,
                                           query: Dict[str, Any],
                                           query_types: List[str],
                                           field_usage: Dict[str, int],
                                           properties: Dict[str, Any]) -> List[str]:
        """Identify potential optimization opportunities."""
        opportunities = []
        
        # Check for missing filters
        if "bool" in query_types and "filter" not in str(query):
            opportunities.append("Consider using filter context for non-scoring clauses")
        
        # Check for wildcard queries that could be optimized
        if "wildcard" in query_types:
            opportunities.append("Wildcard queries can be slow - consider using prefix or edge_ngram")
        
        # Check for sorting without filtering
        if query.get("sort") and not any(t in query_types for t in ["term", "range", "bool"]):
            opportunities.append("Sorting large result sets - consider adding filters")
        
        # Check for high cardinality aggregations
        aggs = query.get("aggs", {})
        if aggs and "terms" in str(aggs):
            opportunities.append("Terms aggregations on high cardinality fields can be expensive")
        
        # Check for missing field type optimizations
        for field_name in field_usage:
            field_config = properties.get(field_name, {})
            field_type = field_config.get("type", "")
            
            if field_type == "text" and "keyword" not in str(field_config):
                opportunities.append(f"Consider adding keyword mapping to {field_name} for aggregations")
        
        return opportunities

    def _calculate_performance_score(self,
                                   complexity: QueryComplexity,
                                   estimated_docs: int,
                                   agg_complexity: int,
                                   index_coverage: float) -> float:
        """Calculate overall performance score (0-100, higher is better)."""
        score = 100.0
        
        # Complexity penalty
        complexity_penalties = {
            QueryComplexity.SIMPLE: 0,
            QueryComplexity.MEDIUM: 10,
            QueryComplexity.COMPLEX: 25,
            QueryComplexity.ADVANCED: 40
        }
        score -= complexity_penalties.get(complexity, 0)
        
        # Document count penalty
        if estimated_docs > 1000000:
            score -= 30
        elif estimated_docs > 100000:
            score -= 20
        elif estimated_docs > 10000:
            score -= 10
        
        # Aggregation penalty
        score -= min(agg_complexity * 5, 20)
        
        # Index coverage bonus (using more fields can be good or bad)
        if index_coverage > 50:
            score -= 10  # Too many fields might be inefficient
        elif index_coverage < 5:
            score += 5   # Focused queries are often better
        
        return max(0.0, min(100.0, score))

    def _generate_query_suggestions(self,
                                  query: Dict[str, Any],
                                  query_types: List[str],
                                  field_usage: Dict[str, int],
                                  opportunities: List[str]) -> List[str]:
        """Generate query improvement suggestions."""
        suggestions = []
        
        # Add optimization opportunities as suggestions
        suggestions.extend(opportunities[:3])  # Limit to top 3
        
        # Query-specific suggestions
        if "match" in query_types and len(query_types) == 1:
            suggestions.append("Consider using match_phrase for exact phrase matching")
        
        if "bool" in query_types:
            suggestions.append("Use filter context for non-scoring conditions to improve performance")
        
        if not query.get("size"):
            suggestions.append("Consider setting a size limit to improve response time")
        
        return suggestions[:5]  # Limit to top 5 suggestions

    @trace_async_function("search.optimize_query")
    async def _optimize_query(self,
                            query: Dict[str, Any],
                            analysis: QueryAnalysis,
                            optimization: SearchOptimization) -> Dict[str, Any]:
        """Optimize query based on analysis and strategy."""
        
        optimized = query.copy()
        
        with tracer.start_span("query_optimization") as span:
            span.set_attribute("optimization.strategy", optimization.value)
            span.set_attribute("optimization.complexity", analysis.complexity.value)
            
            if optimization == SearchOptimization.PERFORMANCE:
                optimized = await self._optimize_for_performance(optimized, analysis)
            elif optimization == SearchOptimization.ACCURACY:
                optimized = await self._optimize_for_accuracy(optimized, analysis)
            else:  # BALANCED
                optimized = await self._optimize_balanced(optimized, analysis)
            
            # Common optimizations
            optimized = self._apply_common_optimizations(optimized, analysis)
            
            return optimized

    async def _optimize_for_performance(self, query: Dict[str, Any], analysis: QueryAnalysis) -> Dict[str, Any]:
        """Optimize query for maximum performance."""
        optimized = query.copy()
        
        # Set reasonable size limits
        if not optimized.get("size"):
            optimized["size"] = 20
        elif optimized.get("size", 0) > 100:
            optimized["size"] = 100
        
        # Add timeout
        optimized["timeout"] = "10s"
        
        # Optimize bool queries to use filter context
        if "bool" in str(optimized):
            optimized = self._convert_to_filter_context(optimized)
        
        # Limit aggregations
        if optimized.get("aggs") and analysis.aggregation_complexity > 3:
            optimized = self._simplify_aggregations(optimized)
        
        return optimized

    async def _optimize_for_accuracy(self, query: Dict[str, Any], analysis: QueryAnalysis) -> Dict[str, Any]:
        """Optimize query for maximum accuracy."""
        optimized = query.copy()
        
        # Increase size for better recall
        if not optimized.get("size") or optimized.get("size", 0) < 50:
            optimized["size"] = 50
        
        # Add explain for debugging
        optimized["explain"] = True
        
        # Use more sophisticated matching for text fields
        if analysis.semantic_fields:
            optimized = self._enhance_text_matching(optimized, analysis.semantic_fields)
        
        return optimized

    async def _optimize_balanced(self, query: Dict[str, Any], analysis: QueryAnalysis) -> Dict[str, Any]:
        """Apply balanced optimizations."""
        optimized = query.copy()
        
        # Moderate size limit
        if not optimized.get("size"):
            optimized["size"] = 50
        elif optimized.get("size", 0) > 200:
            optimized["size"] = 200
        
        # Add reasonable timeout
        optimized["timeout"] = "20s"
        
        # Selective filter context conversion
        if analysis.performance_score < 50:
            optimized = self._convert_to_filter_context(optimized)
        
        return optimized

    def _apply_common_optimizations(self, query: Dict[str, Any], analysis: QueryAnalysis) -> Dict[str, Any]:
        """Apply universally beneficial optimizations."""
        optimized = query.copy()
        
        # Add track_total_hits for better performance on large result sets
        if analysis.estimated_docs > 10000:
            optimized["track_total_hits"] = 10000
        
        # Add source filtering for large documents
        if not optimized.get("_source"):
            optimized["_source"] = True  # Can be customized based on needs
        
        return optimized

    def _convert_to_filter_context(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Convert appropriate clauses to filter context."""
        # This is a simplified implementation
        # In practice, you'd need more sophisticated logic
        return query

    def _simplify_aggregations(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Simplify complex aggregations for better performance."""
        # This is a simplified implementation
        # In practice, you'd implement specific aggregation optimizations
        return query

    def _enhance_text_matching(self, query: Dict[str, Any], semantic_fields: List[str]) -> Dict[str, Any]:
        """Enhance text matching for better accuracy."""
        # This is a simplified implementation
        # In practice, you'd implement sophisticated text matching enhancements
        return query

    def _extract_metrics(self, response: Dict[str, Any], execution_time: float) -> SearchMetrics:
        """Extract comprehensive metrics from search response."""
        
        shards = response.get("_shards", {})
        profile = response.get("profile", {})
        
        # Extract basic metrics
        total_hits = response.get("hits", {}).get("total", {}).get("value", 0)
        max_score = response.get("hits", {}).get("max_score", 0.0)
        
        # Calculate memory usage (simplified)
        memory_usage = self._estimate_memory_usage(response)
        
        # Extract CPU usage from profile if available
        cpu_usage = self._extract_cpu_usage(profile)
        
        return SearchMetrics(
            query_time_ms=int(execution_time),
            total_hits=total_hits,
            max_score=max_score or 0.0,
            shard_info=shards,
            cache_usage={},  # Would be extracted from cluster stats
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage
        )

    def _estimate_memory_usage(self, response: Dict[str, Any]) -> float:
        """Estimate memory usage based on response size."""
        try:
            response_str = json.dumps(response)
            return len(response_str) / (1024 * 1024)  # Convert to MB
        except:
            return 0.0

    def _extract_cpu_usage(self, profile: Dict[str, Any]) -> float:
        """Extract CPU usage from profile information."""
        # This would extract actual CPU metrics from the profile
        # For now, return a placeholder
        return 0.0

    @trace_async_function("search.generate_suggestions")
    async def _generate_suggestions(self,
                                  index_name: str,
                                  query: Dict[str, Any],
                                  analysis: QueryAnalysis,
                                  response: Dict[str, Any]) -> List[str]:
        """Generate intelligent suggestions based on search results."""
        
        suggestions = []
        
        # Performance-based suggestions
        if analysis.performance_score < 50:
            suggestions.append("Consider adding filters to improve query performance")
        
        # Result-based suggestions
        total_hits = response.get("hits", {}).get("total", {}).get("value", 0)
        
        if total_hits == 0:
            suggestions.extend([
                "Try using broader search terms",
                "Check for typos in your search query",
                "Consider using wildcard or fuzzy matching"
            ])
        elif total_hits > 10000:
            suggestions.extend([
                "Results are very broad - consider adding more specific filters",
                "Use date ranges or categories to narrow down results"
            ])
        
        # Field-specific suggestions
        if analysis.semantic_fields:
            suggestions.append("Use phrase matching for exact phrase searches")
        
        return suggestions[:3]  # Limit to top 3

    @trace_async_function("search.generate_related_queries")
    async def _generate_related_queries(self,
                                      index_name: str,
                                      query: Dict[str, Any],
                                      response: Dict[str, Any]) -> List[str]:
        """Generate related query suggestions using AI."""
        
        try:
            # Extract search terms from query
            search_terms = self._extract_search_terms(query)
            
            if not search_terms:
                return []
            
            # Use AI service to generate related queries
            prompt = f"""
            Based on the search query with terms: {', '.join(search_terms)}
            Generate 3 related search queries that users might be interested in.
            Return only the search terms, not full Elasticsearch queries.
            """
            
            ai_response = await self.ai_service.generate_elasticsearch_query(
                prompt, {}, return_debug=False
            )
            
            # Extract suggestions from AI response
            # This would need proper parsing of the AI response
            return []
            
        except Exception as e:
            logger.debug(f"Failed to generate related queries: {e}")
            return []

    def _extract_search_terms(self, query: Dict[str, Any]) -> List[str]:
        """Extract search terms from query for related query generation."""
        terms = []
        
        def extract_from_dict(d: Dict[str, Any]):
            for key, value in d.items():
                if key == "query" and isinstance(value, str):
                    terms.append(value)
                elif key in ["match", "match_phrase"] and isinstance(value, dict):
                    for field_value in value.values():
                        if isinstance(field_value, str):
                            terms.append(field_value)
                        elif isinstance(field_value, dict) and "query" in field_value:
                            terms.append(field_value["query"])
                elif isinstance(value, dict):
                    extract_from_dict(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            extract_from_dict(item)
        
        query_body = query.get("query", {})
        if query_body:
            extract_from_dict(query_body)
        
        return terms

    async def _update_performance_history(self,
                                        index_name: str,
                                        query: Dict[str, Any],
                                        metrics: SearchMetrics,
                                        analysis: QueryAnalysis):
        """Update performance history for learning and optimization."""
        
        # Create a simplified query signature for tracking
        query_signature = self._create_query_signature(query)
        
        history_key = f"{index_name}:{query_signature}"
        
        if history_key not in self.performance_history:
            self.performance_history[history_key] = []
        
        # Store performance data point
        data_point = {
            "timestamp": datetime.now().isoformat(),
            "query_time_ms": metrics.query_time_ms,
            "total_hits": metrics.total_hits,
            "complexity": analysis.complexity.value,
            "performance_score": analysis.performance_score
        }
        
        self.performance_history[history_key].append(data_point)
        
        # Keep only last 100 entries per query type
        if len(self.performance_history[history_key]) > 100:
            self.performance_history[history_key] = self.performance_history[history_key][-100:]

    def _create_query_signature(self, query: Dict[str, Any]) -> str:
        """Create a simplified signature for query performance tracking."""
        # Extract key components for signature
        query_types = self._extract_query_types(query)
        
        # Create a normalized signature
        signature_parts = [
            f"types:{','.join(sorted(query_types))}",
            f"has_aggs:{bool(query.get('aggs'))}",
            f"has_sort:{bool(query.get('sort'))}",
            f"size:{query.get('size', 10)}"
        ]
        
        return "|".join(signature_parts)
