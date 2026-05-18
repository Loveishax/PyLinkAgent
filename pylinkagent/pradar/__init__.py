"""
PyLinkAgent Pradar - 链路追踪核心

参考 Java LinkAgent 的 Pradar 实现，提供分布式追踪能力。

核心功能:
- TraceID 生成与传递
- SpanID 管理
- 调用上下文管理
- 流量染色（压测标识）
- 用户数据透传
"""

from .context import InvokeContext, ContextManager
from .events import SpanEvent, get_event_store
from .exporter import SpanEventExporter, get_span_exporter
from .pradar import Pradar
from .uploader import SpanUploader
from .switcher import PradarSwitcher
from .trace_id import TraceIdGenerator
from .whitelist import WhitelistManager, WhitelistEntry, MatchType

__all__ = [
    "InvokeContext",
    "ContextManager",
    "SpanEvent",
    "get_event_store",
    "SpanEventExporter",
    "get_span_exporter",
    "SpanUploader",
    "Pradar",
    "PradarSwitcher",
    "TraceIdGenerator",
    "WhitelistManager",
    "WhitelistEntry",
    "MatchType",
]
