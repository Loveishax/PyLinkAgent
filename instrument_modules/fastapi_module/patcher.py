"""
FastAPIPatcher - FastAPI 插桩核心逻辑

使用 wrapt + ASGI 中间件实现插桩
完整支持 asyncio 异步场景
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
    from fastapi import FastAPI
except ImportError:
    FastAPI = None  # type: ignore


logger = logging.getLogger(__name__)


class FastAPIPatcher:
    """
    FastAPI 插桩器

    插桩策略：
    1. 包装 FastAPI.__call__ 方法（ASGI 入口）

    使用中间件方式可以：
    - 捕获完整的请求/响应周期
    - 支持流式响应
    - 不影响业务逻辑
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

        if FastAPI is None:
            logger.error("FastAPI 未安装")
            return False

        try:
            # 包装 FastAPI 类，拦截 __call__
            self._patch_fastapi_call()

            self._patched = True
            logger.info("FastAPI 插桩完成")
            return True

        except Exception as e:
            logger.exception(f"FastAPI 插桩失败：{e}")
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
            # wrapt 会自动处理 unpatch
            for target, attr, original in self._original_methods:
                if original is not None:
                    setattr(target, attr, original)

            self._original_methods.clear()
            self._patched = False

            logger.info("FastAPI 插桩已移除")
            return True

        except Exception as e:
            logger.exception(f"FastAPI 移除插桩失败：{e}")
            return False

    def _patch_fastapi_call(self) -> None:
        """
        插桩 FastAPI.__call__ 方法

        这是 ASGI 应用的入口点
        """

        @wrapt.decorator
        async def call_wrapper(
            wrapped: Callable,
            instance: FastAPI,
            args: tuple,
            kwargs: dict
        ):
            """FastAPI.__call__ 包装器"""
            # ASGI 签名：async def __call__(self, scope, receive, send)
            scope = args[0] if args else kwargs.get("scope", {})
            receive = args[1] if len(args) > 1 else kwargs.get("receive")
            send = args[2] if len(args) > 2 else kwargs.get("send")

            # 前置处理
            start_time = time.time()

            # 检查是否应该忽略
            path = scope.get("path", "")
            if self._should_ignore(path):
                return await wrapped(*args, **kwargs)

            # 调用请求回调
            self.on_request(scope, receive, send, start_time)

            # 包装 send 函数以捕获响应
            response_info = {"status_code": 200, "headers": {}}

            async def wrapped_send(message):
                if message["type"] == "http.response.start":
                    response_info["status_code"] = message.get("status", 200)
                    response_info["headers"] = message.get("headers", [])
                elif message["type"] == "http.response.body":
                    pass  # 可以在这里处理响应体

                await send(message)

            # 执行原始调用
            error = None
            try:
                return await wrapped(*args, **kwargs)
            except Exception as e:
                error = e
                raise
            finally:
                elapsed_ms = (time.time() - start_time) * 1000

                if error:
                    self.on_error(scope, error, elapsed_ms)
                else:
                    # 解析响应头
                    headers_dict = {}
                    for h in response_info.get("headers", []):
                        if isinstance(h, (list, tuple)) and len(h) == 2:
                            key, value = h
                            if isinstance(key, bytes):
                                key = key.decode()
                            if isinstance(value, bytes):
                                value = value.decode()
                            headers_dict[key] = value

                    self.on_response(
                        scope=scope,
                        status_code=response_info["status_code"],
                        headers=headers_dict,
                        elapsed_ms=elapsed_ms,
                        start_time=start_time
                    )

        # 应用包装
        original = FastAPI.__call__
        wrapt.wrap_function_wrapper(FastAPI, "__call__", call_wrapper)
        self._original_methods.append((FastAPI, "__call__", original))

    def _should_ignore(self, path: str) -> bool:
        """
        检查路径是否应该被忽略

        Args:
            path: 请求路径

        Returns:
            bool: 是否忽略
        """
        ignored_paths = self.config.get("ignored_paths", [])
        if not ignored_paths:
            return False

        for ignored in ignored_paths:
            if path == ignored or path.startswith(ignored + "/"):
                return True

        return False
