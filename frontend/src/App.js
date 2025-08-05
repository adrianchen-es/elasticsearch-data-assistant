import React, { useState, useEffect } from 'react';
import { MessageSquare, Settings, Database, Search } from 'lucide-react';
import ChatInterface from './components/ChatInterface';
import QueryEditor from './components/QueryEditor';
import { IndexSelector, ProviderSelector } from './components/Selectors';
import { setupTelemetry } from './telemetry/setup';

function App() {
  const [selectedIndex, setSelectedIndex] = useState('');
  const [selectedProvider, setSelectedProvider] = useState('azure');
  const [currentView, setCurrentView] = useState('chat');
  const [indices, setIndices] = useState([]);

  useEffect(() => {
    // Setup telemetry
    setupTelemetry();
    
    // Fetch available indices
    fetchIndices();
  }, []);

  const fetchIndices = async () => {
    try {
      const response = await fetch('/api/indices');
      const data = await response.json();
      setIndices(data);
      if (data.length > 0 && !selectedIndex) {
        setSelectedIndex(data[0]);
      }
    } catch (error) {
      console.error('Failed to fetch indices:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <Database className="h-8 w-8 text-blue-600 mr-3" />
              <h1 className="text-xl font-semibold text-gray-900">
                Elasticsearch AI Assistant
              </h1>
            </div>
            
            <div className="flex items-center space-x-4">
              <IndexSelector
                indices={indices}
                selectedIndex={selectedIndex}
                onIndexChange={setSelectedIndex}
              />
              <ProviderSelector
                selectedProvider={selectedProvider}
                onProviderChange={setSelectedProvider}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            <button
              onClick={() => setCurrentView('chat')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                currentView === 'chat'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <MessageSquare className="inline h-4 w-4 mr-2" />
              Chat Interface
            </button>
            <button
              onClick={() => setCurrentView('query')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                currentView === 'query'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Search className="inline h-4 w-4 mr-2" />
              Query Editor
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {currentView === 'chat' && (
          <ChatInterface
            selectedIndex={selectedIndex}
            selectedProvider={selectedProvider}
          />
        )}
        {currentView === 'query' && (
          <QueryEditor
            selectedIndex={selectedIndex}
          />
        )}
      </main>
    </div>
  );
}

export default App;