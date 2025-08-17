# Compatibility proxy to backend.middleware.enhanced_telemetry
from backend.middleware.enhanced_telemetry import *

# Expose module-level name for imports
__all__ = [name for name in globals() if not name.startswith('_')]
