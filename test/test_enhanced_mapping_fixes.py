#!/usr/bin/env python3
"""
Enhanced Mapping Error Fix Tests
Tests the improved mapping utilities with real-world scenarios.
"""

import sys
import os
import logging
import json
from unittest.mock import MagicMock, AsyncMock, patch

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from utils.mapping_utils import (
    normalize_mapping_data,
    flatten_properties,
    convert_es_type_to_python,
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
    
    # Test case 2: Index mapping format
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
    
    expected = {
        "properties": {
            "title": {"type": "text"},
            "timestamp": {"type": "date"}
        }
    }
    
    result = normalize_mapping_data(index_mapping)
    assert result == expected
    logger.info("✓ Index mapping format normalization passed")
    
    # Test case 3: String input (should handle gracefully)
    string_input = "invalid mapping"
    result = normalize_mapping_data(string_input)
    assert result == {}
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
    nested_mapping = {
        "properties": {
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
    }
    
    result = flatten_properties(nested_mapping)
    
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
    assert result["user.name"]["type"] == "text"
    assert result["user.age"]["type"] == "integer"
    assert result["user.profile.social.twitter"]["type"] == "keyword"
    
    logger.info("✓ Complex mapping flattening passed")
    
    # Test empty mapping
    empty_result = flatten_properties({})
    assert empty_result == {}
    
    logger.info("Mapping flattening tests completed successfully!")
    return True

async def test_python_type_conversion():
    """Test Elasticsearch to Python type conversion"""
    try:
        from utils.mapping_utils import get_python_type
        
        type_mappings = [
            ("text", "str"),
            ("keyword", "str"),
            ("long", "int"),
            ("integer", "int"),
            ("double", "float"),
            ("float", "float"),
            ("date", "datetime"),
            ("boolean", "bool"),
            ("object", "dict"),
            ("nested", "list"),
            ("unknown_type", "Any")
        ]
        
        for es_type, expected_python_type in type_mappings:
            result = get_python_type(es_type)
            assert result == expected_python_type, f"Expected {expected_python_type} for {es_type}, got {result}"
            
        logger.info("✅ All type conversions correct")
        return True
        
    except Exception as e:
        logger.error(f"❌ Type conversion test failed: {e}")
        return False

async def test_full_mapping_extraction():
    """Test full mapping extraction with real-world data"""
    try:
        from utils.mapping_utils import extract_mapping_info
        
        # Simulate the problematic mapping from the original error
        problematic_mapping = {
            'risk-score.risk-score-latest-default': {
                'mappings': {
                    'dynamic': 'false',
                    'properties': {
                        '@timestamp': {'type': 'date'},
                        'event': {
                            'properties': {
                                'ingested': {'type': 'date'}
                            }
                        },
                        'host': {
                            'properties': {
                                'name': {'type': 'keyword'},
                                'risk': {
                                    'properties': {
                                        'calculated_level': {'type': 'keyword'},
                                        'calculated_score': {'type': 'float'},
                                        'calculated_score_norm': {'type': 'float'},
                                        'inputs': {
                                            'properties': {
                                                'category': {'type': 'keyword'},
                                                'risk_score': {'type': 'float'},
                                                'timestamp': {'type': 'date'}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        es_types, python_types, field_count = extract_mapping_info(
            problematic_mapping, 
            'risk-score.risk-score-latest-default'
        )
        
        # Verify we got the expected fields
        expected_fields = [
            '@timestamp',
            'event.ingested',
            'host.name', 
            'host.risk.calculated_level',
            'host.risk.calculated_score',
            'host.risk.calculated_score_norm',
            'host.risk.inputs.category',
            'host.risk.inputs.risk_score',
            'host.risk.inputs.timestamp'
        ]
        
        assert field_count == len(expected_fields), f"Expected {len(expected_fields)} fields, got {field_count}"
        
        for field in expected_fields:
            assert field in es_types, f"Field {field} not found in ES types"
            assert field in python_types, f"Field {field} not found in Python types"
        
        # Verify specific type conversions
        assert es_types['@timestamp'] == 'date'
        assert python_types['@timestamp'] == 'datetime'
        assert es_types['host.risk.calculated_score'] == 'float'
        assert python_types['host.risk.calculated_score'] == 'float'
        
        logger.info(f"✅ Extracted {field_count} fields with correct types")
        return True
        
    except Exception as e:
        logger.error(f"❌ Full mapping extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_format_mapping_summary():
    """Test mapping summary formatting"""
    try:
        from utils.mapping_utils import format_mapping_summary
        
        es_types = {
            'field1': 'text',
            'field2': 'keyword', 
            'field3': 'date',
            'field4': 'float'
        }
        
        python_types = {
            'field1': 'str',
            'field2': 'str',
            'field3': 'datetime', 
            'field4': 'float'
        }
        
        summary = format_mapping_summary(es_types, python_types)
        
        assert 'has 4 fields' in summary
        assert 'field1 (str)' in summary
        assert 'field3 (datetime)' in summary
        
        logger.info("✅ Mapping summary formatted correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Mapping summary test failed: {e}")
        return False

async def test_chat_integration():
    """Test the full integration with chat router"""
    try:
        from utils.mapping_utils import normalize_mapping_data, extract_mapping_info, format_mapping_summary
        
        # Simulate the chat router workflow
        raw_mapping = '{"risk-score.risk-score-latest-default": {"mappings": {"properties": {"@timestamp": {"type": "date"}, "host": {"properties": {"name": {"type": "keyword"}}}}}}}'
        
        # Step 1: Normalize
        mapping_dict = normalize_mapping_data(raw_mapping)
        assert isinstance(mapping_dict, dict)
        
        # Step 2: Extract info
        es_types, python_types, field_count = extract_mapping_info(
            mapping_dict, 
            'risk-score.risk-score-latest-default'
        )
        assert field_count > 0
        
        # Step 3: Format summary
        summary = format_mapping_summary(es_types, python_types)
        assert 'has' in summary and 'fields' in summary
        
        logger.info("✅ Full chat integration workflow works")
        return True
        
    except Exception as e:
        logger.error(f"❌ Chat integration test failed: {e}")
        return False

async def main():
    """Run enhanced mapping fix tests"""
    logger.info("🧪 Starting enhanced mapping fix tests...")
    
    tests = [
        ("Mapping Normalization", test_mapping_normalization),
        ("Mapping Flattening", test_mapping_flattening),
        ("Python Type Conversion", test_python_type_conversion),
        ("Full Mapping Extraction", test_full_mapping_extraction),
        ("Format Mapping Summary", test_format_mapping_summary),
        ("Chat Integration", test_chat_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running {test_name}...")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n📊 Test Results Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All enhanced mapping fix tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
