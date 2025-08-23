import asyncio
import pytest

from backend.services.enhanced_search_service import (
    EnhancedSearchService,
    QueryAnalysis,
    QueryComplexity,
    SearchOptimization,
)

class DummyES:
    def __init__(self):
        # minimal client with search attribute used elsewhere; not needed for optimization tests
        self.client = type('C', (), {'search': lambda *a, **k: {}})()

class DummyAI:
    pass


def make_analysis(performance_score=60, semantic_fields=None, agg_complexity=0):
    return QueryAnalysis(
        complexity=QueryComplexity.SIMPLE,
        estimated_docs=100,
        field_usage={},
        query_types=['match'],
        suggestions=[],
        performance_score=performance_score,
        semantic_fields=semantic_fields or [],
        aggregation_complexity=agg_complexity,
        index_coverage=1.0,
        optimization_opportunities=[],
    )

@pytest.mark.asyncio
async def test_optimize_for_performance_sets_size_and_timeout_and_caps_large_size():
    service = EnhancedSearchService(DummyES(), DummyAI())
    analysis = make_analysis(performance_score=80, agg_complexity=1)

    # No size -> should set to 20
    q = {}
    out = await service._optimize_for_performance(q, analysis)
    assert out['size'] == 20
    assert out['timeout'] == '10s'

    # Large size -> should be capped to 100
    q2 = {'size': 1000}
    out2 = await service._optimize_for_performance(q2, analysis)
    assert out2['size'] == 100

@pytest.mark.asyncio
async def test_optimize_for_accuracy_sets_explain_and_size():
    service = EnhancedSearchService(DummyES(), DummyAI())
    analysis = make_analysis(semantic_fields=['text_field'])

    q = {}
    out = await service._optimize_for_accuracy(q, analysis)
    assert out['size'] >= 50
    assert out['explain'] is True

@pytest.mark.asyncio
async def test_optimize_balanced_defaults_and_timeout():
    service = EnhancedSearchService(DummyES(), DummyAI())
    # performance_score low triggers filter context conversion path; we'll keep it default
    analysis = make_analysis(performance_score=40)

    q = {}
    out = await service._optimize_balanced(q, analysis)
    assert out['size'] == 50
    assert out['timeout'] == '20s'

# Edge case: if size already present and small for balanced, preserve if appropriate
@pytest.mark.asyncio
async def test_balanced_keeps_reasonable_size_if_provided():
    service = EnhancedSearchService(DummyES(), DummyAI())
    analysis = make_analysis()

    q = {'size': 60}
    out = await service._optimize_balanced(q, analysis)
    assert out['size'] == 60
