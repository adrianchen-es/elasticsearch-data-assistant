# backend/services/intelligent_mode_service.py
from typing import Dict, Any, Optional, List, Tuple
import re
import logging
from dataclasses import dataclass
from enum import Enum
from opentelemetry import trace
import asyncio

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class QueryIntent(Enum):
    """Types of query intents that can be detected"""
    DATA_EXPLORATION = "data_exploration"
    SEARCH_DOCUMENTS = "search_documents" 
    ANALYTICS_AGGREGATION = "analytics_aggregation"
    SCHEMA_MAPPING = "schema_mapping"
    GENERAL_CONVERSATION = "general_conversation"
    TROUBLESHOOTING = "troubleshooting"
    TIME_SERIES_ANALYSIS = "time_series_analysis"


class DataSuitability(Enum):
    """Data suitability levels for RAG"""
    EXCELLENT = "excellent"  # Rich text content, recent data
    GOOD = "good"           # Some text content, moderate freshness
    MODERATE = "moderate"    # Limited text, older data
    POOR = "poor"           # Minimal text, very old/sparse data
    UNSUITABLE = "unsuitable"  # No relevant content


@dataclass
class ModeDetectionResult:
    """Result of intelligent mode detection"""
    suggested_mode: str  # "free", "elasticsearch", "auto"
    confidence: float    # 0.0 - 1.0
    intent: QueryIntent
    relevant_indices: List[str]
    reasoning: str
    fallback_to_free: bool = False


@dataclass
class IndexAnalysis:
    """Analysis result for an Elasticsearch index"""
    index_name: str
    content_type: str    # "documents", "logs", "metrics", "events", "mixed"
    text_field_count: int
    vector_field_count: int
    document_count: int
    last_updated: Optional[str]
    data_freshness_score: float  # 0.0 - 1.0
    content_richness_score: float  # 0.0 - 1.0
    suitability: DataSuitability
    sample_fields: List[str]


