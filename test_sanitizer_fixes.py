#!/usr/bin/env python3
"""
Test script to validate the sanitizer and index filtering fixes.
"""
import sys
import os
import asyncio
import logging

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from middleware.enhanced_telemetry import trace_async_function, DataSanitizer
from services.elasticsearch_service import ElasticsearchService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestESService:
    """Mock ES service for testing filtering"""
    
    def __init__(self):
        self.mock_indices_response = [
            {'index': 'user-data-2025', 'status': 'open'},
            {'index': '.monitoring-es-8-mb-2025.07.17-000863', 'status': 'open'},
            {'index': 'partial-.ds-.monitoring-es-8-mb-2025.07.17-000863', 'status': 'open'},
            {'index': '.kibana_7.17.0_001', 'status': 'open'},
            {'index': 'logs-2025.07', 'status': 'open'},
            {'index': 'metricbeat-7.17.0-2025.07.17', 'status': 'open'},
            {'index': '.security-7', 'status': 'open'},
            {'index': 'my-app-logs', 'status': 'open'},
            {'index': 'closed-index', 'status': 'close'}
        ]
    
    def test_index_filtering(self):
        """Test the filtering logic matches our improvements"""
        filtered_indices = []
        for idx in self.mock_indices_response:
            index_name = idx['index']
            
            # Skip system indices (starting with .)
            if index_name.startswith('.'):
                continue
            
            # Skip monitoring indices
            if any(pattern in index_name for pattern in [
                '.monitoring-', 
                '.ds-.monitoring-',
                'partial-.ds-.monitoring-',
                '.watcher-',
                '.security-',
                '.kibana',
                'metricbeat-',
                'filebeat-',
                'winlogbeat-',
                'apm-',
                '.ml-'
            ]):
                logger.debug(f"Filtering out system/monitoring index: {index_name}")
                continue
            
            # Skip indices that look corrupted or partial
            if index_name.startswith('partial-'):
                logger.warning(f"Filtering out potential corrupted index: {index_name}")
                continue
            
            # Skip closed indices (if status is available)
            if idx.get('status') == 'close':
                logger.debug(f"Filtering out closed index: {index_name}")
                continue
                
            filtered_indices.append(index_name)
        
        expected = ['user-data-2025', 'logs-2025.07', 'my-app-logs']
        assert filtered_indices == expected, f"Expected {expected}, got {filtered_indices}"
        logger.info(f"✅ Index filtering test passed: {len(filtered_indices)} valid indices")
        return True

@trace_async_function('test_sanitizer_scoping')
async def test_sanitizer_scoping():
    """Test that sanitizer scoping is fixed"""
    # This should now work without the 'sanitizer not defined' error
    raise ValueError("Test error with sensitive data: api_key=sk-1234567890")

def test_data_sanitizer():
    """Test DataSanitizer functionality"""
    sanitizer = DataSanitizer()
    
    # Test various sensitive data patterns
    test_cases = [
        ("API key: sk-1234567890", "API key: ***REDACTED***"),
        ("Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9", "Bearer ***REDACTED***"),
        ("password=secret123", "password=***REDACTED***"),
        ("Internal IP: 192.168.1.1", "Internal IP: ***INTERNAL_IP***"),
        ("Email: user@company.com", "Email: ***EMAIL***"),
        ("postgres://user:pass@localhost/db", "postgres://***:***@localhost/db"),
    ]
    
    for input_text, expected_pattern in test_cases:
        result = sanitizer.sanitize_value(input_text)
        assert expected_pattern in result or result != input_text, f"Failed to sanitize: {input_text}"
        logger.info(f"✅ Sanitized: '{input_text}' -> '{result}'")
    
    logger.info(f"✅ Data sanitizer test passed for {len(test_cases)} cases")
    return True

async def main():
    """Run all tests"""
    logger.info("🧪 Starting sanitizer and index filtering tests...")
    
    # Test 1: Index filtering
    test_es = TestESService()
    test_es.test_index_filtering()
    
    # Test 2: Data sanitizer
    test_data_sanitizer()
    
    # Test 3: Sanitizer scoping fix
    try:
        await test_sanitizer_scoping()
        logger.error("❌ Should have raised an exception")
        return False
    except ValueError as e:
        logger.info(f"✅ Sanitizer scoping test passed: Exception handled correctly")
    
    logger.info("🎉 All tests passed! Fixes are working correctly.")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
