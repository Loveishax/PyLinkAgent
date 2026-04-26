"""
Pradar invocation context storage.

This module keeps the current trace stack for the active execution context.
It uses ``contextvars`` so HTTP ingress tracing works across async request
handling and FastAPI/Starlette threadpool execution.
"""

from __future__ import annotations

import contextvars
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class InvokeContext:
    """Single invocation context node."""

    trace_id: str = ""
    invoke_id: str = "0"
    app_name: str = ""
    service_name: str = ""
    method_name: str = ""
    middleware_type: str = ""
    cluster_test: bool = False
    cluster_test_flag: str = "0"
    user_data: Dict[str, str] = field(default_factory=dict)
    local_data: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    cost_time: float = 0.0
    parent_context: Optional["InvokeContext"] = None
    children: List["InvokeContext"] = field(default_factory=list)
    has_error: bool = False
    error_msg: str = ""
    request_params: Optional[Dict[str, Any]] = None
    response_result: Optional[Any] = None

    INVOKE_ID_LENGTH_LIMIT = 64
    MAX_USER_DATA_SIZE = 10
    MAX_USER_DATA_KEY_SIZE = 16
    MAX_USER_DATA_VALUE_SIZE = 256

    def is_root(self) -> bool:
        return self.parent_context is None

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def get_full_invoke_id(self) -> str:
        if self.is_root():
            return self.invoke_id
        parts = [self.invoke_id]
        ctx = self.parent_context
        while ctx:
            parts.insert(0, ctx.invoke_id)
            ctx = ctx.parent_context
        return ".".join(parts)

    def get_next_invoke_id(self) -> str:
        return f"{self.invoke_id}.{len(self.children) + 1}"

    def add_child(self, child: "InvokeContext") -> None:
        child.parent_context = self
        self.children.append(child)

    def set_user_data(self, key: str, value: str) -> None:
        if len(self.user_data) >= self.MAX_USER_DATA_SIZE:
            return
        if len(key) > self.MAX_USER_DATA_KEY_SIZE:
            key = key[: self.MAX_USER_DATA_KEY_SIZE]
        if len(value) > self.MAX_USER_DATA_VALUE_SIZE:
            value = value[: self.MAX_USER_DATA_VALUE_SIZE]
        self.user_data[key] = value

    def get_user_data(self, key: str) -> Optional[str]:
        return self.user_data.get(key)

    def set_cluster_test(self, is_test: bool) -> None:
        self.cluster_test = is_test
        self.cluster_test_flag = "1" if is_test else "0"

    def is_cluster_test_enabled(self) -> bool:
        return self.cluster_test

    def is_cluster_test(self) -> bool:
        return self.cluster_test

    def start(self) -> None:
        self.start_time = time.time()
        self.end_time = None

    def end(self) -> None:
        self.end_time = time.time()
        self.cost_time = (self.end_time - self.start_time) * 1000

    def set_error(self, error_msg: str) -> None:
        self.has_error = True
        self.error_msg = error_msg

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "invoke_id": self.invoke_id,
            "app_name": self.app_name,
            "service_name": self.service_name,
            "method_name": self.method_name,
            "middleware_type": self.middleware_type,
            "cluster_test": self.cluster_test,
            "cluster_test_flag": self.cluster_test_flag,
            "user_data": self.user_data,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "cost_time": self.cost_time,
            "has_error": self.has_error,
            "error_msg": self.error_msg,
        }


class ContextManager:
    """Manage the current invocation stack for the active execution context."""

    def __init__(self):
        self._stack_var: contextvars.ContextVar[Tuple[InvokeContext, ...]] = (
            contextvars.ContextVar("pylinkagent_pradar_stack", default=())
        )

    def _get_stack(self) -> Tuple[InvokeContext, ...]:
        return self._stack_var.get()

    def _set_stack(self, stack: Tuple[InvokeContext, ...]) -> None:
        self._stack_var.set(stack)

    def create_context(
        self,
        app_name: str = "",
        service_name: str = "",
        method_name: str = "",
        middleware_type: str = "",
    ) -> InvokeContext:
        return InvokeContext(
            app_name=app_name,
            service_name=service_name,
            method_name=method_name,
            middleware_type=middleware_type,
        )

    def start_trace(
        self,
        app_name: str,
        service_name: str,
        method_name: str,
    ) -> InvokeContext:
        from .trace_id import TraceIdGenerator

        context = self.create_context(
            app_name=app_name,
            service_name=service_name,
            method_name=method_name,
        )
        context.trace_id = TraceIdGenerator.generate()
        context.invoke_id = "0"
        context.start()
        self.push_context(context)
        return context

    def push_context(self, context: InvokeContext) -> None:
        stack = self._get_stack()
        if stack:
            parent = stack[-1]
            context.invoke_id = parent.get_next_invoke_id()
            parent.add_child(context)
        self._set_stack(stack + (context,))

    def pop_context(self) -> Optional[InvokeContext]:
        stack = self._get_stack()
        if not stack:
            return None
        context = stack[-1]
        self._set_stack(stack[:-1])
        context.end()
        return context

    def get_current_context(self) -> Optional[InvokeContext]:
        stack = self._get_stack()
        if stack:
            return stack[-1]
        return None

    def get_root_context(self) -> Optional[InvokeContext]:
        stack = self._get_stack()
        if stack:
            return stack[0]
        return None

    def has_context(self) -> bool:
        return bool(self._get_stack())

    def clear(self) -> None:
        self._set_stack(())

    def get_trace_id(self) -> str:
        context = self.get_current_context()
        if context:
            return context.trace_id
        return ""

    def get_invoke_id(self) -> str:
        context = self.get_current_context()
        if context:
            return context.invoke_id
        return ""

    def is_cluster_test(self) -> bool:
        context = self.get_current_context()
        if context:
            return context.is_cluster_test_enabled()
        return False

    def set_user_data(self, key: str, value: str) -> None:
        context = self.get_current_context()
        if context:
            context.set_user_data(key, value)

    def get_user_data(self, key: str) -> Optional[str]:
        context = self.get_current_context()
        if context:
            return context.get_user_data(key)
        return None

    def get_all_user_data(self) -> Dict[str, str]:
        context = self.get_current_context()
        if context:
            return context.user_data.copy()
        return {}


_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