class IntelligentModeDetector:
    """Service for intelligent detection of chat mode based on query intent and data suitability"""
    
    def __init__(self, elasticsearch_service, mapping_cache_service):
        self.es_service = elasticsearch_service
        self.mapping_cache = mapping_cache_service
        
        # Query patterns for intent detection
        self.intent_patterns = {
            QueryIntent.DATA_EXPLORATION: [
                r'\b(?:show|list|what|describe|explore|browse|overview)\b.*\b(?:data|indices|index|fields|structure)\b',
                r'\b(?:what.*(?:have|available|contains?)|browse|explore)\b',
                r'\b(?:data|dataset|table)s?\s+(?:available|here|exist)\b'
            ],
            QueryIntent.SEARCH_DOCUMENTS: [
                r'\b(?:find|search|look\s+for|get|retrieve|fetch)\b.*\b(?:document|record|entry|item)\b',
                r'\b(?:where|which|that\s+(?:contain|have|include))\b',
                r'\b(?:filter|match|like|similar\s+to)\b'
            ],
            QueryIntent.ANALYTICS_AGGREGATION: [
                r'\b(?:count|sum|average|avg|total|max|min|group\s+by|aggregate)\b',
                r'\b(?:how\s+many|statistics|stats|metrics|analysis|trend)\b',
                r'\b(?:distribution|breakdown|report|dashboard)\b'
            ],
            QueryIntent.SCHEMA_MAPPING: [
                r'\b(?:schema|mapping|structure|fields?|columns?|properties)\b',
                r'\b(?:what.*fields?|field\s+types?|data\s+types?)\b',
                r'\b(?:index\s+structure|table\s+schema)\b'
            ],
            QueryIntent.TIME_SERIES_ANALYSIS: [
                r'\b(?:time|date|timestamp|over\s+time|trend|temporal)\b.*\b(?:analysis|pattern|series)\b',
                r'\b(?:last|past|recent|yesterday|today|week|month|year)\b',
                r'\b(?:timeline|history|chronological|time-based)\b'
            ],
            QueryIntent.TROUBLESHOOTING: [
                r'\b(?:error|exception|failure|problem|issue|bug|debug)\b',
                r'\b(?:why|what.*wrong|not\s+working|failed)\b',
                r'\b(?:troubleshoot|diagnose|investigate)\b'
            ]
        }
        
        # Content type indicators for index classification
        self.content_indicators = {
            "logs": [
                "log", "logs", "audit", "events", "syslog", "application", 
                "@timestamp", "level", "message", "error", "exception"
            ],
            "documents": [
                "content", "body", "text", "title", "description", "document",
                "article", "page", "post", "comment", "review"
            ],
            "metrics": [
                "metrics", "stats", "performance", "cpu", "memory", "disk",
                "network", "latency", "throughput", "gauge", "counter"
            ],
            "events": [
                "event", "action", "activity", "interaction", "click",
                "view", "purchase", "conversion", "user_id", "session"
            ]
        }
        
    async def detect_mode(
        self, 
        messages: List[Dict[str, Any]], 
        current_index: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> ModeDetectionResult:
        """Main method to detect the appropriate chat mode"""
        
        with tracer.start_as_current_span("intelligent_mode_detection") as span:
            if not messages:
                return ModeDetectionResult(
                    suggested_mode="free",
                    confidence=1.0,
                    intent=QueryIntent.GENERAL_CONVERSATION,
                    relevant_indices=[],
                    reasoning="No messages provided"
                )
            
            # Extract the latest user message
            latest_message = self._get_latest_user_message(messages)
            if not latest_message:
                return ModeDetectionResult(
                    suggested_mode="free",
                    confidence=0.8,
                    intent=QueryIntent.GENERAL_CONVERSATION,
                    relevant_indices=[],
                    reasoning="No user message found"
                )
            
            # Analyze query intent
            intent = await self._analyze_query_intent(latest_message)
            span.set_attribute("query.intent", intent.value)
            
            # If it's clearly a general conversation, use free mode
            if intent == QueryIntent.GENERAL_CONVERSATION:
                return ModeDetectionResult(
                    suggested_mode="free",
                    confidence=0.9,
                    intent=intent,
                    relevant_indices=[],
                    reasoning="Detected general conversation intent"
                )
            
            # Get available indices and analyze them
            try:
                indices_analysis = await self._analyze_available_indices()
                span.set_attribute("analysis.indices_count", len(indices_analysis))
            except Exception as e:
                logger.warning(f"Failed to analyze indices: {e}")
                return ModeDetectionResult(
                    suggested_mode="free",
                    confidence=0.7,
                    intent=intent,
                    relevant_indices=[],
                    reasoning=f"Failed to analyze indices: {e}",
                    fallback_to_free=True
                )
            
            # Find relevant indices for the query
            relevant_indices = await self._find_relevant_indices(
                latest_message, intent, indices_analysis, current_index
            )
            
            # Calculate confidence and make decision
            mode_result = await self._determine_mode(
                intent, relevant_indices, indices_analysis, latest_message
            )
            
            span.set_attributes({
                "decision.mode": mode_result.suggested_mode,
                "decision.confidence": mode_result.confidence,
                "decision.relevant_indices": len(mode_result.relevant_indices)
            })
            
            return mode_result
    
    def _get_latest_user_message(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract the latest user message content"""
        for message in reversed(messages):
            if message.get("role") == "user":
                content = message.get("content", "")
                return content if isinstance(content, str) else str(content)
        return None
    
    async def _analyze_query_intent(self, message: str) -> QueryIntent:
        """Analyze the intent of a user message"""
        message_lower = message.lower()
        intent_scores = {}
        
        # Score each intent based on pattern matches
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, message_lower, re.IGNORECASE))
                score += matches
            intent_scores[intent] = score
        
        # Find the highest scoring intent
        if not intent_scores or max(intent_scores.values()) == 0:
            return QueryIntent.GENERAL_CONVERSATION
        
        return max(intent_scores, key=intent_scores.get)
    
    async def _analyze_available_indices(self) -> List[IndexAnalysis]:
        """Analyze all available Elasticsearch indices for data suitability"""
        
        with tracer.start_as_current_span("analyze_available_indices"):
            try:
                # Get list of indices
                indices_list = await self.es_service.get_indices()
                if not indices_list:
                    return []
                
                analyses = []
                
                # Analyze each index (limit to prevent overwhelming analysis)
                for index_name in indices_list[:20]:  # Limit analysis to 20 most relevant
                    try:
                        analysis = await self._analyze_single_index(index_name)
                        if analysis:
                            analyses.append(analysis)
                    except Exception as e:
                        logger.warning(f"Failed to analyze index {index_name}: {e}")
                        continue
                
                # Sort by suitability and freshness
                analyses.sort(key=lambda x: (
                    self._suitability_to_score(x.suitability),
                    x.data_freshness_score
                ), reverse=True)
                
                return analyses
                
            except Exception as e:
                logger.error(f"Failed to analyze available indices: {e}")
                return []
    
    async def _analyze_single_index(self, index_name: str) -> Optional[IndexAnalysis]:
        """Analyze a single Elasticsearch index"""
        
        try:
            # Get mapping information
            mapping = await self.mapping_cache.get_mapping(index_name)
            if not mapping:
                return None
            
            # Analyze field types
            text_fields = []
            vector_fields = []
            all_fields = []
            
            def analyze_properties(properties, prefix=""):
                for field_name, field_def in properties.items():
                    full_name = f"{prefix}.{field_name}" if prefix else field_name
                    all_fields.append(full_name)
                    
                    field_type = field_def.get("type", "")
                    if field_type in ["text", "keyword", "wildcard"]:
                        text_fields.append(full_name)
                    elif field_type == "dense_vector":
                        vector_fields.append(full_name)
                    elif field_type == "object" and "properties" in field_def:
                        analyze_properties(field_def["properties"], full_name)
            
            properties = mapping.get("properties", {}) if mapping else {}
            analyze_properties(properties)
            
            # Get document count (basic stats)
            doc_count = await self._get_document_count(index_name)
            
            # Determine content type
            content_type = self._classify_content_type(index_name, all_fields)
            
            # Calculate scores
            content_richness_score = min(len(text_fields) / 10.0, 1.0)  # More text fields = richer content
            data_freshness_score = await self._calculate_freshness_score(index_name)
            
            # Determine overall suitability
            suitability = self._determine_suitability(
                text_fields, vector_fields, doc_count, content_richness_score, data_freshness_score
            )
            
            return IndexAnalysis(
                index_name=index_name,
                content_type=content_type,
                text_field_count=len(text_fields),
                vector_field_count=len(vector_fields),
                document_count=doc_count,
                last_updated=None,  # Could be enhanced with actual timestamp analysis
                data_freshness_score=data_freshness_score,
                content_richness_score=content_richness_score,
                suitability=suitability,
                sample_fields=all_fields[:10]  # Sample of fields for context
            )
            
        except Exception as e:
            logger.warning(f"Error analyzing index {index_name}: {e}")
            return None
    
    def _classify_content_type(self, index_name: str, fields: List[str]) -> str:
        """Classify the type of content in an index"""
        name_lower = index_name.lower()
        fields_lower = [f.lower() for f in fields]
        
        scores = {}
        for content_type, indicators in self.content_indicators.items():
            score = 0
            # Check index name
            score += sum(1 for indicator in indicators if indicator in name_lower)
            # Check field names
            score += sum(1 for field in fields_lower 
                        for indicator in indicators if indicator in field)
            scores[content_type] = score
        
        if not scores or max(scores.values()) == 0:
            return "mixed"
        
        return max(scores, key=scores.get)
    
    async def _get_document_count(self, index_name: str) -> int:
        """Get approximate document count for an index"""
        try:
            stats = await self.es_service.client.indices.stats(index=index_name)
            return stats.get("indices", {}).get(index_name, {}).get("total", {}).get("docs", {}).get("count", 0)
        except Exception:
            return 0
    
    async def _calculate_freshness_score(self, index_name: str) -> float:
        """Calculate how fresh/recent the data in an index is"""
        try:
            # Simple heuristic: check if there are recent documents
            query = {
                "query": {
                    "range": {
                        "@timestamp": {
                            "gte": "now-7d"
                        }
                    }
                },
                "size": 0
            }
            
            result = await self.es_service.search(index_name, query)
            recent_count = result.get("hits", {}).get("total", {}).get("value", 0)
            
            if recent_count > 1000:
                return 1.0  # Very fresh
            elif recent_count > 100:
                return 0.8  # Moderately fresh
            elif recent_count > 10:
                return 0.6  # Somewhat fresh
            elif recent_count > 0:
                return 0.4  # Some recent activity
            else:
                return 0.2  # Likely old data
                
        except Exception:
            # If @timestamp field doesn't exist or query fails, assume moderate freshness
            return 0.5
    
    def _determine_suitability(
        self, 
        text_fields: List[str], 
        vector_fields: List[str], 
        doc_count: int,
        content_richness: float,
        data_freshness: float
    ) -> DataSuitability:
        """Determine overall data suitability for RAG"""
        
        # No data = unsuitable
        if doc_count == 0:
            return DataSuitability.UNSUITABLE
        
        # Very few text fields and no vectors = poor for RAG
        if len(text_fields) < 2 and len(vector_fields) == 0:
            return DataSuitability.POOR
        
        # Calculate composite score
        composite_score = (
            min(len(text_fields) / 5.0, 1.0) * 0.4 +  # Text field availability
            min(len(vector_fields) / 2.0, 1.0) * 0.2 +  # Vector field bonus
            min(doc_count / 10000.0, 1.0) * 0.2 +      # Document volume
            content_richness * 0.1 +                    # Content richness
            data_freshness * 0.1                        # Data freshness
        )
        
        if composite_score >= 0.8:
            return DataSuitability.EXCELLENT
        elif composite_score >= 0.6:
            return DataSuitability.GOOD
        elif composite_score >= 0.4:
            return DataSuitability.MODERATE
        else:
            return DataSuitability.POOR
    
    async def _find_relevant_indices(
        self, 
        message: str, 
        intent: QueryIntent, 
        indices_analysis: List[IndexAnalysis],
        current_index: Optional[str]
    ) -> List[str]:
        """Find indices most relevant to the user's query"""
        
        message_lower = message.lower()
        relevant = []
        
        # If user specified an index or we have a current index context, prioritize it
        if current_index:
            if any(idx.index_name == current_index for idx in indices_analysis):
                relevant.append(current_index)
        
        # Look for explicit index mentions in the message
        for analysis in indices_analysis:
            if analysis.index_name.lower() in message_lower:
                if analysis.index_name not in relevant:
                    relevant.append(analysis.index_name)
        
        # Intent-based relevance scoring
        intent_preferences = {
            QueryIntent.SEARCH_DOCUMENTS: lambda a: a.content_type == "documents",
            QueryIntent.ANALYTICS_AGGREGATION: lambda a: a.content_type in ["logs", "metrics", "events"],
            QueryIntent.TIME_SERIES_ANALYSIS: lambda a: a.content_type in ["logs", "metrics"],
            QueryIntent.TROUBLESHOOTING: lambda a: a.content_type == "logs",
            QueryIntent.DATA_EXPLORATION: lambda a: True,  # Any index is relevant for exploration
        }
        
        # Score indices based on intent and suitability
        scored_indices = []
        for analysis in indices_analysis:
            if analysis.index_name in relevant:
                continue  # Already included
            
            score = self._suitability_to_score(analysis.suitability)
            
            # Apply intent preferences
            if intent in intent_preferences:
                if intent_preferences[intent](analysis):
                    score += 0.3
            
            # Boost fresh, rich data
            score += analysis.data_freshness_score * 0.1
            score += analysis.content_richness_score * 0.1
            
            scored_indices.append((analysis.index_name, score))
        
        # Sort by score and take top candidates
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        for index_name, score in scored_indices[:5]:  # Limit to top 5
            if score > 0.3:  # Minimum relevance threshold
                relevant.append(index_name)
        
        return relevant
    
    async def _determine_mode(
        self, 
        intent: QueryIntent, 
        relevant_indices: List[str],
        indices_analysis: List[IndexAnalysis],
        message: str
    ) -> ModeDetectionResult:
        """Make the final determination of chat mode"""
        
        # No relevant indices found
        if not relevant_indices:
            return ModeDetectionResult(
                suggested_mode="free",
                confidence=0.8,
                intent=intent,
                relevant_indices=[],
                reasoning="No suitable Elasticsearch indices found for this query",
                fallback_to_free=True
            )
        
        # Find best suitable index
        best_suitability = DataSuitability.UNSUITABLE
        for analysis in indices_analysis:
            if analysis.index_name in relevant_indices:
                if self._suitability_to_score(analysis.suitability) > self._suitability_to_score(best_suitability):
                    best_suitability = analysis.suitability
        
        # Mode decision logic
        if best_suitability in [DataSuitability.EXCELLENT, DataSuitability.GOOD]:
            confidence = 0.9 if best_suitability == DataSuitability.EXCELLENT else 0.8
            return ModeDetectionResult(
                suggested_mode="elasticsearch",
                confidence=confidence,
                intent=intent,
                relevant_indices=relevant_indices,
                reasoning=f"Found {best_suitability.value} data quality in relevant indices"
            )
        elif best_suitability == DataSuitability.MODERATE:
            return ModeDetectionResult(
                suggested_mode="elasticsearch",
                confidence=0.6,
                intent=intent,
                relevant_indices=relevant_indices,
                reasoning="Found moderately suitable data - will attempt Elasticsearch mode with fallback"
            )
        else:
            return ModeDetectionResult(
                suggested_mode="free",
                confidence=0.7,
                intent=intent,
                relevant_indices=relevant_indices,
                reasoning="Available data quality is poor for RAG, falling back to free chat",
                fallback_to_free=True
            )
    
    def _suitability_to_score(self, suitability: DataSuitability) -> float:
        """Convert suitability enum to numeric score"""
        return {
            DataSuitability.EXCELLENT: 1.0,
            DataSuitability.GOOD: 0.8,
            DataSuitability.MODERATE: 0.6,
            DataSuitability.POOR: 0.4,
            DataSuitability.UNSUITABLE: 0.0
        }[suitability]