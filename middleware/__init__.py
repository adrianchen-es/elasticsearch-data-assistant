# Proxy package to keep existing import paths working during tests and runtime
# Re-export modules from backend.middleware
from backend.middleware import enhanced_telemetry

__all__ = ["enhanced_telemetry"]
