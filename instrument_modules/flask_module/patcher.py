"""
FlaskPatcher - Flask 框架插桩实现

负责拦截 Flask 请求处理并采集数据
"""

from typing import Any, Optional, Callable, Dict
import logging
import time
import functools

import wrapt

logger = logging.getLogger(__name__)


class FlaskPatcher:
    """
    Flask 框架插桩器

    支持 Flask 框架的插桩:
    - Flask.__call__ (WSGI 入口)
    - Flask.dispatch_request
    - Flask.handle_exception
    """

    def __init__(
        self,
        module_name: str,
        config: Dict[str, Any],
        on_request: Optional[Callable] = None,
        on_response: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.module_name = module_name
        self.config = config
        self.on_request = on_request
        self.on_response = on_response
        self.on_error = on_error
        self._patched = False
        self._original_methods = {}

    def patch(self) -> bool:
        """应用 Flask 插桩"""
        if self._patched:
            logger.warning("Flask 已经处于插桩状态")
            return True

        try:
            from flask import Flask
        except ImportError:
            logger.warning("Flask 未安装，跳过插桩")
            return False

        logger.info(f"检测到 Flask 版本")

        # 拦截 Flask.__call__ (WSGI 入口)
        self._patch_flask_call()

        # 拦截 Flask.dispatch_request (路由分发)
        self._patch_dispatch_request()

        # 拦截 Flask.handle_exception (异常处理)
        self._patch_exception_handling()

        self._patched = True
        logger.info("Flask 插桩成功")
        return True

    def unpatch(self) -> bool:
        """移除 Flask 插桩"""
        if not self._patched:
            return True

        try:
            from flask import Flask

            # 恢复原始方法
            for key, original in self._original_methods.items():
                if key == 'Flask.__call__':
                    Flask.__call__ = original
                elif key == 'Flask.dispatch_request':
                    Flask.dispatch_request = original
                elif key == 'Flask.handle_exception':
                    Flask.handle_exception = original

            self._original_methods.clear()
            self._patched = False
            logger.info("Flask 插桩已移除")
            return True

        except Exception as e:
            logger.exception(f"Flask 插桩移除异常：{e}")
            return False

    def _patch_flask_call(self) -> None:
        """拦截 Flask.__call__ (WSGI 入口)"""
        from flask import Flask

        self._original_methods['Flask.__call__'] = Flask.__call__

        @wrapt.decorator
        def flask_call_wrapper(wrapped, instance, args, kwargs):
            # WSGI 调用：__call__(environ, start_response)
            environ = args[0] if args else kwargs.get('environ', {})
            start_response = args[1] if len(args) > 1 else kwargs.get('start_response')

            # 提取请求信息
            method = environ.get('REQUEST_METHOD', 'UNKNOWN')
            path = environ.get('PATH_INFO', '/')
            query_string = environ.get('QUERY_STRING', '')
            full_path = f"{path}?{query_string}" if query_string else path

            # 检查是否忽略该路径
            ignored_paths = self.config.get('ignored_paths', ['/health', '/ready', '/metrics'])
            if any(path.startswith(ignored) for ignored in ignored_paths):
                return wrapped(*args, **kwargs)

            start_time = time.time()

            # 提取 Trace 上下文
            trace_context = self._extract_trace_context(environ)

            # 前置钩子
            if self.on_request:
                self.on_request(
                    method=method,
                    path=path,
                    full_path=full_path,
                    headers=dict(environ),
                    trace_context=trace_context,
                    start_time=start_time,
                    instance=instance
                )

            # 包装 start_response 以捕获状态码
            status_code = [None]
            original_start_response = start_response

            def wrapped_start_response(status, headers, exc_info=None):
                status_code[0] = int(status.split()[0]) if status else None
                if original_start_response:
                    return original_start_response(status, headers, exc_info)

            try:
                result = wrapped(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                # 后置钩子
                if self.on_response:
                    self.on_response(
                        method=method,
                        path=path,
                        status_code=status_code[0],
                        elapsed_ms=elapsed_ms,
                        start_time=start_time,
                        instance=instance
                    )

                return result

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000

                # 错误钩子
                if self.on_error:
                    self.on_error(
                        method=method,
                        path=path,
                        exception=e,
                        elapsed_ms=elapsed_ms,
                        start_time=start_time,
                        instance=instance
                    )

                raise

        Flask.__call__ = flask_call_wrapper(Flask.__call__)

    def _patch_dispatch_request(self) -> None:
        """拦截 Flask.dispatch_request (路由分发)"""
        from flask import Flask

        self._original_methods['Flask.dispatch_request'] = Flask.dispatch_request

        @wrapt.decorator
        def dispatch_request_wrapper(wrapped, instance, args, kwargs):
            from flask import request

            method = request.method
            path = request.path
            endpoint = request.endpoint

            start_time = time.time()

            try:
                result = wrapped(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                logger.debug(f"[Flask] {method} {path} -> {endpoint} ({elapsed_ms:.2f}ms)")

                return result

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000

                logger.error(f"[Flask] {method} {path} 错误：{e}")

                raise

        Flask.dispatch_request = dispatch_request_wrapper(Flask.dispatch_request)

    def _patch_exception_handling(self) -> None:
        """拦截 Flask.handle_exception (异常处理)"""
        from flask import Flask

        self._original_methods['Flask.handle_exception'] = Flask.handle_exception

        @wrapt.decorator
        def handle_exception_wrapper(wrapped, instance, args, kwargs):
            from flask import request

            method = request.method
            path = request.path

            # 获取异常对象
            exception = args[0] if args else kwargs.get('e')

            # 错误钩子
            if self.on_error:
                self.on_error(
                    method=method,
                    path=path,
                    exception=exception,
                    elapsed_ms=0,
                    start_time=time.time(),
                    instance=instance
                )

            return wrapped(*args, **kwargs)

        Flask.handle_exception = handle_exception_wrapper(Flask.handle_exception)

    def _extract_trace_context(self, environ: Dict) -> Optional[Dict]:
        """从 WSGI environ 提取 Trace 上下文"""
        # W3C Trace Context: traceparent
        traceparent = environ.get('HTTP_TRACEPARENT', '')

        if traceparent:
            parts = traceparent.split('-')
            if len(parts) >= 4:
                return {
                    'trace_id': parts[1],
                    'parent_span_id': parts[2],
                    'trace_flags': parts[3]
                }

        # 兼容其他 tracing 系统
        uber_trace = environ.get('HTTP_UBER_TRACE_ID', '')
        if uber_trace:
            return {'uber_trace_id': uber_trace}

        return None
