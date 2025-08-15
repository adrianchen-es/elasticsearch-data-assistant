#!/usr/bin/env python3
"""
Lightweight consolidated smoke tests to quickly surface obvious issues without async test plugins.
Run these with: pytest test/test_consolidated_smoke.py -q
"""
import sys
import os
import logging

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from utils.mapping_utils import (
    normalize_mapping_data,
    flatten_properties,
    extract_mapping_info,
    format_mapping_summary,
    get_python_type,
)


def test_imports_work():
    """Sanity: key utilities import correctly."""
    assert callable(normalize_mapping_data)
    assert callable(flatten_properties)
    assert callable(extract_mapping_info)
    assert callable(format_mapping_summary)
    assert callable(get_python_type)


def test_normalize_mapping_various_types():
    """Verify normalize_mapping_data handles common inputs without raising."""
    assert isinstance(normalize_mapping_data("this is a string"), dict)
    assert normalize_mapping_data(None) == {}
    assert isinstance(normalize_mapping_data(12345), dict)
    assert isinstance(normalize_mapping_data(["a", "b"]), dict)

    json_string = '{"idx": {"mappings": {"properties": {"f1": {"type": "text"}}}}}'
    parsed = normalize_mapping_data(json_string)
    assert isinstance(parsed, dict)
    # Either top-level index name or immediate mappings must be present
    assert parsed != {}  


def test_flatten_and_extract():
    props = {
        "simple": {"type": "text"},
        "nested": {"properties": {"inner": {"type": "keyword"}}}
    }
    flat = flatten_properties(props)
    assert "simple" in flat
    assert "nested.inner" in flat

    mapping = {"test-index": {"mappings": {"properties": {"a": {"type": "text"}, "b": {"type": "integer"}}}}}
    es_types, py_types, count = extract_mapping_info(mapping, "test-index")
    assert count == 2
    assert es_types.get("a") == "text"
    assert py_types.get("a") == get_python_type("text")


def test_format_mapping_summary_returns_string():
    es_types = {"a": "text", "b": "keyword"}
    py_types = {k: get_python_type(v) for k, v in es_types.items()}
    summary = format_mapping_summary(es_types, py_types, max_fields=10)
    assert isinstance(summary, str)
    assert "fields" in summary.lower() or "index has" in summary.lower()
