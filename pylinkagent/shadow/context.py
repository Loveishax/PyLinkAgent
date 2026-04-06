"""
影子上下文管理

用于标识当前请求是否为压测流量，支持:
- 压测标记识别 (从 Header/上下文)
- 上下文传递 (跨线程/协程)
- 影子标记传播
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional, List
import uuid


@dataclass
class ShadowContext:
    """
    影子上下文

    用于标识当前流量是否为压测流量

    Attributes:
        is_pressure_test: 是否为压测流量
        pressure_flag: 压测标记值 (如 header 值)
        trace_id: 链路追踪 ID
        shadow_tables: 需要路由到影子表的表名列表
    """
    is_pressure_test: bool = False
    pressure_flag: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4().hex))
    shadow_tables: List[str] = field(default_factory=list)

    def mark_as_pressure(self, flag: str = "true") -> None:
        """标记为压测流量"""
        self.is_pressure_test = True
        self.pressure_flag = flag

    def is_shadow_table(self, table_name: str) -> bool:
        """判断表是否需要路由到影子表"""
        return table_name in self.shadow_tables

    def __repr__(self) -> str:
        return f"ShadowContext(is_pressure={self.is_pressure_test}, trace_id={self.trace_id[:8]})"


# 全局上下文变量 (支持 asyncio)
_shadow_context_var: ContextVar[ShadowContext] = ContextVar(
    "shadow_context",
    default=ShadowContext()
)


def get_shadow_context() -> ShadowContext:
    """获取当前影子上下文"""
    return _shadow_context_var.get()


def set_shadow_context(context: ShadowContext) -> None:
    """设置影子上下文"""
    _shadow_context_var.set(context)


def create_new_context(is_pressure: bool = False) -> ShadowContext:
    """创建新的影子上下文"""
    ctx = ShadowContext()
    if is_pressure:
        ctx.mark_as_pressure()
    _shadow_context_var.set(ctx)
    return ctx


def is_pressure_test() -> bool:
    """判断当前是否为压测流量"""
    return _shadow_context_var.get().is_pressure_test


class ShadowContextManager:
    """
    影子上下文管理器

    支持上下文切换和恢复
    """

    @staticmethod
    def enter_pressure_context(flag: str = "true") -> ShadowContext:
        """进入压测上下文"""
        ctx = ShadowContext()
        ctx.mark_as_pressure(flag)
        token = _shadow_context_var.set(ctx)
        return ctx

    @staticmethod
    def exit_pressure_context(token: any) -> None:
        """退出压测上下文"""
        try:
            _shadow_context_var.reset(token)
        except ValueError:
            # ContextVar 可能已经被重置
            pass

    @staticmethod
    def from_headers(headers: dict) -> ShadowContext:
        """
        从 HTTP Header 创建影子上下文

        支持的 Header:
        - x-pressure-test: true/false
        - x-shadow-flag: 任意压测标记
        - traceparent: W3C Trace Context
        """
        ctx = ShadowContext()

        # 检查压测标记
        pressure_header = headers.get("x-pressure-test", "").lower()
        shadow_flag = headers.get("x-shadow-flag", "")

        if pressure_header == "true" or shadow_flag:
            ctx.mark_as_pressure(shadow_flag or "true")

        # 提取 Trace ID
        traceparent = headers.get("traceparent", "")
        if traceparent and len(traceparent) >= 36:
            # W3C Trace Context 格式：version-trace_id-parent_id-trace_flags
            parts = traceparent.split("-")
            if len(parts) >= 2:
                ctx.trace_id = parts[1]

        return ctx

    @staticmethod
    def inject_to_headers(headers: dict) -> dict:
        """将影子上下文注入到 Header"""
        ctx = get_shadow_context()
        result = dict(headers)

        if ctx.is_pressure_test:
            result["x-pressure-test"] = "true"
            if ctx.pressure_flag:
                result["x-shadow-flag"] = ctx.pressure_flag

        # 注入 Trace Context
        result["traceparent"] = f"00-{ctx.trace_id}-{uuid.uuid4().hex[:16]}-01"

        return result
