"""
影子路由上下文 - ThreadLocal 存储当前请求的路由状态
"""

import threading
from typing import Optional


class ShadowRoutingContext:
    """
    影子路由上下文 - ThreadLocal

    存储当前线程的路由决策, 避免重复判断。
    """

    def __init__(self):
        self._local = threading.local()

    def set_shadow_enabled(self, enabled: bool) -> None:
        """设置当前线程是否启用影子路由"""
        self._local.shadow_enabled = enabled

    def is_shadow_enabled(self) -> bool:
        """当前线程是否启用影子路由"""
        return getattr(self._local, "shadow_enabled", False)

    def clear(self) -> None:
        """清除当前线程的上下文"""
        if hasattr(self._local, "shadow_enabled"):
            del self._local.shadow_enabled

    def reset_all(self) -> None:
        """重置所有线程上下文 (用于测试)"""
        self._local = threading.local()


# 全局实例
_shadow_context = ShadowRoutingContext()


def get_shadow_context() -> ShadowRoutingContext:
    """获取全局影子路由上下文"""
    return _shadow_context
