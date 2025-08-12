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

def normalize_mapping_data(mapping_data: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize mapping data to ensure it's a proper dictionary.
    Handles various formats that might be returned from Elasticsearch.
    Returns None if normalization fails.
    """
    try:
        logger.debug(f"Normalizing mapping data of type {type(mapping_data)}: {mapping_data}")

        if mapping_data is None:
            logger.info("Mapping data is None. Returning empty dictionary.")
            return {}

        if hasattr(mapping_data, "model_dump"):
            logger.info("Mapping data has model_dump method. Using it to normalize.")
            return mapping_data.model_dump()

        if isinstance(mapping_data, dict):
            logger.info("Mapping data is already a dictionary. Returning as-is.")
            return mapping_data

        if isinstance(mapping_data, str):
            try:
                parsed = json.loads(mapping_data)
                if isinstance(parsed, dict):
                    logger.info("Mapping data is a valid JSON string. Parsed successfully.")
                    return parsed
            except json.JSONDecodeError:
                logger.warning("Mapping data is a string but not valid JSON.")
            return None

        try:
            serialized = json.dumps(mapping_data, default=str)
            parsed = json.loads(serialized)
            if isinstance(parsed, dict):
                logger.info("Mapping data serialized and parsed successfully.")
                return parsed
        except (TypeError, json.JSONDecodeError):
            logger.warning("Mapping data could not be serialized and parsed.")

        logger.warning("Mapping data could not be normalized to a dictionary.")
        return None

    except Exception as e:
        logger.error(f"Error normalizing mapping data: {e}")
        return None

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

def extract_mapping_info(mapping_dict: Any, index_name: str) -> Tuple[Dict[str, str], Dict[str, str], int]:
    """
    Extract and flatten mapping information from Elasticsearch mapping response.

    Returns:
        - es_types: Dict with field names as keys and ES types as values
        - python_types: Dict with field names as keys and Python types as values
        - field_count: Total number of fields
    """
    try:
        logger.debug(f"Extracting mapping info for index: {index_name}")
        normalized_mapping = normalize_mapping_data(mapping_dict)

        if not normalized_mapping:
            logger.warning(f"Mapping data for {index_name} could not be normalized.")
            return {}, {}, 0

        if not isinstance(normalized_mapping, dict):
            logger.warning(f"Mapping data for {index_name} is not a dictionary after normalization.")
            return {}, {}, 0

        index_mapping = normalized_mapping.get(index_name, {})
        if not index_mapping and normalized_mapping:
            index_mapping = next(iter(normalized_mapping.values()), {})

        if not isinstance(index_mapping, dict):
            logger.warning(f"Index mapping for {index_name} is not a dictionary: {type(index_mapping)}")
            logger.debug(f"Index mapping content: {index_mapping}")
            return {}, {}, 0

        mappings = index_mapping.get('mappings', {})
        if not isinstance(mappings, dict):
            logger.warning(f"Mappings for {index_name} is not a dictionary: {type(mappings)}")
            return {}, {}, 0

        properties = mappings.get('properties', {})
        if not isinstance(properties, dict):
            logger.warning(f"Properties for {index_name} is not a dictionary: {type(properties)}")
            return {}, {}, 0

        logger.debug(f"Flattening properties for index: {index_name}")
        es_types = flatten_properties(properties)

        python_types = {field: get_python_type(es_type) for field, es_type in es_types.items()}
        field_count = len(es_types)

        logger.info(f"Extracted {field_count} fields for index: {index_name}")
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
