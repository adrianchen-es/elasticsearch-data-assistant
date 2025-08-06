//require('./telemetry/node_tracing.js');
import React, { useState, useEffect } from 'react';
import { MessageSquare, Settings, Database, Search, CheckCircle, XCircle, AlertCircle, RefreshCw, Server, Globe } from 'lucide-react';
import { setupTelemetryWeb } from './telemetry/setup';
import { ProviderSelector } from './components/Selectors';
import ChatInterface from './components/ChatInterface';
import QueryEditor from './components/QueryEditor';

function App() {
  const [selectedProvider, setSelectedProvider] = useState('azure');
  const [currentView, setCurrentView] = useState('chat');
  const [indices, setIndices] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState('');
  
  // Backend health status state (/api/health)
  const [backendHealth, setBackendHealth] = useState({
    status: 'checking', // 'healthy', 'unhealthy', 'checking', 'error'
    message: 'Checking backend status...',
    lastChecked: null,
    services: {}
  });

  // Proxy health status state (/api/healthz)
  const [proxyHealth, setProxyHealth] = useState({
    status: 'checking', // 'healthy', 'unhealthy', 'checking', 'error'
    message: 'Checking proxy status...',
    lastChecked: null,
    services: {}
  });

  // Check backend health status
  const checkBackendHealth = async () => {
    try {
      setBackendHealth(prev => ({ ...prev, status: 'checking', message: 'Checking backend status...' }));
      
      const response = await fetch('/api/health');
      const data = await response.json();
      
      if (response.ok) {
        setBackendHealth({
          status: data.status === 'healthy' ? 'healthy' : 'unhealthy',
          message: data.message || (data.status === 'healthy' ? 'Backend operational' : 'Backend issues detected'),
          lastChecked: new Date().toISOString(),
          services: data.services || {}
        });
      } else {
        throw new Error(data.message || 'Backend health check failed');
      }
    } catch (error) {
      setBackendHealth({
        status: 'error',
        message: `Backend unreachable: ${error.message}`,
        lastChecked: new Date().toISOString(),
        services: {}
      });
    }
  };

  // Check proxy health status
  const checkProxyHealth = async () => {
    try {
      setProxyHealth(prev => ({ ...prev, status: 'checking', message: 'Checking proxy status...' }));
      
      const response = await fetch('/api/healthz');
      const data = await response.json();
      
      if (response.ok) {
        setProxyHealth({
          status: data.status === 'healthy' ? 'healthy' : 'unhealthy',
          message: data.message || (data.status === 'healthy' ? 'Proxy operational' : 'Proxy issues detected'),
          lastChecked: new Date().toISOString(),
          services: data.services || {}
        });
      } else {
        throw new Error(data.message || 'Proxy health check failed');
      }
    } catch (error) {
      setProxyHealth({
        status: 'error',
        message: `Proxy unreachable: ${error.message}`,
        lastChecked: new Date().toISOString(),
        services: {}
      });
    }
  };

  // Check both health endpoints
  const checkAllHealth = async () => {
    await Promise.all([
      checkBackendHealth(),
      checkProxyHealth()
    ]);
  };

  useEffect(() => {
    // Setup telemetry
    setupTelemetryWeb();
    
    // Initial health checks
    checkAllHealth();
    
    // Set up periodic health checks every 30 seconds
    const healthCheckInterval = setInterval(checkAllHealth, 30000);
    
    return () => clearInterval(healthCheckInterval);
  }, []);

  // Render health status icon
  const renderHealthIcon = (healthStatus) => {
    const iconProps = { className: "h-5 w-5" };
    
    switch (healthStatus.status) {
      case 'healthy':
        return <CheckCircle {...iconProps} className="h-5 w-5 text-green-500" />;
      case 'unhealthy':
        return <AlertCircle {...iconProps} className="h-5 w-5 text-yellow-500" />;
      case 'error':
        return <XCircle {...iconProps} className="h-5 w-5 text-red-500" />;
      case 'checking':
      default:
        return <RefreshCw {...iconProps} className="h-5 w-5 text-gray-400 animate-spin" />;
    }
  };

  // Format last checked time
  const formatLastChecked = (timestamp) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  // Generate tooltip content
  const getTooltipContent = (healthStatus, systemName) => {
    const { status, message, lastChecked, services } = healthStatus;
    
    let content = `${systemName}: ${message}\nLast checked: ${formatLastChecked(lastChecked)}`;
    
    if (Object.keys(services).length > 0) {
      content += `\n\n${systemName} Services:`;
      Object.entries(services).forEach(([service, serviceStatus]) => {
        const statusIcon = typeof serviceStatus === 'object' 
          ? (typeof serviceStatus.status === 'string' && serviceStatus.status.startsWith('healthy') ? '✅' : '❌')
          : (typeof serviceStatus === 'string' && serviceStatus.startsWith('healthy') ? '✅' : '❌');
        const serviceMessage = typeof serviceStatus === 'object' 
          ? serviceStatus.message || service
          : service;
        content += `\n${statusIcon} ${serviceMessage}`;
      });
    }
    
    return content;
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
              {/* Backend Health Status */}
              <div className="relative group">
                <button
                  onClick={checkBackendHealth}
                  className="flex items-center space-x-2 px-2 py-1 rounded-md hover:bg-gray-100 transition-colors"
                  title={getTooltipContent(backendHealth, 'Backend')}
                >
                  <Server className="h-4 w-4 text-gray-500" />
                  {renderHealthIcon(backendHealth)}
                  <span className="text-sm text-gray-600 hidden md:inline">
                    Backend
                  </span>
                </button>
                
                {/* Backend Tooltip */}
                <div className="absolute right-0 top-full mt-1 w-80 bg-black text-white text-xs rounded-md p-3 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-opacity z-50">
                  <div className="whitespace-pre-line">
                    {getTooltipContent(backendHealth, 'Backend')}
                  </div>
                  <div className="text-gray-300 mt-2 text-xs">
                    Click to refresh backend status
                  </div>
                </div>
              </div>

              {/* Proxy Health Status */}
              <div className="relative group">
                <button
                  onClick={checkProxyHealth}
                  className="flex items-center space-x-2 px-2 py-1 rounded-md hover:bg-gray-100 transition-colors"
                  title={getTooltipContent(proxyHealth, 'Proxy')}
                >
                  <Globe className="h-4 w-4 text-gray-500" />
                  {renderHealthIcon(proxyHealth)}
                  <span className="text-sm text-gray-600 hidden md:inline">
                    Proxy
                  </span>
                </button>
                
                {/* Proxy Tooltip */}
                <div className="absolute right-0 top-full mt-1 w-80 bg-black text-white text-xs rounded-md p-3 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-opacity z-50">
                  <div className="whitespace-pre-line">
                    {getTooltipContent(proxyHealth, 'Proxy')}
                  </div>
                  <div className="text-gray-300 mt-2 text-xs">
                    Click to refresh proxy status
                  </div>
                </div>
              </div>
              
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
            selectedProvider={selectedProvider}
            selectedIndex={selectedIndex}
            setSelectedIndex={setSelectedIndex}
          />
        )}
        {currentView === 'query' && (
          <QueryEditor
            selectedIndex={selectedIndex}
            setSelectedIndex={setSelectedIndex}
          />
        )}
      </main>
    </div>
  );
}

export default App;

process.on('SIGINT', function () {
  process.exit();
});