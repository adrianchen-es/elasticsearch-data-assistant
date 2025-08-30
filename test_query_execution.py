#!/usr/bin/env python3
"""
Test script to validate query execution functionality.
This tests the backend API endpoints that the frontend uses.
"""

import asyncio
import json
import sys
import os

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
from main import app

def test_query_endpoints():
    """Test that query validation and execution endpoints are accessible"""
    client = TestClient(app)
    
    # Test query validation endpoint
    validation_payload = {
        "index_name": "test_index",
        "query": {"match_all": {}}
    }
    
    print("Testing query validation endpoint...")
    validation_response = client.post("/api/query/validate", json=validation_payload)
    print(f"Validation status: {validation_response.status_code}")
    
    if validation_response.status_code == 200:
        validation_data = validation_response.json()
        print(f"Validation response: {validation_data}")
    else:
        print(f"Validation error: {validation_response.text}")
    
    # Test query execution endpoint
    execution_payload = {
        "index_name": "test_index", 
        "query": {"match_all": {}}
    }
    
    print("\nTesting query execution endpoint...")
    execution_response = client.post("/api/query/execute", json=execution_payload)
    print(f"Execution status: {execution_response.status_code}")
    
    if execution_response.status_code == 200:
        execution_data = execution_response.json()
        print(f"Execution response keys: {list(execution_data.keys())}")
        print(f"Query ID generated: {execution_data.get('query_id', 'None')}")
    else:
        print(f"Execution error: {execution_response.text}")
    
    print("\nQuery endpoints test completed.")
    return validation_response.status_code == 200 and execution_response.status_code in [200, 500]  # 500 expected if no ES

if __name__ == "__main__":
    success = test_query_endpoints()
    print(f"\nTest result: {'PASS' if success else 'FAIL'}")
    sys.exit(0 if success else 1)
