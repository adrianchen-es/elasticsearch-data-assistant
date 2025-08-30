"""
AI Tool definitions for function calling with Elasticsearch queries.
"""

import json
from typing import Dict, List, Any

def get_elasticsearch_tools() -> List[Dict[str, Any]]:
    """Get the function definitions for Elasticsearch operations."""
    return [
        {
            "type": "function",
            "function": {
                "name": "execute_elasticsearch_query",
                "description": "Execute an Elasticsearch query against the selected indices. This tool handles search queries, aggregations, and filtering operations on Elasticsearch data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "object",
                            "description": "The Elasticsearch query DSL object. Can be a simple match query, bool query, aggregation, or any valid Elasticsearch query structure.",
                            "properties": {
                                "match": {
                                    "type": "object",
                                    "description": "Simple match query for text search"
                                },
                                "match_all": {
                                    "type": "object",
                                    "description": "Match all documents query"
                                },
                                "bool": {
                                    "type": "object",
                                    "description": "Boolean query with must, should, must_not, and filter clauses"
                                },
                                "range": {
                                    "type": "object",
                                    "description": "Range query for numeric or date fields"
                                },
                                "term": {
                                    "type": "object",
                                    "description": "Exact term matching"
                                },
                                "terms": {
                                    "type": "object",
                                    "description": "Multiple exact term matching"
                                },
                                "wildcard": {
                                    "type": "object",
                                    "description": "Wildcard pattern matching"
                                },
                                "regexp": {
                                    "type": "object",
                                    "description": "Regular expression matching"
                                }
                            }
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of documents to return (0-10000, default: 10)",
                            "minimum": 0,
                            "maximum": 10000,
                            "default": 10
                        },
                        "from": {
                            "type": "integer",
                            "description": "Starting offset for pagination (default: 0)",
                            "minimum": 0,
                            "default": 0
                        },
                        "sort": {
                            "type": "array",
                            "description": "Sort order specification",
                            "items": {
                                "type": "object"
                            }
                        },
                        "aggs": {
                            "type": "object",
                            "description": "Aggregations to perform on the data"
                        },
                        "_source": {
                            "description": "Fields to include or exclude from the response",
                            "oneOf": [
                                {"type": "boolean"},
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}}
                            ]
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": True
                }
            }
        }
    ]

def parse_function_arguments(arguments_str: str) -> Dict[str, Any]:
    """Parse function arguments from JSON string, with error handling."""
    try:
        return json.loads(arguments_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in function arguments: {e}")

def validate_elasticsearch_query(query_args: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize Elasticsearch query arguments."""
    # Ensure we have a query
    if "query" not in query_args:
        raise ValueError("Query parameter is required")
    
    # Validate size limits
    size = query_args.get("size", 10)
    if not isinstance(size, int) or size < 0 or size > 10000:
        query_args["size"] = min(max(0, int(size)), 10000)
    
    # Validate from offset
    from_offset = query_args.get("from", 0)
    if not isinstance(from_offset, int) or from_offset < 0:
        query_args["from"] = max(0, int(from_offset))
    
    # Ensure query is a dict
    if not isinstance(query_args["query"], dict):
        raise ValueError("Query must be a valid object")
    
    return query_args
