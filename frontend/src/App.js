//require('./telemetry/node_tracing.js');
import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { setupTelemetryWeb } from './telemetry/setup';
import { info as feInfo } from './lib/logging';
import { readCachedHealth, writeCachedHealth } from './utils/healthCache';
import { ProviderSelector } from './components/Selectors';
import ChatInterface from './components/ChatInterface';
import QueryEditor from './components/QueryEditor';
import MobileLayout from './components/MobileLayout';

function App() {
  const [selectedProvider, setSelectedProvider] = useState('azure');
  const [currentView, setCurrentView] = useState('chat');
  // indices and selectedIndex are managed in child components; keep local placeholders
  const [indices] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState('');

  const [providers, setProviders] = useState([
    { id: 'azure', name: 'Azure OpenAI', configured: true, healthy: true },
    { id: 'openai', name: 'OpenAI', configured: true, healthy: true }
  ]);
  // User tuning for search behavior (persisted in localStorage)
  const [tuning, setTuning] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('elasticsearch_chat_tuning') || '{}');
    } catch { return {}; }
  });
  
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
  const HEALTH_CACHE_KEYS = {
    backend: 'health_backend',
    proxy: 'health_proxy'
  };

  const HEALTH_TTLS = {
    success: 15 * 60 * 1000, // 15 minutes for healthy services
    error: 5 * 60 * 1000, // 5 minutes for unhealthy services (retry sooner)
    manual: 30 * 1000, // 30 seconds throttle for manual refresh
  };

  // Track last manual refresh to implement throttling
  const [lastManualRefresh, setLastManualRefresh] = useState({
    backend: 0,
    proxy: 0
  });

  // health cache helpers now live in ./utils/healthCache and use sessionStorage

  const checkBackendHealth = async (force = false) => {
    // Implement manual refresh throttling
    if (force) {
      const now = Date.now();
      if (now - lastManualRefresh.backend < HEALTH_TTLS.manual) {
        const remainingSeconds = Math.ceil((HEALTH_TTLS.manual - (now - lastManualRefresh.backend)) / 1000);
  feInfo(`Backend health check throttled. Try again in ${remainingSeconds}s`);
        return;
      }
      setLastManualRefresh(prev => ({ ...prev, backend: now }));
    }

    // If cached and not forced, use cache
    if (!force) {
      const cached = readCachedHealth(HEALTH_CACHE_KEYS.backend);
      if (cached) {
        setBackendHealth(cached);
        return;
      }
    }
    try {
      setBackendHealth(prev => ({ ...prev, status: 'checking', message: 'Checking backend status...' }));
      const response = await fetch('/api/health');
      const data = await response.json();
      if (response.ok) {
        const computed = {
          status: data.status === 'healthy' ? 'healthy' : 'unhealthy',
          message: data.message || (data.status === 'healthy' ? 'Backend operational' : 'Backend issues detected'),
          lastChecked: new Date().toISOString(),
          services: data.services || {}
        };
        // Cache based on success/error with dynamic TTL
        const ttl = computed.status === 'healthy' ? HEALTH_TTLS.success : HEALTH_TTLS.error;
        writeCachedHealth(HEALTH_CACHE_KEYS.backend, computed, ttl);
        setBackendHealth(computed);
      } else {
        throw new Error(data.message || 'Backend health check failed');
      }
    } catch (error) {
      const computed = {
        status: 'error',
        message: `Backend unreachable: ${error.message}`,
        lastChecked: new Date().toISOString(),
        services: {}
      };
      writeCachedHealth(HEALTH_CACHE_KEYS.backend, computed, HEALTH_TTLS.error);
      setBackendHealth(computed);
    }
  };

  const checkProxyHealth = async (force = false) => {
    // Implement manual refresh throttling
    if (force) {
      const now = Date.now();
      if (now - lastManualRefresh.proxy < HEALTH_TTLS.manual) {
        const remainingSeconds = Math.ceil((HEALTH_TTLS.manual - (now - lastManualRefresh.proxy)) / 1000);
  feInfo(`Proxy health check throttled. Try again in ${remainingSeconds}s`);
        return;
      }
      setLastManualRefresh(prev => ({ ...prev, proxy: now }));
    }

    if (!force) {
      const cached = readCachedHealth(HEALTH_CACHE_KEYS.proxy);
      if (cached) {
        setProxyHealth(cached);
        return;
      }
    }
    try {
      setProxyHealth(prev => ({ ...prev, status: 'checking', message: 'Checking proxy status...' }));
      const response = await fetch('/api/healthz');
      const data = await response.json();
      if (response.ok) {
        const computed = {
          status: data.status === 'healthy' ? 'healthy' : 'unhealthy',
          message: data.message || (data.status === 'healthy' ? 'Proxy operational' : 'Proxy issues detected'),
          lastChecked: new Date().toISOString(),
          services: data.services || {}
        };
        const ttl = computed.status === 'healthy' ? HEALTH_TTLS.success : HEALTH_TTLS.error;
        writeCachedHealth(HEALTH_CACHE_KEYS.proxy, computed, ttl);
        setProxyHealth(computed);
      } else {
        throw new Error(data.message || 'Proxy health check failed');
      }
    } catch (error) {
      const computed = {
        status: 'error',
        message: `Proxy unreachable: ${error.message}`,
        lastChecked: new Date().toISOString(),
        services: {}
      };
      writeCachedHealth(HEALTH_CACHE_KEYS.proxy, computed, HEALTH_TTLS.error);
      setProxyHealth(computed);
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
    // Fetch provider statuses to gate selection by availability
    (async () => {
      try {
        const resp = await fetch('/api/providers');
        if (resp.ok) {
          const data = await resp.json();
          if (data && Array.isArray(data.providers)) {
            setProviders(data.providers.map(p => ({
              id: p.id,
              name: p.name || p.id,
              configured: !!p.configured,
              healthy: !!p.healthy
            })));
            // If current selection is not healthy, fallback to a healthy default
            const selected = data.providers.find(p => p.id === selectedProvider);
            const healthyDefault = data.providers.find(p => p.healthy) || data.providers.find(p => p.configured);
            if (!selected || !selected.healthy) {
              if (healthyDefault) setSelectedProvider(healthyDefault.id);
            }
          }
        }
      } catch (e) {
        // Non-fatal: leave defaults
      }
    })();
    
    // Initial health checks (will use cache if available)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  checkAllHealth();
    
    // Set up periodic health checks every 30 seconds
    const healthCheckInterval = setInterval(checkAllHealth, 30000);
    
    return () => clearInterval(healthCheckInterval);
  }, []);

  // Persist tuning to localStorage when it changes
  useEffect(() => {
    try {
      localStorage.setItem('elasticsearch_chat_tuning', JSON.stringify(tuning || {}));
    } catch {}
  }, [tuning]);

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

  // Generate tooltip content with concise errors and per-service details for backend
  const getTooltipContent = (healthStatus, systemName) => {
    const { status, message, lastChecked, services } = healthStatus || {};

    // Basic header
    let content = `${systemName}: ${status === 'healthy' ? (message || 'Healthy') : (status === 'error' ? 'Unreachable' : (message || 'Server Error'))}\nLast checked: ${formatLastChecked(lastChecked)}`;

    // For backend, if any service is not healthy, list per-service status.
    if (systemName && systemName.toLowerCase() === 'backend' && services && Object.keys(services).length > 0) {
      const entries = Object.entries(services);
      const anyUnhealthy = entries.some(([_k, v]) => {
        const s = typeof v === 'object' ? v.status : v;
        return typeof s === 'string' && !s.startsWith('healthy');
      });

      if (anyUnhealthy) {
        content += `\n\nServices:`;
        entries.forEach(([service, serviceStatus]) => {
          const s = typeof serviceStatus === 'object' ? serviceStatus.status : serviceStatus;
          const msg = typeof serviceStatus === 'object' ? (serviceStatus.message || service) : service;
          const icon = (typeof s === 'string' && s.startsWith('healthy')) ? '✅' : '❌';
          content += `\n${icon} ${service}: ${msg}`;
        });
      }
    }

    // For non-backend systems, when unhealthy or error, avoid dumping full JSON: already represented above.
    return content;
  };

  return (
    <MobileLayout
      currentView={currentView}
      setCurrentView={setCurrentView}
      backendHealth={backendHealth}
      proxyHealth={proxyHealth}
      renderHealthIcon={renderHealthIcon}
  // Pass tooltip generator so layout buttons can show details
  getTooltipContent={getTooltipContent}
      checkBackendHealth={checkBackendHealth}
      selectedProvider={selectedProvider}
      setSelectedProvider={setSelectedProvider}
      providers={providers}
    tuning={tuning}
    setTuning={setTuning}
  // Enhanced chat availability: detect via backend health.services.enhanced or message
  enhancedAvailable={Boolean((backendHealth && backendHealth.services && backendHealth.services.enhanced) || (backendHealth && backendHealth.message && backendHealth.message.toLowerCase().includes('enhanced')))}
    >
      {currentView === 'chat' && (
        <ChatInterface
          selectedProvider={selectedProvider}
          selectedIndex={selectedIndex}
          setSelectedIndex={setSelectedIndex}
          providers={providers}
      tuning={tuning}
        />
      )}
      {currentView === 'query' && (
        <QueryEditor
          selectedIndex={selectedIndex}
          setSelectedIndex={setSelectedIndex}
        />
      )}
    </MobileLayout>
  );
}

export default App;