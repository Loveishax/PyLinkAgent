"""
FastAPIModule - FastAPI 框架插桩实现

负责管理 FastAPI 模块的插桩生命周期
"""

from typing import Dict, Any, Optional, Callable
import logging
import time

from instrument_modules.base import InstrumentModule
from .patcher import FastAPIPatcher


logger = logging.getLogger(__name__)


class FastAPIModule(InstrumentModule):
    """
    FastAPI 框架插桩模块

    插桩目标：
    - FastAPI.__call__ (ASGI 入口)
    - Starlette routing
    - 中间件链

    采集数据：
    - HTTP 方法、URL、路径、状态码
    - 请求/响应耗时
    - 请求/响应头（可选）
    - 请求/响应体（可选，受大小限制）
    - 异常信息
    - Trace 上下文传播
    """

    name = "fastapi"
    version = "1.0.0"
    description = "FastAPI 框架插桩模块"

    # 依赖的框架版本
    dependencies = {
        "fastapi": ">=0.68.0",
        "starlette": ">=0.14.0",
    }

    # 默认配置
    default_config = {
        "capture_headers": True,
        "capture_body": False,
        "max_body_size": 1024,
        "ignored_paths": ["/health", "/ready", "/metrics"],
        "inject_trace_context": True,
        "sample_rate": 1.0,
    }

    def __init__(self):
        super().__init__()
        self._patcher: Optional[FastAPIPatcher] = None

    def patch(self) -> bool:
        """
        应用 FastAPI 插桩

        Returns:
            bool: 插桩成功返回 True
        """
        if self._active:
            logger.warning("FastAPI 模块已处于活动状态")
            return True

        # 1. 检查依赖
        if not self.check_dependencies():
            logger.error("FastAPI 依赖检查失败")
            return False

        # 2. 检查是否已安装 FastAPI
        try:
            import fastapi
            logger.info(f"检测到 FastAPI 版本：{fastapi.__version__}")
        except ImportError:
            logger.warning("FastAPI 未安装，跳过插桩")
            return False

        # 3. 合并配置
        config = {**self.default_config, **self._config}
        self.set_config(config)

        # 4. 创建并应用 patcher
        self._patcher = FastAPIPatcher(
            module_name=self.name,
            config=config,
            on_request=self._on_request,
            on_response=self._on_response,
            on_error=self._on_error,
        )

        # 5. 执行插桩
        try:
            success = self._patcher.patch()
            if success:
                self._active = True
                logger.info("FastAPI 模块插桩成功")
            else:
                logger.error("FastAPI 模块插桩失败")
            return success

        except Exception as e:
            logger.exception(f"FastAPI 模块插桩异常：{e}")
            return False

    def unpatch(self) -> bool:
        """
        移除 FastAPI 插桩

        Returns:
            bool: 移除成功返回 True
        """
        if not self._active:
            return True

        try:
            if self._patcher:
                success = self._patcher.unpatch()
                if success:
                    self._active = False
                    logger.info("FastAPI 模块插桩已移除")
                return success
            return True

        except Exception as e:
            logger.exception(f"FastAPI 模块移除插桩异常：{e}")
            return False

    def _on_request(
        self,
        scope: Dict[str, Any],
        receive: Callable,
        send: Callable,
        start_time: float
    ) -> None:
        """
        请求进入时的回调

        Args:
            scope: ASGI scope
            receive: ASGI receive
            send: ASGI send
            start_time: 开始时间
        """
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        logger.debug(f"[FastAPI] {method} {path}")

        # 创建 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()

            # 提取上游 Trace 上下文
            trace_context = self._extract_trace_context(scope)
            if trace_context:
                context_manager.set_context(trace_context)

            # 创建新的 Span
            context_manager.start_span(
                name=f"HTTP {method} {path}",
                attributes={
                    "http.method": method,
                    "http.url": path,
                    "http.request.start_time": start_time,
                    "span.kind": "server",
                }
            )

    def _on_response(
        self,
        scope: Dict[str, Any],
        status_code: int,
        headers: Dict[str, str],
        elapsed_ms: float,
        start_time: float
    ) -> None:
        """
        响应发出后的回调

        Args:
            scope: ASGI scope
            status_code: 状态码
            headers: 响应头
            elapsed_ms: 耗时（毫秒）
            start_time: 开始时间
        """
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        logger.debug(f"[FastAPI] {method} {path} -> {status_code} ({elapsed_ms:.2f}ms)")

        # 结束 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            span = context_manager.end_span()
            if span:
                span.set_attribute("http.status_code", status_code)
                span.set_attribute("http.response.time", elapsed_ms)
                span.set_attribute("http.route", path)

        # 上报数据
        self._report_data(
            method=method,
            path=path,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
        )

    def _on_error(
        self,
        scope: Dict[str, Any],
        exception: Exception,
        elapsed_ms: float
    ) -> None:
        """
        请求处理错误的回调

        Args:
            scope: ASGI scope
            exception: 异常对象
            elapsed_ms: 耗时（毫秒）
        """
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        logger.error(f"[FastAPI] {method} {path} 错误：{exception}")

        # 记录错误 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            span = context_manager.end_span()
            if span:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(exception))
                span.set_attribute("error.type", type(exception).__name__)

    def _extract_trace_context(self, scope: Dict[str, Any]) -> Optional[Any]:
        """从 ASGI scope 提取 Trace 上下文"""
        from pylinkagent.core.context import TraceContext, Span

        headers_dict = {
            k.lower(): v.decode() if isinstance(v, bytes) else v
            for k, v in scope.get("headers", [])
        } if isinstance(scope.get("headers"), list) else {}

        # 尝试从 traceparent 头提取（W3C Trace Context）
        traceparent = headers_dict.get("traceparent", "")

        if traceparent:
            parts = traceparent.split("-")
            if len(parts) >= 4:
                trace_id = parts[1]
                parent_span_id = parts[2]

                # 创建上下文
                context = TraceContext(
                    trace_id=trace_id,
                    root_span=Span(
                        trace_id=trace_id,
                        span_id=parent_span_id,
                        parent_span_id=None,
                        name="upstream"
                    )
                )
                return context

        return None

    def _report_data(
        self,
        method: str,
        path: str,
        status_code: int,
        elapsed_ms: float,
        **kwargs: Any
    ) -> None:
        """
        上报采集数据
        """
        from pylinkagent import get_agent
        from pylinkagent.core.reporter import DataPoint, DataType

        agent = get_agent()
        if not agent:
            return

        # 采样检查
        sampler = agent.get_sampler()
        if not sampler.should_sample(sample_type="trace"):
            return

        # 构建数据
        data = {
            "module": self.name,
            "type": "http_server",
            "method": method,
            "path": path,
            "status_code": status_code,
            "elapsed_ms": round(elapsed_ms, 2),
            **kwargs
        }

        # 上报
        reporter = agent.get_reporter()
        reporter.report(DataPoint(
            data_type=DataType.SPAN,
            data=data
        ))
