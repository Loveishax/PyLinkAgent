"""
Local span event model and in-memory store.
"""

from __future__ import annotations

import os
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Deque, Dict, List, Optional


@dataclass
class SpanEvent:
    """Unified local span representation aligned to Java span semantics."""

    trace_id: str
    invoke_id: str
    parent_invoke_id: str = ""
    app_name: str = ""
    invoke_type: str = ""
    middleware_name: str = ""
    service_name: str = ""
    method_name: str = ""
    result_code: str = ""
    cluster_test: bool = False
    is_entry: bool = False
    is_server: bool = False
    up_app_name: str = ""
    remote_ip: str = ""
    port: int = 0
    request_summary: str = ""
    response_summary: str = ""
    error_message: str = ""
    agent_id: str = ""
    tenant_app_key: str = ""
    env_code: str = ""
    user_id: str = ""
    start_time_ms: int = 0
    end_time_ms: int = 0
    cost_ms: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    local_attributes: Dict[str, Any] = field(default_factory=dict)
    event_id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SpanEventStore:
    """Thread-safe recent span store for diagnostics and tests."""

    def __init__(self, maxlen: Optional[int] = None):
        store_size = maxlen or int(os.getenv("PYLINKAGENT_SPAN_STORE_SIZE", "500"))
        self._events: Deque[SpanEvent] = deque(maxlen=store_size)
        self._lock = threading.Lock()
        self._next_event_id = 1

    def append(self, event: SpanEvent) -> None:
        with self._lock:
            if event.event_id <= 0:
                event.event_id = self._next_event_id
                self._next_event_id += 1
            self._events.append(event)

    def list_recent(self, limit: Optional[int] = None) -> List[SpanEvent]:
        with self._lock:
            items = list(self._events)
        if limit is not None:
            return items[-limit:]
        return items

    def list_after(self, event_id: int, limit: Optional[int] = None) -> List[SpanEvent]:
        with self._lock:
            items = [item for item in self._events if item.event_id > event_id]
        if limit is not None:
            return items[:limit]
        return items

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._next_event_id = 1


_event_store: Optional[SpanEventStore] = None


def get_event_store() -> SpanEventStore:
    global _event_store
    if _event_store is None:
        _event_store = SpanEventStore()
    return _event_store
