#!/usr/bin/env python3
"""
Consolidated Mapping Error Handling Tests
Tests mapping-related functionality, including error handling, normalization, flattening, and type conversion.
"""

import sys
import os
import logging
import json
from unittest.mock import MagicMock, AsyncMock
import pytest
import asyncio

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from utils.mapping_utils import (
    normalize_mapping_data,
    flatten_properties,
    extract_mapping_info,
    format_mapping_summary
)

class TestMappingErrorHandling:
    """Test handling of unexpected mapping data types"""
    
    def test_string_mapping_data(self):
        """Test handling of string mapping data instead of dict"""
        # Test case from the error message
        string_data = "this is a string instead of dict"
        normalized = normalize_mapping_data(string_data)
        assert isinstance(normalized, dict)
        assert "_raw_string" in normalized
        
    def test_none_mapping_data(self):
        """Test handling of None mapping data"""
        normalized = normalize_mapping_data(None)
        assert isinstance(normalized, dict)
        assert normalized == {}
        
    def test_empty_mapping_data(self):
        """Test handling of empty mapping data"""
        normalized = normalize_mapping_data({})
        assert isinstance(normalized, dict)
        assert normalized == {}
        
    def test_numeric_mapping_data(self):
        """Test handling of numeric mapping data"""
        normalized = normalize_mapping_data(12345)
        assert isinstance(normalized, dict)
        assert "_raw_value" in normalized
        
    def test_list_mapping_data(self):
        """Test handling of list mapping data"""
        normalized = normalize_mapping_data(["item1", "item2"])
        assert isinstance(normalized, dict)
        
    def test_json_string_mapping_data(self):
        """Test handling of JSON string mapping data"""
        json_string = '{"test": {"mappings": {"properties": {"field1": {"type": "text"}}}}}'
        normalized = normalize_mapping_data(json_string)
        assert isinstance(normalized, dict)
        assert "test" in normalized
        
    def test_pydantic_model_mapping_data(self):
        """Test handling of Pydantic model mapping data"""
        # Mock a Pydantic model
        mock_model = MagicMock()
        mock_model.model_dump.return_value = {"test": "data"}
        
        normalized = normalize_mapping_data(mock_model)
        assert isinstance(normalized, dict)
        assert normalized == {"test": "data"}

class TestExtractMappingInfo:
    """Test extract_mapping_info function with various edge cases"""
    
    def test_extract_mapping_info_with_string_data(self):
        """Test extract_mapping_info with string data that caused the original error"""
        string_mapping = "partial-.ds-elastic-cloud-logs-8-2024.12.11-000175"
        es_types, python_types, field_count = extract_mapping_info(string_mapping, "test-index")
        
        assert isinstance(es_types, dict)
        assert isinstance(python_types, dict)
        assert field_count == 0
        
    def test_extract_mapping_info_with_none(self):
        """Test extract_mapping_info with None data"""
        es_types, python_types, field_count = extract_mapping_info(None, "test-index")
        
        assert isinstance(es_types, dict)
        assert isinstance(python_types, dict)
        assert field_count == 0
        
    def test_extract_mapping_info_with_valid_mapping(self):
        """Test extract_mapping_info with valid mapping data"""
        valid_mapping = {
            "test-index": {
                "mappings": {
                    "properties": {
                        "field1": {"type": "text"},
                        "field2": {"type": "keyword"},
                        "field3": {"type": "integer"}
                    }
                }
            }
        }
        
        es_types, python_types, field_count = extract_mapping_info(valid_mapping, "test-index")
        
        assert field_count == 3
        assert es_types["field1"] == "text"
        assert es_types["field2"] == "keyword"
        assert es_types["field3"] == "integer"
        assert python_types["field1"] == "str"
        assert python_types["field2"] == "str"
        assert python_types["field3"] == "int"
        
    def test_extract_mapping_info_with_nested_properties(self):
        """Test extract_mapping_info with nested properties"""
        nested_mapping = {
            "test-index": {
                "mappings": {
                    "properties": {
                        "user": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "text"},
                                "email": {"type": "keyword"}
                            }
                        },
                        "timestamp": {"type": "date"}
                    }
                }
            }
        }
        
        es_types, python_types, field_count = extract_mapping_info(nested_mapping, "test-index")
        
        # The flattening includes the parent object field "user" plus the nested fields.
        # Expected fields: "user", "user.name", "user.email", "timestamp"
        expected_fields = {"user", "user.name", "user.email", "timestamp"}
        assert set(es_types.keys()) == expected_fields
        assert field_count == len(expected_fields)
        assert python_types["user.name"] == "str"
        assert python_types["timestamp"] == "datetime"
        
    def test_extract_mapping_info_with_malformed_index_mapping(self):
        """Test extract_mapping_info with malformed index mapping"""
        malformed_mapping = {
            "test-index": "this should be a dict but it's a string"
        }
        
        es_types, python_types, field_count = extract_mapping_info(malformed_mapping, "test-index")
        
        assert isinstance(es_types, dict)
        assert isinstance(python_types, dict)
        assert field_count == 0

