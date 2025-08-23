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
      {/* Mobile Header - visible on small screens */}
      <header className="bg-white shadow-sm border-b border-gray-200 md:hidden">
        <div className="flex items-center justify-between h-14 px-3 sm:px-4 sm:h-16">
          <div className="flex items-center min-w-0 flex-1">
            <Database className="h-5 w-5 sm:h-6 sm:w-6 text-blue-600 mr-2 flex-shrink-0" />
            <div className="flex items-center space-x-2 min-w-0">
              <h1 className="text-base sm:text-lg font-semibold text-gray-900 truncate">ES AI Assistant</h1>
              {enhancedAvailable && (
                <span className="hidden xs:inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <Star className="w-3 h-3 mr-1" />
                  Enhanced
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-1 sm:space-x-2 flex-shrink-0">
            {/* Health indicators - compact on mobile */}
            <div className="flex items-center space-x-1">
              {backendHealth && renderHealthIcon && (
                <button
                  onClick={() => checkBackendHealth && checkBackendHealth(true)}
                  title={getTooltipContent ? getTooltipContent(backendHealth, 'Backend') : 'Backend Health'}
                  className="p-1 rounded hover:bg-gray-100 touch-manipulation"
                >
                  {renderHealthIcon(backendHealth)}
                </button>
              )}
              {proxyHealth && renderHealthIcon && (
                <button
                  title={getTooltipContent ? getTooltipContent(proxyHealth, 'Proxy') : 'Proxy Health'}
                  className="p-1 rounded hover:bg-gray-100 touch-manipulation"
                >
                  {renderHealthIcon(proxyHealth)}
                </button>
              )}
            </div>
            <button 
              className="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 touch-manipulation" 
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="h-5 w-5 sm:h-6 sm:w-6" /> : <Menu className="h-5 w-5 sm:h-6 sm:w-6" />}
            </button>
          </div>
        </div>
        {mobileMenuOpen && (
          <div className="border-t border-gray-200 bg-white shadow-lg">
            <div className="px-3 pt-3 pb-4 space-y-4 max-h-96 overflow-y-auto">
              {/* AI Provider Selector */}
              {providers && selectedProvider && setSelectedProvider && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">AI Provider</label>
                  <ProviderSelector
                    selectedProvider={selectedProvider}
                    onProviderChange={setSelectedProvider}
                    providers={providers}
                  />
                </div>
              )}
              
              {/* Navigation */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Navigation</label>
                <div className="grid grid-cols-1 gap-2">
                  <button 
                    onClick={() => {setCurrentView && setCurrentView('chat'); setMobileMenuOpen(false);}}
                    className={`w-full px-4 py-3 rounded-lg text-sm text-left hover:bg-gray-50 flex items-center space-x-2 touch-manipulation transition-colors ${
                      currentView === 'chat' ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'border border-gray-200'
                    }`}
                  >
                    <span className="text-lg">💬</span>
                    <span>Chat Interface</span>
                  </button>
                  <button 
                    onClick={() => {setCurrentView && setCurrentView('query'); setMobileMenuOpen(false);}}
                    className={`w-full px-4 py-3 rounded-lg text-sm text-left hover:bg-gray-50 flex items-center space-x-2 touch-manipulation transition-colors ${
                      currentView === 'query' ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'border border-gray-200'
                    }`}
                  >
                    <span className="text-lg">🔍</span>
                    <span>Query Editor</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </header>
      
      {/* Desktop Header - visible on larger screens */}
      <header className="hidden md:block bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <div className="flex items-center">
                <Database className="h-6 w-6 text-blue-600 mr-3" />
                <div className="flex items-center space-x-2">
                  <h1 className="text-xl font-semibold text-gray-900">ES AI Assistant</h1>
                  {enhancedAvailable && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      <Star className="w-3 h-3 mr-1" />
                      Enhanced
                    </span>
                  )}
                </div>
              </div>
              
              {/* Desktop Navigation */}
              <nav className="flex space-x-1">
                <button 
                  onClick={() => setCurrentView && setCurrentView('chat')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    currentView === 'chat' 
                      ? 'bg-blue-100 text-blue-700' 
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  Chat Interface
                </button>
                <button 
                  onClick={() => setCurrentView && setCurrentView('query')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    currentView === 'query' 
                      ? 'bg-blue-100 text-blue-700' 
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  Query Editor
                </button>
              </nav>
            </div>
            
            <div className="flex items-center space-x-4">
              {/* AI Provider Selector */}
              {providers && selectedProvider && setSelectedProvider && (
                <div className="min-w-0">
                  <ProviderSelector
                    selectedProvider={selectedProvider}
                    onProviderChange={setSelectedProvider}
                    providers={providers}
                  />
                </div>
              )}
              
              {/* Health indicators */}
              <div className="flex items-center space-x-2">
                {backendHealth && renderHealthIcon && (
                  <button
                    onClick={() => checkBackendHealth && checkBackendHealth(true)}
                    title={getTooltipContent ? getTooltipContent(backendHealth, 'Backend') : 'Backend Health'}
                    className="p-2 rounded hover:bg-gray-100"
                  >
                    {renderHealthIcon(backendHealth)}
                  </button>
                )}
                {proxyHealth && renderHealthIcon && (
                  <button
                    title={getTooltipContent ? getTooltipContent(proxyHealth, 'Proxy') : 'Proxy Health'}
                    className="p-2 rounded hover:bg-gray-100"
                  >
                    {renderHealthIcon(proxyHealth)}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </header>
      
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
