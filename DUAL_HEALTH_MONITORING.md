# Dual Health Monitoring Implementation

## Overview
Enhanced the health monitoring system to separately track backend and proxy health with dedicated endpoints and visual indicators.

## Architecture

### Two-Tier Health Monitoring
1. **Backend Health** (`/api/health`) - Monitors backend services via gateway proxy
2. **Proxy Health** (`/api/healthz`) - Monitors gateway proxy and its connectivity to backend

## Frontend Implementation

### Separate Health States
```javascript
// Backend health status (/api/health)
const [backendHealth, setBackendHealth] = useState({
  status: 'checking',
  message: 'Checking backend status...',
  lastChecked: null,
  services: {}
});

// Proxy health status (/api/healthz)
const [proxyHealth, setProxyHealth] = useState({
  status: 'checking',
  message: 'Checking proxy status...',
  lastChecked: null,
  services: {}
});
```

### Dual Health Icons in Header
- **Backend Status**: Server icon + health indicator
- **Proxy Status**: Globe icon + health indicator

### Visual Design
```jsx
{/* Backend Health Status */}
<Server className="h-4 w-4 text-gray-500" />
{renderHealthIcon(backendHealth)}

{/* Proxy Health Status */}
<Globe className="h-4 w-4 text-gray-500" />
{renderHealthIcon(proxyHealth)}
```

## Health Check Functions

### Backend Health Check
- **Endpoint**: `/api/health`
- **Purpose**: Check backend services (Elasticsearch, AI, Mapping Cache)
- **Response**: Detailed service status from backend

### Proxy Health Check
- **Endpoint**: `/api/healthz` 
- **Purpose**: Check proxy gateway and backend connectivity
- **Response**: Proxy status + backend reachability

### Concurrent Monitoring
```javascript
const checkAllHealth = async () => {
  await Promise.all([
    checkBackendHealth(),
    checkProxyHealth()
  ]);
};
```

## Enhanced Proxy Health Endpoint

### Gateway `/api/healthz` Features
- **Backend Connectivity**: Tests connection to backend
- **Response Time Monitoring**: Measures backend response time
- **Proxy Metrics**: Reports uptime and memory usage
- **Error Handling**: Graceful failure with detailed errors

### Response Format
```json
{
  "status": "healthy|unhealthy|error",
  "message": "Proxy gateway operational",
  "services": {
    "backend": {
      "status": "healthy",
      "message": "Backend reachable in 45ms",
      "response_time_ms": 45
    },
    "proxy": {
      "status": "healthy",
      "message": "Proxy server running",
      "uptime_seconds": 3600,
      "memory_usage_mb": 128
    }
  },
  "timestamp": "2025-08-10T...",
  "response_time_ms": 52
}
```

## Status Indicators

### Health Status Colors
- 🟢 **Green CheckCircle**: Service healthy
- 🟡 **Yellow AlertCircle**: Service has issues
- 🔴 **Red XCircle**: Service failed/unreachable
- 🔄 **Gray RefreshCw**: Currently checking (spinning)

### Service Icons
- 🖥️ **Server**: Backend services indicator
- 🌐 **Globe**: Proxy gateway indicator

## User Experience

### Independent Monitoring
- **Separate tooltips**: Each service shows detailed status
- **Individual refresh**: Click each icon to refresh that service
- **Status isolation**: Backend/proxy issues don't mask each other

### Comprehensive Information
- **Backend tooltip**: Shows Elasticsearch, AI, and cache service status
- **Proxy tooltip**: Shows gateway health and backend connectivity
- **Response times**: Displays performance metrics

### Responsive Design
- **Mobile friendly**: Service labels hidden on smaller screens (`hidden md:inline`)
- **Icon visibility**: Health indicators always visible
- **Hover states**: Smooth transitions and feedback

## Error Scenarios

### Backend Down
- **Backend icon**: Red X (backend unreachable)
- **Proxy icon**: Yellow warning (can't reach backend) or Green (proxy OK)

### Proxy Issues
- **Backend icon**: May show checking/error if proxy can't forward requests
- **Proxy icon**: Red X (proxy server issues)

### Network Issues
- **Both icons**: May show error states
- **Tooltips**: Display specific error messages
- **Retry capability**: Click to retry failed checks

## Monitoring Benefits

### Operational Visibility
1. **Service Isolation**: Quickly identify which tier has issues
2. **Performance Metrics**: Response times for both layers
3. **Historical Context**: Last checked timestamps
4. **Detailed Diagnostics**: Service-specific error messages

### Troubleshooting
1. **Layer Identification**: Know if issues are in proxy or backend
2. **Connectivity Testing**: Proxy tests backend connectivity
3. **Performance Analysis**: Response time monitoring
4. **Service Health**: Individual service status tracking

## Automatic Updates
- **30-second intervals**: Both services checked automatically
- **Concurrent checks**: Both health endpoints called in parallel
- **Independent timers**: Each service can be refreshed individually
- **State management**: Separate state prevents cross-contamination

## Implementation Details

### Gateway Enhancements
- **Backend connectivity test**: Validates upstream connection
- **Timeout handling**: 5-second timeout for backend checks  
- **Performance monitoring**: Response time tracking
- **Resource monitoring**: Memory usage and uptime reporting

### Frontend Architecture
- **Dual state management**: Separate state for each service
- **Concurrent API calls**: Parallel health checks for efficiency
- **Independent tooltips**: Service-specific information display
- **Responsive icons**: Appropriate sizing for different screens

This dual monitoring approach provides comprehensive visibility into both application layers, enabling faster issue identification and resolution while maintaining a clean, intuitive user interface.