class TestFlattenProperties:
    """Test flatten_properties function"""
    
    def test_flatten_simple_properties(self):
        """Test flattening simple properties"""
        properties = {
            "field1": {"type": "text"},
            "field2": {"type": "keyword"}
        }
        
        flattened = flatten_properties(properties)
        assert flattened == {"field1": "text", "field2": "keyword"}
        
    def test_flatten_nested_properties(self):
        """Test flattening nested properties"""
        properties = {
            "user": {
                "type": "object",
                "properties": {
                    "name": {"type": "text"},
                    "profile": {
                        "type": "object",
                        "properties": {
                            "age": {"type": "integer"}
                        }
                    }
                }
            }
        }
        
        flattened = flatten_properties(properties)
        assert "user.name" in flattened
        assert "user.profile.age" in flattened
        assert flattened["user.name"] == "text"
        assert flattened["user.profile.age"] == "integer"
        
    def test_flatten_properties_with_invalid_field_def(self):
        """Test flattening properties with invalid field definition"""
        properties = {
            "valid_field": {"type": "text"},
            "invalid_field": "this should be a dict"
        }
        
        flattened = flatten_properties(properties)
        # Should only include valid fields
        assert "valid_field" in flattened
        assert "invalid_field" not in flattened

class TestFormatMappingSummary:
    """Test format_mapping_summary function"""
    
    def test_format_empty_mapping_summary(self):
        """Test formatting empty mapping summary"""
        summary = format_mapping_summary({}, {})
        assert "No field properties found" in summary
        
    def test_format_mapping_summary_with_fields(self):
        """Test formatting mapping summary with fields"""
        es_types = {"field1": "text", "field2": "keyword"}
        python_types = {"field1": "str", "field2": "str"}
        
        summary = format_mapping_summary(es_types, python_types)
        assert "2 fields" in summary
        assert "field1" in summary
        assert "field2" in summary

class TestMappingIntegration:
    """Integration tests for mapping functionality"""
    
    def test_end_to_end_mapping_processing(self):
        """Test complete mapping processing pipeline"""
        # Simulate various types of mapping data that could cause issues
        test_cases = [
            "string_data",
            None,
            {"invalid": "structure"},
            {
                "test-index": {
                    "mappings": {
                        "properties": {
                            "field1": {"type": "text"},
                            "field2": {"type": "date"}
                        }
                    }
                }
            }
        ]
        
        for mapping_data in test_cases:
            # Normalize the data
            normalized = normalize_mapping_data(mapping_data)
            assert isinstance(normalized, dict)
            
            # Extract mapping info
            es_types, python_types, field_count = extract_mapping_info(normalized, "test-index")
            assert isinstance(es_types, dict)
            assert isinstance(python_types, dict)
            assert isinstance(field_count, int)
            
            # Format summary
            summary = format_mapping_summary(es_types, python_types)
            assert isinstance(summary, str)

# Async tests for route handlers
class TestAsyncMappingHandling:
    """Test async mapping handling in routes"""
    
    @pytest.mark.asyncio
    async def test_chat_route_mapping_error_handling(self):
        """Test that chat route properly handles mapping errors"""
        # This would normally test the actual chat route, but since we can't easily
        # import it due to dependencies, we'll test the logic components
        
        # Test the normalize and extract functions with problematic data
        problematic_data = "partial-.ds-elastic-cloud-logs-8-2024.12.11-000175"
        
        # This should not raise an exception
        normalized = normalize_mapping_data(problematic_data)
        es_types, python_types, field_count = extract_mapping_info(normalized, "test-index")
        
        assert isinstance(es_types, dict)
        assert isinstance(python_types, dict)
        assert field_count == 0
        
    @pytest.mark.asyncio
    async def test_query_route_mapping_error_handling(self):
        """Test that query route properly handles mapping errors"""
        # Similar to above, test the components used by query route
        
        # Test various problematic mapping formats
        test_cases = [
            "string_instead_of_dict",
            12345,
            None,
            [],
            {"malformed": "structure"}
        ]
        
        for test_data in test_cases:
            # This should not raise an exception
            normalized = normalize_mapping_data(test_data)
            es_types, python_types, field_count = extract_mapping_info(normalized, "test-index")
            
            assert isinstance(es_types, dict)
            assert isinstance(python_types, dict)
            assert isinstance(field_count, int)

if __name__ == "__main__":
    pytest.main([__file__])
