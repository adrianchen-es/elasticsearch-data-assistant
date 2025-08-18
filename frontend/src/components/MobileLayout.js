import React, { useState } from 'react';
import { Menu, X, Database, MessageSquare, Search, Settings } from 'lucide-react';

const MobileLayout = ({ 
  children, 
  currentView, 
  setCurrentView, 
  backendHealth, 
  proxyHealth,
  renderHealthIcon,
  checkBackendHealth,
  selectedProvider,
  setSelectedProvider,
  providers,
  tuning,
  setTuning
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navigationItems = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'query', label: 'Query Editor', icon: Search },
  ];

  const closeMobileMenu = () => setMobileMenuOpen(false);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Mobile Header */}
      <header className="bg-white shadow-sm border-b border-gray-200 lg:hidden">
        <div className="flex items-center justify-between h-16 px-4">
          <div className="flex items-center">
            <Database className="h-6 w-6 text-blue-600 mr-2" />
            <h1 className="text-lg font-semibold text-gray-900">ES AI Assistant</h1>
          </div>
          <div className="flex items-center space-x-2">
            {/* Health indicators - compact for mobile */}
              <div className="flex items-center space-x-1">
                <button
                  onClick={() => checkBackendHealth(true)}
                  className="p-1"
                  title={typeof backendHealth === 'object' ? `Backend: ${backendHealth.message || backendHealth.status}` : 'Backend Status'}
                >
                  {renderHealthIcon(backendHealth)}
                </button>
                {/* Only show proxy status when backend is not reachable/healthy to avoid noise */}
                {(backendHealth && (backendHealth.status === 'unhealthy' || backendHealth.status === 'error')) && (
                  <div title={typeof proxyHealth === 'object' ? `Proxy: ${proxyHealth.message || proxyHealth.status}` : 'Proxy Status'}>
                    {renderHealthIcon(proxyHealth)}
                  </div>
                )}
              </div>
            
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100"
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Menu */}
        {mobileMenuOpen && (
          <div className="border-t border-gray-200 bg-white">
            <div className="px-2 pt-2 pb-3 space-y-1">
              {navigationItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setCurrentView(item.id);
                      closeMobileMenu();
                    }}
                    className={`${
                      currentView === item.id
                        ? 'bg-blue-50 border-blue-500 text-blue-700'
                        : 'border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-800'
                    } group border-l-4 px-3 py-2 flex items-center text-sm font-medium w-full`}
                  >
                    <Icon className="mr-3 h-5 w-5" />
                    {item.label}
                  </button>
                );
              })}
              
              {/* Provider selector in mobile menu */}
              <div className="px-3 py-2 border-t border-gray-200 mt-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  AI Provider
                </label>
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded-md px-2 py-1"
                  data-testid="mobile-provider-selector"
                >
                  {providers.map((provider) => (
                    <option key={provider.id} value={provider.id} disabled={provider.configured === false || provider.healthy === false}>
                      {provider.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Tuning toggles in mobile menu */}
              {setTuning && (
                <div className="px-3 py-2 border-t border-gray-200 mt-2">
                  <label className="block text-xs font-medium text-gray-700 mb-1" title="Adjust query strategy preferences">
                    Tuning
                  </label>
                  <div className="flex items-center space-x-4">
                    <label className="flex items-center space-x-1 text-sm" title="Favor precision: narrower results">
                      <input type="checkbox" checked={Boolean(tuning?.precision)} onChange={(e)=> setTuning({ ...(tuning||{}), precision: e.target.checked })} />
                      <span>Precision</span>
                    </label>
                    <label className="flex items-center space-x-1 text-sm" title="Favor recall: broader results">
                      <input type="checkbox" checked={Boolean(tuning?.recall)} onChange={(e)=> setTuning({ ...(tuning||{}), recall: e.target.checked })} />
                      <span>Recall</span>
                    </label>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </header>

      {/* Desktop Header */}
      <header className="bg-white shadow-sm border-b border-gray-200 hidden lg:block">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <Database className="h-8 w-8 text-blue-600 mr-3" />
              <h1 className="text-xl font-semibold text-gray-900">
                Elasticsearch AI Assistant
              </h1>
            </div>
            
            {/* Desktop Navigation */}
            <nav className="flex space-x-8">
              {navigationItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => setCurrentView(item.id)}
                    className={`${
                      currentView === item.id
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    } border-b-2 px-1 pt-1 pb-4 text-sm font-medium flex items-center`}
                  >
                    <Icon className="mr-2 h-4 w-4" />
                    {item.label}
                  </button>
                );
              })}
            </nav>

            {/* Desktop Health, Provider & Tuning */}
            <div className="flex items-center space-x-4">
              {/* Provider selector */}
              <div className="flex items-center space-x-2">
                <label className="text-sm font-medium text-gray-700">Provider:</label>
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  className="text-sm border border-gray-300 rounded-md px-2 py-1"
                  data-testid="provider-selector"
                >
                  {providers.map((provider) => (
                    <option key={provider.id} value={provider.id} disabled={provider.configured === false || provider.healthy === false}>
                      {provider.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Tuning toggles */}
              {setTuning && (
                <div className="flex items-center space-x-2">
                  <label className="text-sm font-medium text-gray-700" title="Adjust query strategy preferences">Tuning:</label>
                  <label className="flex items-center space-x-1 text-sm" title="Favor precision: narrower results">
                    <input type="checkbox" checked={Boolean(tuning?.precision)} onChange={(e)=> setTuning({ ...(tuning||{}), precision: e.target.checked })} />
                    <span>Precision</span>
                  </label>
                  <label className="flex items-center space-x-1 text-sm" title="Favor recall: broader results">
                    <input type="checkbox" checked={Boolean(tuning?.recall)} onChange={(e)=> setTuning({ ...(tuning||{}), recall: e.target.checked })} />
                    <span>Recall</span>
                  </label>
                </div>
              )}

              {/* Health Status */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => checkBackendHealth(true)}
                  className="flex items-center space-x-1 px-2 py-1 rounded-md hover:bg-gray-100"
                  title="Backend Status"
                >
                  {renderHealthIcon(backendHealth)}
                  <span className="text-sm text-gray-600">Backend</span>
                </button>
                <div className="flex items-center space-x-1" title="Proxy Status">
                  {renderHealthIcon(proxyHealth)}
                  <span className="text-sm text-gray-600">Proxy</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        <div className="h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 lg:py-6">
          {children}
        </div>
      </main>
    </div>
  );
};

export default MobileLayout;
