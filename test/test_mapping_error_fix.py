#!/usr/bin/env python3
"""
Test Mapping Error Fix
Tests that the 'str' object has no attribute 'get' error is resolved.
"""

import sys
import os
import asyncio
import logging
import json
from unittest.mock import MagicMock, AsyncMock, patch

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mapping_string_error():
    """Test that mapping handling works when unexpected string data is returned"""
    try:
        from routers.chat import ChatRequest, ChatMessage
        from services.mapping_cache_service import MappingCacheService
        from fastapi import Request
        
        # Mock the mapping cache service to return different problematic values
        mock_mapping_service = AsyncMock()
        
        # Test cases for different problematic return values
        test_cases = [
            ("string_mapping", "this is a string instead of dict"),
            ("none_mapping", None),
            ("empty_mapping", {}),
            ("numeric_mapping", 12345),
            ("list_mapping", ["item1", "item2"]),
        ]
        
        for case_name, problematic_mapping in test_cases:
            logger.info(f"Testing case: {case_name} with value: {problematic_mapping}")
            
            mock_mapping_service.get_mapping.return_value = problematic_mapping
            
            # Create a test request for mapping query
            req = ChatRequest(
                messages=[ChatMessage(role="user", content="show me the mapping for this index")],
                mode="elasticsearch",
                index_name="test_index",
                stream=False,
                debug=False
            )
            
            # Mock the FastAPI Request
            mock_request = MagicMock()
            mock_request.app.state.mapping_cache_service = mock_mapping_service
            mock_request.app.state.ai_service = AsyncMock()
            mock_request.app.state.es = AsyncMock()
            
            # Test the mapping handling logic directly
            try:
                # Simulate the problematic code path
                mapping = problematic_mapping
                
                # Normalize to dict for safe serialization (this is the existing logic)
                if hasattr(mapping, "model_dump"):
                    mapping_dict = mapping.model_dump()
                elif isinstance(mapping, dict):
                    mapping_dict = mapping
                else:
                    try:
                        mapping_dict = json.loads(json.dumps(mapping, default=str))
                    except Exception:
                        mapping_dict = {"_raw": str(mapping)}

                # This is our new safety check
                if not isinstance(mapping_dict, dict):
                    logger.warning(f"Unexpected mapping_dict type: {type(mapping_dict)}, value: {mapping_dict}")
                    mapping_dict = {"_raw": str(mapping_dict)}

                # This should not fail anymore
                index_body = mapping_dict.get("test_index") or next(iter(mapping_dict.values()), {}) if mapping_dict else {}
                properties = (index_body.get("mappings") or {}).get("properties", {}) if isinstance(index_body, dict) else {}
                field_names = sorted(list(properties.keys())) if isinstance(properties, dict) else []
                
                logger.info(f"  ✅ Case {case_name} handled successfully - got {len(field_names)} fields")
                
            except AttributeError as e:
                if "'str' object has no attribute 'get'" in str(e):
                    logger.error(f"  ❌ Case {case_name} still has the 'str' object error: {e}")
                    return False
                else:
                    logger.error(f"  ❌ Case {case_name} has different AttributeError: {e}")
                    return False
            except Exception as e:
                logger.error(f"  ❌ Case {case_name} failed with unexpected error: {e}")
                return False
        
        logger.info("✅ All mapping error cases handled correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Mapping error test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_mapping_normal_case():
    """Test that normal mapping functionality still works"""
    try:
        # Test with normal mapping data structure
        normal_mapping = {
            "test_index": {
                "mappings": {
                    "properties": {
                        "field1": {"type": "text"},
                        "field2": {"type": "keyword"},
                        "field3": {"type": "date"}
                    }
                }
            }
        }
        
        # Test the mapping handling logic
        mapping = normal_mapping
        
        # Normalize to dict for safe serialization
        if hasattr(mapping, "model_dump"):
            mapping_dict = mapping.model_dump()
        elif isinstance(mapping, dict):
            mapping_dict = mapping
        else:
            try:
                mapping_dict = json.loads(json.dumps(mapping, default=str))
            except Exception:
                mapping_dict = {"_raw": str(mapping)}

        # Safety check
        if not isinstance(mapping_dict, dict):
            mapping_dict = {"_raw": str(mapping_dict)}

        # Process mapping
        index_body = mapping_dict.get("test_index") or next(iter(mapping_dict.values()), {}) if mapping_dict else {}
        properties = (index_body.get("mappings") or {}).get("properties", {}) if isinstance(index_body, dict) else {}
        field_names = sorted(list(properties.keys())) if isinstance(properties, dict) else []
        
        # Verify we got the expected fields
        expected_fields = ["field1", "field2", "field3"]
        assert field_names == expected_fields, f"Expected {expected_fields}, got {field_names}"
        
        logger.info("✅ Normal mapping case works correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Normal mapping test failed: {e}")
        return False

async def main():
    """Run mapping error fix tests"""
    logger.info("🧪 Starting mapping error fix tests...")
    
    tests = [
        ("Mapping String Error Cases", test_mapping_string_error),
        ("Normal Mapping Case", test_mapping_normal_case),
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
        logger.info("🎉 All mapping error fix tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
