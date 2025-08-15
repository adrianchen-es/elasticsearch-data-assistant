#!/usr/bin/env python3
"""
Enhanced Mapping Error Fix Tests
Tests the improved mapping utilities with real-world scenarios.
"""

import sys
import os
import logging
import json

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from utils.mapping_utils import (
    normalize_mapping_data,
    flatten_properties,
    get_python_type,
    extract_mapping_info,
    format_mapping_summary
)


def test_mapping_normalization():
    """Test the normalize_mapping_data function with various input formats."""
    logger.info("Testing mapping normalization...")
    
    # Test case 1: Simple mapping object (should pass through unchanged)
    simple_mapping = {
        "properties": {
            "title": {"type": "text"},
            "timestamp": {"type": "date"}
        }
    }
    
    result = normalize_mapping_data(simple_mapping)
    assert result == simple_mapping
    logger.info("✓ Simple mapping normalization passed")
    
    # Test case 2: Index mapping format - should pass through as-is since it's already a dict
    index_mapping = {
        "test-index": {
            "mappings": {
                "properties": {
                    "title": {"type": "text"},
                    "timestamp": {"type": "date"}
                }
            }
        }
    }
    
    result = normalize_mapping_data(index_mapping)
    # The normalize function returns the dict as-is if it's already a dict
    assert result == index_mapping
    logger.info("✓ Index mapping format normalization passed")
    
    # Test case 3: String input (should handle gracefully)
    string_input = "invalid mapping"
    result = normalize_mapping_data(string_input)
    # Should return a dict with wrapped value
    assert isinstance(result, dict)
    assert "_raw_string" in result
    assert result["_raw_string"] == "invalid mapping"
    logger.info("✓ String input handled gracefully")
    
    # Test case 4: None input
    result = normalize_mapping_data(None)
    assert result == {}
    logger.info("✓ None input handled gracefully")
    
    logger.info("Mapping normalization tests completed successfully!")
    return True


def test_mapping_flattening():
    """Test the flatten_properties function with nested structures."""
    logger.info("Testing mapping flattening...")
    
    # Test complex nested structure
    nested_properties = {
        "user": {
            "properties": {
                "name": {"type": "text"},
                "age": {"type": "integer"},
                "profile": {
                    "properties": {
                        "bio": {"type": "text"},
                        "social": {
                            "properties": {
                                "twitter": {"type": "keyword"},
                                "linkedin": {"type": "keyword"}
                            }
                        }
                    }
                }
            }
        },
        "metadata": {
            "properties": {
                "created": {"type": "date"},
                "updated": {"type": "date"}
            }
        }
    }
    
    result = flatten_properties(nested_properties)
    
    # Verify flattened structure
    expected_fields = [
        "user.name",
        "user.age", 
        "user.profile.bio",
        "user.profile.social.twitter",
        "user.profile.social.linkedin",
        "metadata.created",
        "metadata.updated"
    ]
    
    result_fields = list(result.keys())
    
    for field in expected_fields:
        assert field in result_fields, f"Field {field} not found in flattened result"
    
    # Verify types are preserved
    assert result["user.name"] == "text"
    assert result["user.age"] == "integer"
    assert result["user.profile.social.twitter"] == "keyword"
    
    logger.info("✓ Complex mapping flattening passed")
    
    # Test empty mapping
    empty_result = flatten_properties({})
    assert empty_result == {}
    
    logger.info("Mapping flattening tests completed successfully!")
    return True


def test_python_type_conversion():
    """Test Elasticsearch to Python type conversion."""
    logger.info("Testing Python type conversion...")
    
    # Test various ES types based on the actual mapping
    test_cases = [
        ("text", "str"),
        ("keyword", "str"), 
        ("integer", "int"),
        ("long", "int"),
        ("float", "float"),
        ("double", "float"),
        ("boolean", "bool"),
        ("date", "datetime"),
        ("object", "dict"),
        ("nested", "list"),  # Updated to match actual mapping
        ("ip", "str"),
        ("unknown_type", "Any")  # Should default to 'Any'
    ]
    
    for es_type, expected_py_type in test_cases:
        result = get_python_type(es_type)
        assert result == expected_py_type, f"Expected {expected_py_type}, got {result} for ES type {es_type}"
    
    logger.info("✓ Python type conversion passed")
    return True


def test_full_mapping_extraction():
    """Test the complete mapping extraction pipeline."""
    logger.info("Testing full mapping extraction...")
    
    # Complex real-world-like mapping
    complex_mapping = {
        "test-logs-2024": {
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "message": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    },
                    "level": {"type": "keyword"},
                    "service": {
                        "properties": {
                            "name": {"type": "keyword"},
                            "version": {"type": "keyword"},
                            "environment": {"type": "keyword"}
                        }
                    },
                    "request": {
                        "properties": {
                            "method": {"type": "keyword"},
                            "url": {"type": "text"},
                            "duration_ms": {"type": "long"},
                            "headers": {
                                "properties": {
                                    "user_agent": {"type": "text"},
                                    "content_type": {"type": "keyword"}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    es_types, python_types, field_count = extract_mapping_info(complex_mapping, "test-logs-2024")
    
    # Verify we got results
    assert field_count > 0
    assert len(es_types) > 0
    assert len(python_types) > 0
    
    # Check some expected fields exist
    expected_fields = [
        "@timestamp", 
        "message",
        "service.name",
        "request.method", 
        "request.headers.user_agent"
    ]
    
    for field in expected_fields:
        assert field in es_types, f"Field {field} not found"
    
    # Verify types were converted correctly
    assert python_types["@timestamp"] == "datetime"
    assert python_types["message"] == "str"
    assert python_types["request.duration_ms"] == "int"
    
    logger.info("✓ Full mapping extraction passed")
    return True


def test_format_mapping_summary():
    """Test mapping summary formatting."""
    logger.info("Testing mapping summary formatting...")
    
    sample_es_types = {
        "title": "text",
        "count": "integer",
        "user.name": "keyword",
        "metadata.created": "date"
    }
    
    sample_python_types = {
        "title": "str",
        "count": "int", 
        "user.name": "str",
        "metadata.created": "datetime"
    }
    
    result = format_mapping_summary(sample_es_types, sample_python_types)
    
    # Should be a formatted string
    assert isinstance(result, str)
    assert "4 fields" in result
    
    # Check that fields are listed
    assert "title" in result
    assert "count" in result
    assert "user.name" in result
    
    logger.info("✓ Mapping summary formatting passed")
    return True


def test_chat_integration():
    """Test integration with chat functionality."""
    logger.info("Testing chat integration...")
    
    # Simulate the original problematic data structure
    problematic_mapping = "invalid string data"  # This was causing the original error
    
    # Our utilities should handle this gracefully
    normalized = normalize_mapping_data(problematic_mapping)
    es_types, python_types, field_count = extract_mapping_info(normalized, "test-index")
    summary = format_mapping_summary(es_types, python_types)
    
    # Should not crash and should provide meaningful output
    assert isinstance(summary, str)
    assert len(summary) > 0
    
    logger.info("✓ Chat integration test passed")
    return True


def main():
    """Run all tests."""
    logger.info("Starting Enhanced Mapping Fix Tests...")
    
    tests = [
        test_mapping_normalization,
        test_mapping_flattening, 
        test_python_type_conversion,
        test_full_mapping_extraction,
        test_format_mapping_summary,
        test_chat_integration
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            logger.info(f"✓ {test.__name__} passed")
        except Exception as e:
            logger.error(f"✗ {test.__name__} failed: {e}")
            results.append(False)
    
    passed = sum(results)
    total = len(results)
    
    logger.info(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
