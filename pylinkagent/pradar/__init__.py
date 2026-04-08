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
from .pradar import Pradar
from .switcher import PradarSwitcher
from .trace_id import TraceIdGenerator
from .whitelist import WhitelistManager, WhitelistEntry, MatchType

__all__ = [
    "InvokeContext",
    "ContextManager",
    "Pradar",
    "PradarSwitcher",
    "TraceIdGenerator",
    "WhitelistManager",
    "WhitelistEntry",
    "MatchType",
]
