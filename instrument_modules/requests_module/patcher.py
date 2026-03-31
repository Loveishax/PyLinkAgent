"""
RequestsPatcher - requests 插桩核心逻辑

使用 wrapt 库实现安全的函数包装
"""

from typing import Dict, Any, Optional, Callable, List, Tuple
import time
import logging

try:
    import wrapt
    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False

try:
    import requests
    from requests import Session
except ImportError:
    Session = None  # type: ignore


logger = logging.getLogger(__name__)


class RequestsPatcher:
    """
    requests 插桩器

    插桩点：
    1. Session.request - 主要入口
    2. HTTPAdapter.send - 底层发送（可选）

    不推荐插桩 requests.get/post 等快捷方法，
    因为它们最终都会调用 Session.request
    """

    def __init__(
        self,
        module_name: str,
        config: Dict[str, Any],
        on_request: Callable,
        on_response: Callable,
        on_error: Callable,
    ):
        """
        初始化插桩器

        Args:
            module_name: 模块名称
            config: 配置
            on_request: 请求回调
            on_response: 响应回调
            on_error: 错误回调
        """
        self.module_name = module_name
        self.config = config
        self.on_request = on_request
        self.on_response = on_response
        self.on_error = on_error

        self._patched: bool = False
        self._original_methods: List[Tuple] = []

    def patch(self) -> bool:
        """
        应用插桩

        Returns:
            bool: 成功返回 True
        """
        if not WRAPT_AVAILABLE:
            logger.error("wrapt 未安装，无法进行插桩")
            return False

        if Session is None:
            logger.error("requests 未安装")
            return False

        try:
            # 1. 插桩 Session.request
            self._patch_session_request()

            self._patched = True
            logger.info("requests 插桩完成")
            return True

        except Exception as e:
            logger.exception(f"requests 插桩失败：{e}")
            self.unpatch()
            return False

    def unpatch(self) -> bool:
        """
        移除插桩

        Returns:
            bool: 成功返回 True
        """
        if not self._patched:
            return True

        try:
            # wrapt 会自动处理 unpatch，只需恢复原始方法
            for target, attr, original in self._original_methods:
                if original is not None:
                    setattr(target, attr, original)

            self._original_methods.clear()
            self._patched = False

            logger.info("requests 插桩已移除")
            return True

        except Exception as e:
            logger.exception(f"requests 移除插桩失败：{e}")
            return False

    def _patch_session_request(self) -> None:
        """插桩 Session.request 方法"""

        @wrapt.decorator
        def request_wrapper(
            wrapped: Callable,
            instance: Session,
            args: tuple,
            kwargs: dict
        ):
            """Session.request 包装器"""
            # 前置处理
            start_time = time.time()

            # 提取请求信息
            method = kwargs.get("method", args[0] if args else "GET")
            url = kwargs.get("url", args[1] if len(args) > 1 else "")
            headers = kwargs.get("headers", instance.headers if instance else {})
            body = kwargs.get("data") or kwargs.get("json")

            # 检查是否应该忽略
            if self._should_ignore(url):
                return wrapped(*args, **kwargs)

            # 注入 Trace 上下文
            if self.config.get("inject_trace_context", True):
                headers = self._inject_trace_context(headers)
                kwargs["headers"] = headers

            # 调用请求回调
            self.on_request(method, url, headers, body, start_time)

            # 执行原始请求
            result = None
            error = None
            try:
                result = wrapped(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                raise
            finally:
                elapsed_ms = (time.time() - start_time) * 1000

                if error:
                    self.on_error(method, url, error, elapsed_ms)
                elif result is not None:
                    # 提取响应信息
                    response_headers = dict(result.headers) if hasattr(result, "headers") else {}
                    response_body = result.content if hasattr(result, "content") else None

                    self.on_response(
                        method=method,
                        url=url,
                        status_code=result.status_code if hasattr(result, "status_code") else 0,
                        headers=response_headers,
                        body=response_body,
                        elapsed_ms=elapsed_ms,
                        start_time=start_time
                    )

        # 应用包装
        original = Session.request
        wrapt.wrap_function_wrapper(Session, "request", request_wrapper)
        self._original_methods.append((Session, "request", original))

    def _should_ignore(self, url: str) -> bool:
        """
        检查 URL 是否应该被忽略

        Args:
            url: 请求 URL

        Returns:
            bool: 是否忽略
        """
        ignored_hosts = self.config.get("ignored_hosts", [])
        if not ignored_hosts:
            return False

        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        for host in ignored_hosts:
            if hostname == host or hostname.endswith(f".{host}"):
                return True

        return False

    def _inject_trace_context(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """
        注入 Trace 上下文到请求头

        支持 W3C Trace Context 标准

        Args:
            headers: 原始请求头

        Returns:
            注入后的请求头
        """
        from pylinkagent import get_agent

        agent = get_agent()
        if not agent:
            return headers if headers else {}

        context_manager = agent.get_context_manager()
        context = context_manager.get_context()

        if not context:
            return headers if headers else {}

        # 确保 headers 是可变的
        if isinstance(headers, (list, tuple)):
            headers = dict(headers)
        elif headers is None:
            headers = {}

        # 注入 W3C Trace-Parent
        trace_parent = f"00-{context.trace_id}-{context.root_span.span_id}-01"
        headers["traceparent"] = trace_parent

        # 也可以注入自定义头（兼容旧系统）
        headers["X-PyLinkAgent-TraceId"] = context.trace_id
        headers["X-PyLinkAgent-SpanId"] = context.root_span.span_id

        return headers
