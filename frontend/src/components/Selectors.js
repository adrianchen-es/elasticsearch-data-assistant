import React from 'react';
import { Database, Cpu } from 'lucide-react';

// Component to select AI provider
const ProviderSelector = ({ selectedProvider, onProviderChange }) => {
  const providers = [
    { value: 'azure', label: 'Azure AI', available: true },
    { value: 'openai', label: 'OpenAI', available: true }
  ];

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-1">
        AI Provider
      </label>
      <div className="relative">
        <select
          value={selectedProvider}
          onChange={(e) => onProviderChange(e.target.value)}
          className="appearance-none bg-white border border-gray-300 rounded-md pl-3 pr-10 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-32"
        >
          {providers.map((provider) => (
            <option 
              key={provider.value} 
              value={provider.value}
              disabled={!provider.available}
            >
              {provider.label}
            </option>
          ))}
        </select>
        <Cpu className="absolute right-3 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>
    </div>
  );
};

export { ProviderSelector };