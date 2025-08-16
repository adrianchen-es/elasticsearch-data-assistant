import json
import sys
import os
from fastapi.testclient import TestClient


def test_mapping_fastpath_returns_structured_mapping():
    # Ensure repo root is importable so 'backend' package and its submodules resolve
    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    # Ensure 'middleware' and other top-level backend modules import correctly by
    # adding the backend/ directory to sys.path so imports like 'middleware.xxx' work.
    backend_dir = os.path.join(repo_root, 'backend')
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Set minimal environment so AIService initialization doesn't fail during app startup
    os.environ.setdefault('AZURE_OPENAI_API_KEY', 'testkey')
    os.environ.setdefault('AZURE_OPENAI_ENDPOINT', 'https://test-openai.local')
    # Ensure telemetry is disabled in test runs to avoid network calls
    os.environ.setdefault('OTEL_TEST_MODE', '1')

    from backend.main import app

    # Use context manager so FastAPI startup events run and initialize app.state
    with TestClient(app) as client:
        # Construct a request that triggers mapping fast-path.
        body = {
            "messages": [{"role": "user", "content": "Show mapping for index X"}],
            "mode": "elasticsearch",
            "index_name": "test-index",
            "debug": True,
            "mapping_response_format": "both"
        }

        resp = client.post('/api/chat', json=body)
    assert resp.status_code == 200
    data = resp.json()
    # debug_info should include mapping_response when available
    debug = data.get('debug_info') or {}
    # mapping_response may be attached under debug_info
    mapping_resp = debug.get('mapping_response')
    # We expect either a dict with 'fields' or None (depending on server flow), but ensure key exists
    assert mapping_resp is not None, "mapping_response not present in debug_info"
    assert isinstance(mapping_resp.get('fields'), list)
