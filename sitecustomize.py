"""Auto bootstrap hook for Python startup.

This file is imported automatically by Python when it is present on sys.path.
It intentionally does nothing unless ``PYLINKAGENT_ENABLED=true`` is set.
"""

try:
    from pylinkagent.auto_bootstrap import auto_bootstrap

    auto_bootstrap()
except Exception:
    pass
