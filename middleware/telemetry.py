"""
Top-level proxy module that re-exports the telemetry bootstrap from backend.middleware.telemetry
to maintain compatibility with imports like `import middleware.telemetry` found in tests and entrypoints.
"""
try:
    from backend.middleware import telemetry as _backend_telemetry
except Exception:
    _backend_telemetry = None

if _backend_telemetry is not None:
    # Re-export commonly used symbols
    try:
        setup_telemetry = _backend_telemetry.setup_telemetry
    except Exception:
        def setup_telemetry(*a, **k):
            return None
    __all__ = [name for name in dir(_backend_telemetry) if not name.startswith("_")]
else:
    # Minimal stub to avoid import errors in test environments
    def setup_telemetry(*a, **k):
        return None
    __all__ = ["setup_telemetry"]
