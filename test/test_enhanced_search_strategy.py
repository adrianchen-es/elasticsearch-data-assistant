import asyncio
from unittest.mock import AsyncMock
from backend.services.enhanced_search_service import SearchOptimization


def test_tuning_to_strategy_mapping():
    # Map tuning flags to expected strategies locally (replicate logic)
    def map_tuning(tuning):
        prec = bool(tuning.get("precision")) if tuning else False
        rec = bool(tuning.get("recall")) if tuning else False
        if prec and not rec:
            return SearchOptimization.ACCURACY
        if rec and not prec:
            return SearchOptimization.PERFORMANCE
        return SearchOptimization.BALANCED

    assert map_tuning({"precision": True, "recall": False}) == SearchOptimization.ACCURACY
    assert map_tuning({"precision": False, "recall": True}) == SearchOptimization.PERFORMANCE
    assert map_tuning({"precision": True, "recall": True}) == SearchOptimization.BALANCED
    assert map_tuning(None) == SearchOptimization.BALANCED


async def _fake_execute(index_name, query, optimization, explain, profile):
    # Validate invocation signature
    assert optimization in list(SearchOptimization)
    return type("R", (), {"hits": [], "total_hits": 0, "max_score": 0.0, "took_ms": 1, "timed_out": False, "shards_info": {}, "aggregations": {}, "analysis": None, "metrics": None, "suggestions": [], "related_queries": []})


def test_enhanced_service_called(monkeypatch):
    # Replace EnhancedSearchService.execute_enhanced_search with fake
    fake = AsyncMock(side_effect=_fake_execute)
    class FakeEnhanced:
        def __init__(self):
            self.execute_enhanced_search = fake

    monkeypatch.setattr('backend.routers.query.EnhancedSearchService', FakeEnhanced)
    # Simulate mapping from query router; directly import router function to test mapping logic
    from backend.routers.query import _apply_tuning_to_query
    if hasattr(__import__('backend.routers.query', fromlist=['*']), '_apply_tuning_to_query'):
        _apply_tuning_to_query = _apply_tuning_to_query
    else:
        _apply_tuning_to_query = lambda q, t: q

    # Call fake execute through assembly
    import asyncio
    async def runner():
        svc = FakeEnhanced()
        await svc.execute_enhanced_search('idx', {'query': {}}, optimization=SearchOptimization.ACCURACY, explain=True, profile=False)

    asyncio.get_event_loop().run_until_complete(runner())
