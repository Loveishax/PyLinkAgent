"""
PyLinkAgent 上下文管理

使用 contextvars 实现跨线程/异步的上下文传递
支持 Trace 上下文、Span 链式调用
"""

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import threading
import uuid
import time


@dataclass
class Span:
    """
    Span 表示一个操作的时间区间

    对应 OpenTelemetry Span 概念
    """
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def set_attribute(self, key: str, value: Any) -> None:
        """设置属性"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """添加事件"""
        self.events.append({
            "name": name,
            "attributes": attributes or {},
            "timestamp": time.time()
        })

    def end(self) -> None:
        """结束 Span"""
        self.end_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "attributes": self.attributes,
            "events": self.events,
        }


@dataclass
class TraceContext:
    """
    Trace 上下文

    包含当前 Trace 的所有信息，支持 Span 栈式管理
    """
    trace_id: str
    root_span: Span
    active_span: Optional[Span] = field(default=None)
    span_stack: List[Span] = field(default_factory=list)
    baggage: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.active_span is None:
            self.active_span = self.root_span

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Span:
        """
        创建并启动新的 Span

        Args:
            name: Span 名称
            attributes: Span 属性

        Returns:
            Span: 新创建的 Span
        """
        span = Span(
            trace_id=self.trace_id,
            span_id=self._generate_span_id(),
            parent_span_id=self.active_span.span_id if self.active_span else None,
            name=name,
            attributes=attributes or {}
        )
        self.span_stack.append(span)
        self.active_span = span
        return span

    def end_span(self) -> Optional[Span]:
        """
        结束当前 Span

        Returns:
            Optional[Span]: 结束的 Span，如果栈为空返回 None
        """
        if not self.span_stack:
            return None

        span = self.span_stack.pop()
        span.end()

        if self.span_stack:
            self.active_span = self.span_stack[-1]
        else:
            self.active_span = self.root_span

        return span

    def get_current_span(self) -> Optional[Span]:
        """获取当前活跃的 Span"""
        return self.active_span

    @staticmethod
    def _generate_span_id() -> str:
        """生成 Span ID"""
        return uuid.uuid4().hex[:16]

    @staticmethod
    def _generate_trace_id() -> str:
        """生成 Trace ID"""
        return uuid.uuid4().hex[:32]

    @classmethod
    def new(cls, root_span_name: str = "root") -> "TraceContext":
        """
        创建新的 Trace 上下文

        Args:
            root_span_name: 根 Span 名称

        Returns:
            TraceContext: 新的上下文
        """
        trace_id = cls._generate_trace_id()
        root_span = Span(
            trace_id=trace_id,
            span_id=cls._generate_span_id(),
            parent_span_id=None,
            name=root_span_name
        )
        return cls(
            trace_id=trace_id,
            root_span=root_span,
            active_span=root_span
        )


class ContextManager:
    """
    上下文管理器

    使用 contextvars 管理 Trace 上下文，自动支持 asyncio
    """

    def __init__(self):
        self._context_var: ContextVar[Optional[TraceContext]] = ContextVar(
            "pylinkagent_trace_context",
            default=None
        )
        self._lock = threading.Lock()

    def initialize(self) -> None:
        """初始化上下文管理器"""
        # contextvars 在 Python 3.7+ 自动支持 asyncio
        pass

    def cleanup(self) -> None:
        """清理上下文"""
        self._context_var.set(None)

    def set_context(self, context: TraceContext) -> Token:
        """
        设置当前上下文

        Args:
            context: 要设置的上下文

        Returns:
            Token: 用于恢复上下文的 token
        """
        return self._context_var.set(context)

    def get_context(self) -> Optional[TraceContext]:
        """获取当前上下文"""
        return self._context_var.get()

    def reset_context(self, token: Token) -> None:
        """使用 token 恢复上下文"""
        self._context_var.reset(token)

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Optional[Span]:
        """
        在当前上下文中启动新的 Span

        Args:
            name: Span 名称
            attributes: Span 属性

        Returns:
            Optional[Span]: 创建的 Span，如果无上下文返回 None
        """
        context = self.get_context()
        if context is None:
            return None
        return context.start_span(name, attributes)

    def end_span(self) -> Optional[Span]:
        """
        结束当前 Span

        Returns:
            Optional[Span]: 结束的 Span
        """
        context = self.get_context()
        if context is None:
            return None
        return context.end_span()

    def create_context(self, root_span_name: str = "root") -> TraceContext:
        """
        创建新的上下文并设置为当前

        Args:
            root_span_name: 根 Span 名称

        Returns:
            TraceContext: 创建的上下文
        """
        context = TraceContext.new(root_span_name)
        self.set_context(context)
        return context
