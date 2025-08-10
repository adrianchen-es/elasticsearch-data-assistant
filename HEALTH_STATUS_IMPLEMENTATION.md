# System Health Status Implementation

## Overview
Added a real-time system health status indicator to the application header that monitors the `/api/health` endpoint and provides visual feedback about system availability.

## Features Implemented

### 1. Health Status Icons
- **✅ Green CheckCircle**: All systems operational (healthy)
- **⚠️ Yellow AlertCircle**: Some services have issues (unhealthy)
- **❌ Red XCircle**: Health check failed or system error
- **🔄 Gray RefreshCw (spinning)**: Currently checking status

### 2. Status Monitoring
- **Automatic checks**: Health status checked every 30 seconds
- **Initial check**: Status checked immediately on app load
- **Manual refresh**: Click the status icon to trigger immediate check
- **Real-time updates**: UI updates automatically when status changes

### 3. Detailed Tooltip
Hover over the status icon to see detailed information:
- Current system status message
- Last check timestamp
- Individual service status with icons:
  - ✅ Service healthy
  - ❌ Service unhealthy
- Click prompt for manual refresh

### 4. Status States
- **healthy**: All services operational
- **unhealthy**: Some services have issues but system partially functional  
- **error**: Health check failed or system unavailable
- **checking**: Currently performing health check (shows spinner)

## Implementation Details

### State Management
```javascript
const [healthStatus, setHealthStatus] = useState({
  status: 'checking',
  message: 'Checking system status...',
  lastChecked: null,
  services: {}
});
```

### Health Check Function
```javascript
const checkHealthStatus = async () => {
  try {
    const response = await fetch('/api/health');
    const data = await response.json();
    // Update status based on response
  } catch (error) {
    // Handle error state
  }
};
```

### Periodic Updates
- Health check runs every 30 seconds automatically
- Uses `setInterval` with cleanup in `useEffect`
- Prevents memory leaks with proper cleanup

### Visual Design
- **Responsive text**: Status text hidden on small screens (`hidden sm:inline`)
- **Hover effects**: Button has subtle hover background
- **Smooth transitions**: Uses CSS transitions for state changes
- **Accessible tooltip**: Dark background with white text, appears on hover

## API Integration

### Expected Response Format
The health endpoint should return:
```json
{
  "status": "healthy|unhealthy|error",
  "message": "Status description",
  "services": {
    "elasticsearch": "healthy",
    "mapping_cache": "healthy",
    "ai_service": "unhealthy"
  }
}
```

### Service Status Handling
- Supports both string status (`"healthy"`) and object status (`{status: "healthy", message: "..."}`)
- Displays service-specific messages when available
- Shows appropriate icons for each service state

## User Experience

### Header Integration
- Status icon placed in the top-right corner next to provider selector
- Maintains clean header layout without clutter
- Non-intrusive but easily accessible

### Tooltip Features
- **Rich information**: Shows comprehensive system status
- **Service breakdown**: Individual service status with icons
- **Timestamp**: Shows when status was last checked
- **Interaction hint**: Tells user they can click to refresh

### Visual Feedback
- **Color coding**: Intuitive green/yellow/red status colors
- **Animation**: Spinning icon during status checks
- **Immediate updates**: UI reflects status changes instantly

## Error Handling

### Network Failures
- Gracefully handles fetch failures
- Shows error status with descriptive message
- Allows manual retry by clicking icon

### Malformed Responses
- Handles missing or invalid response data
- Provides fallback status messages
- Maintains system stability

## Performance Considerations

### Efficient Updates
- Uses 30-second intervals to balance freshness with performance
- Caches status to avoid excessive API calls
- Minimal re-renders through proper state management

### Network Optimization
- Single endpoint call for all service status
- Lightweight JSON response
- Non-blocking health checks

## Accessibility

### Screen Readers
- Proper `title` attribute for screen readers
- Semantic button element for status icon
- Clear status text descriptions

### Keyboard Navigation
- Status button is keyboard accessible
- Proper focus management
- Standard button interaction patterns

This implementation provides users with immediate visual feedback about system health while maintaining a clean, professional interface that doesn't interfere with the primary application functionality.
