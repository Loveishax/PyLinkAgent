"""
InvokeContext - 调用上下文

参考 Java LinkAgent 的 InvokeContext 实现，存储单次调用的追踪信息。
"""

import time
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class InvokeContext:
    """
    调用上下文 - 存储单次调用的追踪信息

    对应 Java 的 InvokeContext
    """
    # Trace ID - 全局唯一追踪标识
    trace_id: str = ""

    # Span ID - 调用节点标识（0.1.2...）
    invoke_id: str = "0"

    # 应用名称
    app_name: str = ""

    # 服务名称
    service_name: str = ""

    # 方法名称
    method_name: str = ""

    # 中间件类型（HTTP/RPC/DB/MQ 等）
    middleware_type: str = ""

    # 是否压测流量
    cluster_test: bool = False

    # 压测标识（"1" 或 "0"）
    cluster_test_flag: str = "0"

    # 用户数据（键值对透传）
    user_data: Dict[str, str] = field(default_factory=dict)

    # 本地数据（仅当前调用使用）
    local_data: Dict[str, Any] = field(default_factory=dict)

    # 开始时间
    start_time: float = field(default_factory=time.time)

    # 结束时间
    end_time: Optional[float] = None

    # 耗时（毫秒）
    cost_time: float = 0.0

    # 父级上下文（用于嵌套调用）
    parent_context: Optional['InvokeContext'] = None

    # 子上下文列表
    children: List['InvokeContext'] = field(default_factory=list)

    # 是否有错误
    has_error: bool = False

    # 错误信息
    error_msg: str = ""

    # 请求参数
    request_params: Optional[Dict[str, Any]] = None

    # 响应结果
    response_result: Optional[Any] = None

    # 常量
    INVOKE_ID_LENGTH_LIMIT = 64
    MAX_USER_DATA_SIZE = 10
    MAX_USER_DATA_KEY_SIZE = 16
    MAX_USER_DATA_VALUE_SIZE = 256

    def is_root(self) -> bool:
        """是否是根节点"""
        return self.parent_context is None

    def is_leaf(self) -> bool:
        """是否是叶子节点"""
        return len(self.children) == 0

    def get_full_invoke_id(self) -> str:
        """获取完整的调用 ID"""
        if self.is_root():
            return self.invoke_id
        parts = [self.invoke_id]
        ctx = self.parent_context
        while ctx:
            parts.insert(0, ctx.invoke_id)
            ctx = ctx.parent_context
        return ".".join(parts)

    def get_next_invoke_id(self) -> str:
        """获取下一个子节点的 invoke_id"""
        # 基于当前节点的 invoke_id 生成子节点 ID
        # 根节点 "0" 的子节点是 "0.1", "0.2", "0.3"...
        return f"{self.invoke_id}.{len(self.children) + 1}"

    def add_child(self, child: 'InvokeContext') -> None:
        """添加子上下文"""
        child.parent_context = self
        self.children.append(child)

    def set_user_data(self, key: str, value: str) -> None:
        """
        设置用户数据

        Args:
            key: 键
            value: 值
        """
        if len(self.user_data) >= self.MAX_USER_DATA_SIZE:
            return
        if len(key) > self.MAX_USER_DATA_KEY_SIZE:
            key = key[:self.MAX_USER_DATA_KEY_SIZE]
        if len(value) > self.MAX_USER_DATA_VALUE_SIZE:
            value = value[:self.MAX_USER_DATA_VALUE_SIZE]
        self.user_data[key] = value

    def get_user_data(self, key: str) -> Optional[str]:
        """获取用户数据"""
        return self.user_data.get(key)

    def set_cluster_test(self, is_test: bool) -> None:
        """设置压测标识"""
        self.cluster_test = is_test
        self.cluster_test_flag = "1" if is_test else "0"

    def is_cluster_test(self) -> bool:
        """是否是压测流量"""
        return self.cluster_test

    def start(self) -> None:
        """标记调用开始"""
        self.start_time = time.time()
        self.end_time = None

    def end(self) -> None:
        """标记调用结束"""
        self.end_time = time.time()
        self.cost_time = (self.end_time - self.start_time) * 1000  # 毫秒

    def has_error(self) -> bool:
        """是否有错误"""
        return self.has_error

    def set_error(self, error_msg: str) -> None:
        """设置错误信息"""
        self.has_error = True
        self.error_msg = error_msg

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
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
    """
    上下文管理器 - 管理调用上下文栈

    使用 ThreadLocal 存储上下文栈，支持嵌套调用
    """

    def __init__(self):
        # 每个线程独立的上下文栈
        self._local = threading.local()

    def _get_stack(self) -> List[InvokeContext]:
        """获取当前线程的上下文栈"""
        if not hasattr(self._local, 'stack'):
            self._local.stack = []
        return self._local.stack

    def create_context(
        self,
        app_name: str = "",
        service_name: str = "",
        method_name: str = "",
        middleware_type: str = "",
    ) -> InvokeContext:
        """
        创建新的调用上下文

        Args:
            app_name: 应用名称
            service_name: 服务名称
            method_name: 方法名称
            middleware_type: 中间件类型

        Returns:
            InvokeContext: 新创建的上下文
        """
        context = InvokeContext(
            app_name=app_name,
            service_name=service_name,
            method_name=method_name,
            middleware_type=middleware_type,
        )
        return context

    def start_trace(
        self,
        app_name: str,
        service_name: str,
        method_name: str,
    ) -> InvokeContext:
        """
        开始一次追踪（根节点）

        Args:
            app_name: 应用名称
            service_name: 服务名称
            method_name: 方法名称

        Returns:
            InvokeContext: 根上下文
        """
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
        """
        压入上下文到栈顶

        Args:
            context: 上下文
        """
        stack = self._get_stack()

        # 如果有父上下文，建立父子关系
        if stack:
            parent = stack[-1]
            # 先获取下一个 invoke_id（基于当前 children 数量）
            context.invoke_id = parent.get_next_invoke_id()
            # 再添加子节点
            parent.add_child(context)

        stack.append(context)

    def pop_context(self) -> Optional[InvokeContext]:
        """
        弹出栈顶上下文

        Returns:
            InvokeContext: 栈顶上下文，栈空时返回 None
        """
        stack = self._get_stack()
        if stack:
            context = stack.pop()
            context.end()
            return context
        return None

    def get_current_context(self) -> Optional[InvokeContext]:
        """获取当前栈顶上下文"""
        stack = self._get_stack()
        if stack:
            return stack[-1]
        return None

    def get_root_context(self) -> Optional[InvokeContext]:
        """获取根上下文"""
        stack = self._get_stack()
        if stack:
            return stack[0]
        return None

    def has_context(self) -> bool:
        """是否有上下文"""
        stack = self._get_stack()
        return len(stack) > 0

    def clear(self) -> None:
        """清空上下文栈"""
        self._local.stack = []

    def get_trace_id(self) -> str:
        """获取当前 Trace ID"""
        context = self.get_current_context()
        if context:
            return context.trace_id
        return ""

    def get_invoke_id(self) -> str:
        """获取当前 Invoke ID"""
        context = self.get_current_context()
        if context:
            return context.invoke_id
        return ""

    def is_cluster_test(self) -> bool:
        """当前是否是压测流量"""
        context = self.get_current_context()
        if context:
            return context.is_cluster_test()
        return False

    def set_user_data(self, key: str, value: str) -> None:
        """设置用户数据"""
        context = self.get_current_context()
        if context:
            context.set_user_data(key, value)

    def get_user_data(self, key: str) -> Optional[str]:
        """获取用户数据"""
        context = self.get_current_context()
        if context:
            return context.get_user_data(key)
        return None

    def get_all_user_data(self) -> Dict[str, str]:
        """获取所有用户数据"""
        context = self.get_current_context()
        if context:
            return context.user_data.copy()
        return {}


# 全局 ContextManager 实例
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取 ContextManager 单例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
