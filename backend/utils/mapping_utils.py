"""
Mapping utilities for flattening Elasticsearch mappings and type conversion.
"""
import json
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Elasticsearch to Python type mapping
ES_TO_PYTHON_TYPES = {
    'text': 'str',
    'keyword': 'str', 
    'long': 'int',
    'integer': 'int',
    'short': 'int',
    'byte': 'int',
    'double': 'float',
    'float': 'float',
    'half_float': 'float',
    'scaled_float': 'float',
    'date': 'datetime',
    'boolean': 'bool',
    'binary': 'bytes',
    'ip': 'str',
    'geo_point': 'dict',
    'geo_shape': 'dict',
    'object': 'dict',
    'nested': 'list',
    'completion': 'str',
    'token_count': 'int',
    'murmur3': 'str',
    'annotated-text': 'str',
    'percolator': 'dict',
    'join': 'str',
    'rank_feature': 'float',
    'rank_features': 'dict',
    'dense_vector': 'list',
    'sparse_vector': 'dict',
    'alias': 'str',
    'flattened': 'dict',
    'shape': 'dict',
    'histogram': 'dict',
    'constant_keyword': 'str'
}

def normalize_mapping_data(mapping_data: Any) -> Dict[str, Any]:
    """
    Normalize mapping data to ensure it's a proper dictionary.
    Handles various formats that might be returned from Elasticsearch.
    """
    try:
        if mapping_data is None:
            return {}
            
        # If it has model_dump method (Pydantic model)
        if hasattr(mapping_data, "model_dump"):
            return mapping_data.model_dump()
            
        # If it's already a dict, return as-is
        if isinstance(mapping_data, dict):
            return mapping_data
            
        # If it's a string that looks like JSON, try to parse it
        if isinstance(mapping_data, str):
            try:
                parsed = json.loads(mapping_data)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            # If string parsing fails, wrap it
            return {"_raw_string": mapping_data}
            
        # For other types, try JSON serialization round-trip
        try:
            serialized = json.dumps(mapping_data, default=str)
            parsed = json.loads(serialized)
            if isinstance(parsed, dict):
                return parsed
        except (TypeError, json.JSONDecodeError):
            pass
            
        # Final fallback - wrap the value
        return {"_raw_value": str(mapping_data)}
        
    except Exception as e:
        logger.error(f"Error normalizing mapping data: {e}")
        return {"_error": f"Failed to normalize: {str(e)}"}

def flatten_properties(properties: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """
    Flatten nested Elasticsearch properties into dot notation.
    Returns a dict with field names as keys and ES types as values.
    """
    flattened = {}
    
    for field_name, field_def in properties.items():
        current_path = f"{prefix}.{field_name}" if prefix else field_name
        
        if not isinstance(field_def, dict):
            continue
            
        # Get the field type
        field_type = field_def.get('type')
        
        if field_type:
            # Direct field with type
            flattened[current_path] = field_type
        
        # Check for nested properties (object/nested types or properties without explicit type)
        nested_props = field_def.get('properties')
        if nested_props and isinstance(nested_props, dict):
            # Recursively flatten nested properties
            nested_flattened = flatten_properties(nested_props, current_path)
            flattened.update(nested_flattened)
        elif not field_type:
            # If no type and no properties, it might be an object field
            flattened[current_path] = 'object'
    
    return flattened

def get_python_type(es_type: str) -> str:
    """Convert Elasticsearch type to Python type for display."""
    return ES_TO_PYTHON_TYPES.get(es_type, 'Any')

def extract_mapping_info(mapping_dict: Dict[str, Any], index_name: str) -> Tuple[Dict[str, str], Dict[str, str], int]:
    """
    Extract and flatten mapping information from Elasticsearch mapping response.
    
    Returns:
        - es_types: Dict with field names as keys and ES types as values
        - python_types: Dict with field names as keys and Python types as values  
        - field_count: Total number of fields
    """
    try:
        # Normalize the mapping_dict first to handle unexpected types
        normalized_mapping = normalize_mapping_data(mapping_dict)
        
        if not isinstance(normalized_mapping, dict):
            logger.warning(f"Mapping data for {index_name} is not a dictionary after normalization")
            return {}, {}, 0
        
        # Get the index-specific mapping
        index_mapping = normalized_mapping.get(index_name, {})
        if not index_mapping and normalized_mapping:
            # If no exact match, try to get the first mapping
            index_mapping = next(iter(normalized_mapping.values()), {}) if normalized_mapping else {}
        
        # Ensure index_mapping is a dict
        if not isinstance(index_mapping, dict):
            logger.warning(f"Index mapping for {index_name} is not a dictionary: {type(index_mapping)}")
            logger.warning(f"Warning: mapping is {index_mapping}")
            return {}, {}, 0
        
        # Extract properties from mappings
        mappings = index_mapping.get('mappings', {})
        if not isinstance(mappings, dict):
            logger.warning(f"Mappings for {index_name} is not a dictionary: {type(mappings)}")
            return {}, {}, 0
            
        properties = mappings.get('properties', {})
        if not isinstance(properties, dict):
            logger.warning(f"Properties for {index_name} is not a dictionary: {type(properties)}")
            return {}, {}, 0
        
        # Flatten the properties
        es_types = flatten_properties(properties)
        
        # Create Python type mapping
        python_types = {field: get_python_type(es_type) for field, es_type in es_types.items()}
        
        field_count = len(es_types)
        
        return es_types, python_types, field_count
        
    except Exception as e:
        logger.error(f"Error extracting mapping info for {index_name}: {e}")
        return {}, {}, 0

def format_mapping_summary(es_types: Dict[str, str], python_types: Dict[str, str], max_fields: int = 50) -> str:
    """
    Format a human-readable summary of the mapping.
    """
    if not es_types:
        return "No field properties found in mapping."
    
    field_count = len(es_types)
    
    # Sort fields for consistent display
    sorted_fields = sorted(es_types.keys())
    preview_fields = sorted_fields[:max_fields]
    
    # Create preview with types for first few fields
    preview_parts = []
    for field in preview_fields[:10]:  # Show types for first 10 fields
        python_type = python_types.get(field, 'Any')
        preview_parts.append(f"{field} ({python_type})")
    
    # Add remaining field names without types
    if len(preview_fields) > 10:
        remaining = [f for f in preview_fields[10:]]
        preview_parts.extend(remaining)
    
    preview = ", ".join(preview_parts)
    if field_count > max_fields:
        preview += f" ... ({field_count - max_fields} more fields)"
    
    return f"Index has {field_count} fields. Fields: {preview}"
