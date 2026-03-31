"""
PyLinkAgent 全局开关

提供原子级的全局启用/禁用控制，确保在探针关闭时
能够零开销地 bypass 所有插桩逻辑
"""

import threading


class GlobalSwitch:
    """
    全局开关

    使用原子操作确保线程安全，所有插桩代码应该首先检查此开关

    Example:
        switch = GlobalSwitch()

        def instrumented_function(...):
            if not switch.is_enabled():
                return original_function(...)  # 零开销路径
            # 正常插桩逻辑
    """

    def __init__(self):
        self._enabled = False
        self._lock = threading.Lock()

    def enable(self) -> None:
        """启用探针"""
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        """禁用探针"""
        with self._lock:
            self._enabled = False

    def is_enabled(self) -> bool:
        """检查探针是否启用"""
        return self._enabled

    def toggle(self) -> bool:
        """
        切换开关状态

        Returns:
            bool: 切换后的状态
        """
        with self._lock:
            self._enabled = not self._enabled
            return self._enabled
