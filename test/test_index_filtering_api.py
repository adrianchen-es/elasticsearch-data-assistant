#!/usr/bin/env python3
"""
Test the new index filtering API endpoints
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from routers.providers import router, IndexFilterSettings
from config.settings import settings


class TestIndexFilteringAPI:
    """Test the new index filtering API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the providers router"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_get_index_filter_settings(self, client):
        """Test getting current index filter settings"""
        response = client.get("/index-filter-settings")
        assert response.status_code == 200
        
        data = response.json()
        assert "filter_system_indices" in data
        assert "filter_monitoring_indices" in data
        assert "filter_closed_indices" in data
        assert "show_data_streams" in data
        
        # Test that default values are returned
        assert isinstance(data["filter_system_indices"], bool)
        assert isinstance(data["filter_monitoring_indices"], bool)
        assert isinstance(data["filter_closed_indices"], bool)
        assert isinstance(data["show_data_streams"], bool)

    def test_update_index_filter_settings(self, client):
        """Test updating index filter settings"""
        # Get current settings first
        original_response = client.get("/index-filter-settings")
        original_settings = original_response.json()
        
        # Update settings
        new_settings = {
            "filter_system_indices": False,
            "filter_monitoring_indices": False,
            "filter_closed_indices": False,
            "show_data_streams": False
        }
        
        response = client.put("/index-filter-settings", json=new_settings)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "settings" in data
        
        # Verify settings were updated
        updated_response = client.get("/index-filter-settings")
        updated_settings = updated_response.json()
        
        assert updated_settings["filter_system_indices"] == False
        assert updated_settings["filter_monitoring_indices"] == False
        assert updated_settings["filter_closed_indices"] == False
        assert updated_settings["show_data_streams"] == False
        
        # Restore original settings
        client.put("/index-filter-settings", json=original_settings)

    def test_get_elasticsearch_settings(self, client):
        """Test getting Elasticsearch configuration and filtering settings"""
        response = client.get("/elasticsearch-settings")
        assert response.status_code == 200
        
        data = response.json()
        assert "elasticsearch_url" in data
        assert "has_api_key" in data
        assert "filtering" in data
        assert "cache" in data
        
        # Check filtering settings structure
        filtering = data["filtering"]
        assert "filter_system_indices" in filtering
        assert "filter_monitoring_indices" in filtering
        assert "filter_closed_indices" in filtering
        assert "show_data_streams" in filtering
        
        # Check cache settings structure
        cache = data["cache"]
        assert "mapping_cache_interval_minutes" in cache
        
        # Verify data types
        assert isinstance(data["has_api_key"], bool)
        assert isinstance(filtering["filter_system_indices"], bool)
        assert isinstance(cache["mapping_cache_interval_minutes"], (int, float))

    def test_index_filter_settings_model_validation(self):
        """Test the IndexFilterSettings Pydantic model validation"""
        # Test valid settings
        valid_settings = IndexFilterSettings(
            filter_system_indices=True,
            filter_monitoring_indices=False,
            filter_closed_indices=True,
            show_data_streams=False
        )
        
        assert valid_settings.filter_system_indices == True
        assert valid_settings.filter_monitoring_indices == False
        assert valid_settings.filter_closed_indices == True
        assert valid_settings.show_data_streams == False
        
        # Test default values
        default_settings = IndexFilterSettings()
        assert default_settings.filter_system_indices == True
        assert default_settings.filter_monitoring_indices == True
        assert default_settings.filter_closed_indices == True
        assert default_settings.show_data_streams == True

    def test_index_filter_settings_integration(self, client):
        """Test end-to-end integration of filtering settings"""
        # Store original settings
        original_response = client.get("/index-filter-settings")
        original_settings = original_response.json()
        
        try:
            # Test various combinations
            test_combinations = [
                {
                    "filter_system_indices": True,
                    "filter_monitoring_indices": True,
                    "filter_closed_indices": True,
                    "show_data_streams": True
                },
                {
                    "filter_system_indices": False,
                    "filter_monitoring_indices": False,
                    "filter_closed_indices": False,
                    "show_data_streams": False
                },
                {
                    "filter_system_indices": True,
                    "filter_monitoring_indices": False,
                    "filter_closed_indices": True,
                    "show_data_streams": False
                }
            ]
            
            for test_settings in test_combinations:
                # Update settings
                response = client.put("/index-filter-settings", json=test_settings)
                assert response.status_code == 200
                
                # Verify they were applied
                verify_response = client.get("/index-filter-settings")
                verify_data = verify_response.json()
                
                for key, expected_value in test_settings.items():
                    assert verify_data[key] == expected_value, f"Setting {key} was not updated correctly"
                
                # Verify they appear in elasticsearch settings too
                es_response = client.get("/elasticsearch-settings")
                es_data = es_response.json()
                
                for key, expected_value in test_settings.items():
                    assert es_data["filtering"][key] == expected_value, f"Setting {key} not reflected in ES settings"
                    
        finally:
            # Always restore original settings
            client.put("/index-filter-settings", json=original_settings)


def run_tests():
    """Run all API endpoint tests"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
