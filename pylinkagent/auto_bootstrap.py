"""Utilities for automatic PyLinkAgent bootstrap."""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_AUTO_BOOTSTRAPPED = False


def _is_enabled(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def auto_bootstrap() -> bool:
    """Bootstrap the agent when environment gating enables it."""
    global _AUTO_BOOTSTRAPPED

    if _AUTO_BOOTSTRAPPED:
        return True

    if not _is_enabled(os.getenv("PYLINKAGENT_ENABLED")):
        return False

    try:
        from .bootstrap import bootstrap, is_running

        if not is_running():
            bootstrap()
        _AUTO_BOOTSTRAPPED = True
        return True
    except Exception as exc:
        logger.warning("PyLinkAgent auto bootstrap failed: %s", exc)
        return False
