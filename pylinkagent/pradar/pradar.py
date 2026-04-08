"""
Pradar - 链路追踪核心 API

参考 Java LinkAgent 的 Pradar 类，提供分布式追踪的核心 API。
"""

import logging
from typing import Optional, Dict, Any, List
from .context import InvokeContext, ContextManager, get_context_manager
from .trace_id import TraceIdGenerator
from .switcher import PradarSwitcher


logger = logging.getLogger(__name__)


class Pradar:
    """
    Pradar - 链路追踪核心 API

    对应 Java 的 Pradar 类
    """

    # 压测标识
    CLUSTER_TEST_ON = "1"
    CLUSTER_TEST_OFF = "0"

    # 调试标识
    DEBUG_ON = "1"
    DEBUG_OFF = "0"

    # 上下文键
    TRACE_ID_KEY = "PRADAR_TRACE_ID"
    INVOKE_ID_KEY = "PRADAR_INVOKE_ID"
    USER_DATA_KEY = "PRADAR_USER_DATA"
    CLUSTER_TEST_KEY = "PRADAR_CLUSTER_TEST"
    REMOTE_APPNAME_KEY = "PRADAR_RMT_APP"  # 缩短 key 避免被截断（16 字符内）

    @classmethod
    def start_trace(
        cls,
        app_name: str,
        service_name: str,
        method_name: str,
    ) -> InvokeContext:
        """
        开始一次追踪

        Args:
            app_name: 应用名称
            service_name: 服务名称
            method_name: 方法名称

        Returns:
            InvokeContext: 根上下文
        """
        ctx_manager = get_context_manager()
        context = ctx_manager.start_trace(app_name, service_name, method_name)

        # 检查是否是压测流量
        if PradarSwitcher.is_cluster_test_enabled():
            context.set_cluster_test(True)

        logger.debug(f"Pradar.start_trace: trace_id={context.trace_id}")
        return context

    @classmethod
    def end_trace(cls) -> Optional[InvokeContext]:
        """
        结束追踪

        Returns:
            InvokeContext: 结束的上下文，无上下文时返回 None
        """
        ctx_manager = get_context_manager()
        context = ctx_manager.pop_context()

        if context:
            logger.debug(
                f"Pradar.end_trace: trace_id={context.trace_id}, "
                f"cost={context.cost_time:.2f}ms"
            )

            # 如果是根节点，清空上下文
            if context.is_root():
                ctx_manager.clear()

        return context

    @classmethod
    def has_context(cls) -> bool:
        """是否有上下文"""
        ctx_manager = get_context_manager()
        return ctx_manager.has_context()

    @classmethod
    def get_context(cls) -> Optional[InvokeContext]:
        """获取当前上下文"""
        ctx_manager = get_context_manager()
        return ctx_manager.get_current_context()

    @classmethod
    def get_trace_id(cls) -> str:
        """获取当前 Trace ID"""
        ctx_manager = get_context_manager()
        return ctx_manager.get_trace_id()

    @classmethod
    def get_invoke_id(cls) -> str:
        """获取当前 Invoke ID"""
        ctx_manager = get_context_manager()
        return ctx_manager.get_invoke_id()

    @classmethod
    def set_cluster_test(cls, is_test: bool) -> None:
        """
        设置压测标识

        Args:
            is_test: 是否是压测流量
        """
        ctx_manager = get_context_manager()
        context = ctx_manager.get_current_context()
        if context:
            context.set_cluster_test(is_test)
            logger.debug(f"Pradar.set_cluster_test: {is_test}")

    @classmethod
    def is_cluster_test(cls) -> bool:
        """当前是否是压测流量"""
        ctx_manager = get_context_manager()
        return ctx_manager.is_cluster_test()

    @classmethod
    def cluster_test(cls, cluster_test_flag: str) -> None:
        """
        设置压测标识（字符串形式）

        Args:
            cluster_test_flag: "1" 或 "0"
        """
        is_test = cluster_test_flag == cls.CLUSTER_TEST_ON
        cls.set_cluster_test(is_test)

    @classmethod
    def get_cluster_test_flag(cls) -> str:
        """获取压测标识"""
        if cls.is_cluster_test():
            return cls.CLUSTER_TEST_ON
        return cls.CLUSTER_TEST_OFF

    @classmethod
    def set_user_data(cls, key: str, value: str) -> None:
        """
        设置用户数据

        Args:
            key: 键
            value: 值
        """
        ctx_manager = get_context_manager()
        ctx_manager.set_user_data(key, value)
        logger.debug(f"Pradar.set_user_data: {key}={value}")

    @classmethod
    def get_user_data(cls, key: str) -> Optional[str]:
        """获取用户数据"""
        ctx_manager = get_context_manager()
        return ctx_manager.get_user_data(key)

    @classmethod
    def get_all_user_data(cls) -> Dict[str, str]:
        """获取所有用户数据"""
        ctx_manager = get_context_manager()
        return ctx_manager.get_all_user_data()

    @classmethod
    def remove_user_data(cls, key: str) -> None:
        """移除用户数据"""
        ctx_manager = get_context_manager()
        context = ctx_manager.get_current_context()
        if context and key in context.user_data:
            del context.user_data[key]

    @classmethod
    def set_request_params(cls, params: Dict[str, Any]) -> None:
        """设置请求参数"""
        ctx_manager = get_context_manager()
        context = ctx_manager.get_current_context()
        if context:
            context.request_params = params

    @classmethod
    def get_request_params(cls) -> Optional[Dict[str, Any]]:
        """获取请求参数"""
        ctx_manager = get_context_manager()
        context = ctx_manager.get_current_context()
        if context:
            return context.request_params
        return None

    @classmethod
    def set_response_result(cls, result: Any) -> None:
        """设置响应结果"""
        ctx_manager = get_context_manager()
        context = ctx_manager.get_current_context()
        if context:
            context.response_result = result

    @classmethod
    def get_response_result(cls) -> Optional[Any]:
        """获取响应结果"""
        ctx_manager = get_context_manager()
        context = ctx_manager.get_current_context()
        if context:
            return context.response_result
        return None

    @classmethod
    def set_error(cls, error_msg: str) -> None:
        """
        设置错误信息

        Args:
            error_msg: 错误信息
        """
        ctx_manager = get_context_manager()
        context = ctx_manager.get_current_context()
        if context:
            context.set_error(error_msg)
            logger.error(f"Pradar.set_error: {error_msg}")

    @classmethod
    def has_error(cls) -> bool:
        """是否有错误"""
        ctx_manager = get_context_manager()
        context = ctx_manager.get_current_context()
        if context:
            return context.has_error
        return False

    @classmethod
    def start_server_invoke(
        cls,
        service_name: str,
        method_name: str,
        remote_app: str = "",
    ) -> InvokeContext:
        """
        开始服务端调用

        Args:
            service_name: 服务名称
            method_name: 方法名称
            remote_app: 远程应用名称

        Returns:
            InvokeContext: 上下文
        """
        ctx_manager = get_context_manager()
        context = ctx_manager.create_context(
            service_name=service_name,
            method_name=method_name,
            middleware_type="RPC",
        )

        # 继承父上下文的 trace_id
        parent = ctx_manager.get_current_context()
        if parent:
            context.trace_id = parent.trace_id
            context.cluster_test = parent.cluster_test
            context.cluster_test_flag = parent.cluster_test_flag
            # 复制用户数据
            context.user_data = parent.user_data.copy()

        ctx_manager.push_context(context)
        context.start()

        if remote_app:
            cls.set_remote_appname(remote_app)

        return context

    @classmethod
    def end_server_invoke(cls) -> Optional[InvokeContext]:
        """结束服务端调用"""
        return cls.end_trace()

    @classmethod
    def start_client_invoke(
        cls,
        service_name: str,
        method_name: str,
        remote_app: str,
    ) -> InvokeContext:
        """
        开始客户端调用

        Args:
            service_name: 服务名称
            method_name: 方法名称
            remote_app: 远程应用名称

        Returns:
            InvokeContext: 上下文
        """
        ctx_manager = get_context_manager()
        context = ctx_manager.create_context(
            service_name=service_name,
            method_name=method_name,
            middleware_type="RPC",
        )

        # 继承父上下文的 trace_id
        parent = ctx_manager.get_current_context()
        if parent:
            context.trace_id = parent.trace_id
            context.cluster_test = parent.cluster_test
            context.cluster_test_flag = parent.cluster_test_flag
            context.user_data = parent.user_data.copy()

        ctx_manager.push_context(context)
        context.start()

        cls.set_remote_appname(remote_app)

        return context

    @classmethod
    def end_client_invoke(cls) -> Optional[InvokeContext]:
        """结束客户端调用"""
        return cls.end_trace()

    @classmethod
    def set_remote_appname(cls, remote_app: str) -> None:
        """设置远程应用名称"""
        cls.set_user_data(cls.REMOTE_APPNAME_KEY, remote_app)

    @classmethod
    def get_remote_appname(cls) -> Optional[str]:
        """获取远程应用名称"""
        return cls.get_user_data(cls.REMOTE_APPNAME_KEY)

    @classmethod
    def export_context(cls) -> Dict[str, str]:
        """
        导出上下文（用于跨进程传递）

        Returns:
            Dict[str, str]: 上下文数据
        """
        ctx_manager = get_context_manager()
        context = ctx_manager.get_current_context()

        if not context:
            return {}

        return {
            cls.TRACE_ID_KEY: context.trace_id,
            cls.INVOKE_ID_KEY: context.invoke_id,
            cls.CLUSTER_TEST_KEY: context.cluster_test_flag,
            cls.USER_DATA_KEY: str(context.user_data),
        }

    @classmethod
    def import_context(cls, context_data: Dict[str, str]) -> None:
        """
        导入上下文（用于跨进程接收）

        Args:
            context_data: 上下文数据
        """
        trace_id = context_data.get(cls.TRACE_ID_KEY, "")
        cluster_test = context_data.get(cls.CLUSTER_TEST_KEY, "")
        user_data = context_data.get(cls.USER_DATA_KEY, "")

        if trace_id:
            ctx_manager = get_context_manager()
            context = ctx_manager.create_context()
            context.trace_id = trace_id
            context.cluster_test_flag = cluster_test
            context.cluster_test = cluster_test == cls.CLUSTER_TEST_ON

            # 解析用户数据
            if user_data:
                try:
                    import ast
                    context.user_data = ast.literal_eval(user_data)
                except Exception:
                    pass

            ctx_manager.push_context(context)
            context.start()

    @classmethod
    def clear(cls) -> None:
        """清空上下文"""
        ctx_manager = get_context_manager()
        ctx_manager.clear()
        logger.debug("Pradar.clear: 上下文已清空")
