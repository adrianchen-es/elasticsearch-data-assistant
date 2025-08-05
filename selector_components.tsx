import React from 'react';
import { ChevronDown, Database, Cpu } from 'lucide-react';

export const IndexSelector = ({ indices, selectedIndex, onIndexChange }) => {
  return (
    <div className="relative">
      <select
        value={selectedIndex}
        onChange={(e) => onIndexChange(e.target.value)}
        className="appearance-none bg-white border border-gray-300 rounded-md pl-3 pr-8 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        <option value="">Select Index</option>
        {indices.map((index) => (
          <option key={index} value={index}>
            {index}
          </option>
        ))}
      </select>
      <Database className="absolute right-2 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
    </div>
  );
};

export const ProviderSelector = ({ selectedProvider, onProviderChange }) => {
  const providers = [
    { value: 'azure', label: 'Azure AI' },
    { value: 'openai', label: 'OpenAI' }
  ];

  return (
    <div className="relative">
      <select
        value={selectedProvider}
        onChange={(e) => onProviderChange(e.target.value)}
        className="appearance-none bg-white border border-gray-300 rounded-md pl-3 pr-8 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        {providers.map((provider) => (
          <option key={provider.value} value={provider.value}>
            {provider.label}
          </option>
        ))}
      </select>
      <Cpu className="absolute right-2 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
    </div>
  );
};