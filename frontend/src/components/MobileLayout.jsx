import React, { useState } from 'react';
import { Database, X, Menu, Star } from 'lucide-react';
import { ProviderSelector } from './Selectors.jsx';

export default function MobileLayout({ 
  children, 
  currentView, 
  setCurrentView, 
  backendHealth, 
  proxyHealth, 
  renderHealthIcon,
  getTooltipContent,
  checkBackendHealth,
  selectedProvider,
  setSelectedProvider,
  providers,
  tuning,
  setTuning,
  enhancedAvailable 
}) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white shadow-sm border-b border-gray-200 lg:hidden">
        <div className="flex items-center justify-between h-16 px-4">
          <div className="flex items-center">
            <Database className="h-6 w-6 text-blue-600 mr-2" />
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-semibold text-gray-900">ES AI Assistant</h1>
              {enhancedAvailable && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <Star className="w-3 h-3 mr-1" />
                  Enhanced
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {/* Health indicators */}
            <div className="flex items-center space-x-1">
              {backendHealth && renderHealthIcon && (
                <button
                  onClick={() => checkBackendHealth && checkBackendHealth(true)}
                  title={getTooltipContent ? getTooltipContent(backendHealth, 'Backend') : 'Backend Health'}
                  className="p-1 rounded hover:bg-gray-100"
                >
                  {renderHealthIcon(backendHealth)}
                </button>
              )}
              {proxyHealth && renderHealthIcon && (
                <button
                  title={getTooltipContent ? getTooltipContent(proxyHealth, 'Proxy') : 'Proxy Health'}
                  className="p-1 rounded hover:bg-gray-100"
                >
                  {renderHealthIcon(proxyHealth)}
                </button>
              )}
            </div>
            <button className="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
        {mobileMenuOpen && (
          <div className="border-t border-gray-200 bg-white">
            <div className="px-2 pt-2 pb-3 space-y-3">
              {/* AI Provider Selector */}
              {providers && selectedProvider && setSelectedProvider && (
                <div className="px-3">
                  <ProviderSelector
                    selectedProvider={selectedProvider}
                    onProviderChange={setSelectedProvider}
                    providers={providers}
                  />
                </div>
              )}
              
              {/* Navigation */}
              <div className="space-y-1">
                <button 
                  onClick={() => {setCurrentView && setCurrentView('chat'); setMobileMenuOpen(false);}}
                  className={`w-full px-3 py-2 rounded-md text-sm text-left hover:bg-gray-50 block ${currentView === 'chat' ? 'bg-blue-50 text-blue-700' : ''}`}
                >
                  Chat Interface
                </button>
                <button 
                  onClick={() => {setCurrentView && setCurrentView('query'); setMobileMenuOpen(false);}}
                  className={`w-full px-3 py-2 rounded-md text-sm text-left hover:bg-gray-50 block ${currentView === 'query' ? 'bg-blue-50 text-blue-700' : ''}`}
                >
                  Query Editor
                </button>
              </div>
            </div>
          </div>
        )}
      </header>
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
