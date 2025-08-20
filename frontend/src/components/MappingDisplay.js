export { default } from './MappingDisplay.jsx';
import React, { useState, useCallback } from 'react';
import { ChevronDown, ChevronRight, Eye, EyeOff, Copy, Check } from 'lucide-react';

const MappingDisplay = ({ mapping, indexName }) => {
  const [expandedPaths, setExpandedPaths] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [showDataTypes, setShowDataTypes] = useState(true);
  const [copiedField, setCopiedField] = useState(null);

  // Process mapping to flat structure for display
  const flattenMapping = useCallback((obj, prefix = '') => {
    let fields = [];
    
    if (obj && typeof obj === 'object') {
      Object.entries(obj).forEach(([key, value]) => {
        const fullPath = prefix ? `${prefix}.${key}` : key;
        
        if (value && typeof value === 'object') {
          if (value.type) {
            // This is a field definition
            fields.push({
              path: fullPath,
              type: value.type,
              analyzer: value.analyzer,
              format: value.format,
              fields: value.fields,
              properties: value.properties,
              isLeaf: true
            });
            
            // If it has sub-fields or properties, recurse
            if (value.properties) {
              fields.push(...flattenMapping(value.properties, fullPath));
            }
            if (value.fields) {
              fields.push(...flattenMapping(value.fields, fullPath));
            }
          } else if (value.properties) {
            // This is an object with properties
            fields.push({
              path: fullPath,
              type: 'object',
              isLeaf: false
            });
            fields.push(...flattenMapping(value.properties, fullPath));
          } else {
            // Generic object
            fields.push(...flattenMapping(value, fullPath));
          }
        }
      });
    }
    
    return fields;
  }, []);

  const mappingFields = React.useMemo(() => {
    if (!mapping || !mapping.mappings) return [];
    return flattenMapping(mapping.mappings.properties || mapping.mappings);
  }, [mapping, flattenMapping]);

  const filteredFields = React.useMemo(() => {
    if (!searchTerm) return mappingFields;
    return mappingFields.filter(field => 
      field.path.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (field.type && field.type.toLowerCase().includes(searchTerm.toLowerCase()))
    );
  }, [mappingFields, searchTerm]);

  const toggleExpand = (path) => {
    const newExpanded = new Set(expandedPaths);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpandedPaths(newExpanded);
  };

  const copyFieldPath = async (path) => {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedField(path);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (err) {
      console.error('Failed to copy field path:', err);
    }
  };

  const getTypeColor = (type) => {
    const colors = {
      'text': 'bg-blue-100 text-blue-800',
      'keyword': 'bg-green-100 text-green-800',
      'long': 'bg-purple-100 text-purple-800',
      'integer': 'bg-purple-100 text-purple-800',
      'double': 'bg-purple-100 text-purple-800',
      'float': 'bg-purple-100 text-purple-800',
      'date': 'bg-orange-100 text-orange-800',
      'boolean': 'bg-yellow-100 text-yellow-800',
      'object': 'bg-gray-100 text-gray-800',
      'nested': 'bg-indigo-100 text-indigo-800'
    };
    return colors[type] || 'bg-gray-100 text-gray-800';
  };

  // groupByParent helper removed; not used in current render

  const renderField = (field) => {
    const hasChildren = mappingFields.some(f => 
      f.path.startsWith(field.path + '.') && f.path !== field.path
    );
    const isExpanded = expandedPaths.has(field.path);
    const indent = field.level * 20;

    return (
      <div
        key={field.path}
        className="border-b border-gray-100 hover:bg-gray-50"
        style={{ paddingLeft: `${indent}px` }}
      >
        <div className="flex items-center justify-between py-2 px-3">
          <div className="flex items-center space-x-2 min-w-0 flex-1">
            {hasChildren && (
              <button
                onClick={() => toggleExpand(field.path)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
              </button>
            )}
            {!hasChildren && <div className="w-6" />}
            
            <span 
              className="font-mono text-sm text-gray-900 truncate cursor-pointer hover:text-blue-600"
              onClick={() => copyFieldPath(field.path)}
              title={`Click to copy: ${field.path}`}
            >
              {field.path.split('.').pop()}
            </span>
            
            {showDataTypes && field.type && (
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(field.type)}`}>
                {field.type}
              </span>
            )}
            
            {field.analyzer && (
              <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded-full text-xs">
                {field.analyzer}
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-2">
            {copiedField === field.path ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <button
                onClick={() => copyFieldPath(field.path)}
                className="p-1 hover:bg-gray-100 rounded opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Copy className="h-4 w-4 text-gray-400" />
              </button>
            )}
          </div>
        </div>
      </div>
    );
  };

  if (!mapping) {
    return (
      <div className="text-center py-8 text-gray-500">
        No mapping data available
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-gray-900">
            Index Mapping: {indexName}
          </h3>
          <button
            onClick={() => setShowDataTypes(!showDataTypes)}
            className="flex items-center space-x-2 px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50"
          >
            {showDataTypes ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            <span>{showDataTypes ? 'Hide' : 'Show'} Types</span>
          </button>
        </div>
        
        {/* Search */}
        <input
          type="text"
          placeholder="Search fields..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {/* Field List */}
      <div className="max-h-96 overflow-y-auto">
        {filteredFields.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            {searchTerm ? `No fields match "${searchTerm}"` : 'No fields found'}
          </div>
        ) : (
          <div className="group">
            {filteredFields.map(renderField)}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-200 bg-gray-50 text-sm text-gray-600">
        Showing {filteredFields.length} of {mappingFields.length} fields
        {searchTerm && (
          <button
            onClick={() => setSearchTerm('')}
            className="ml-2 text-blue-600 hover:text-blue-800"
          >
            Clear search
          </button>
        )}
      </div>
    </div>
  );
};

export default MappingDisplay;
