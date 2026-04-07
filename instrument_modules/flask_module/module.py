"""
FlaskModule - Flask 框架插桩实现

负责管理 Flask 模块的插桩生命周期
"""

from typing import Dict, Any, Optional
import logging
import time

from instrument_modules.base import InstrumentModule
from .patcher import FlaskPatcher


logger = logging.getLogger(__name__)


class FlaskModule(InstrumentModule):
    """
    Flask 框架插桩模块

    插桩目标：
    - Flask.__call__ (WSGI 入口)
    - Flask.dispatch_request (路由分发)
    - Flask.handle_exception (异常处理)

    采集数据：
    - HTTP 方法、路径、状态码
    - 请求/响应耗时
    - 端点信息
    - 异常信息
    - Trace 上下文传播
    """

    name = "flask"
    version = "1.0.0"
    description = "Flask 框架插桩模块"

    # 依赖的框架版本
    dependencies = {
        "flask": ">=2.0.0",
    }

    # 默认配置
    default_config = {
        "capture_headers": True,
        "capture_body": False,
        "max_body_size": 1024,  # 1KB
        "ignored_paths": ["/health", "/ready", "/metrics", "/favicon.ico"],
        "inject_trace_context": True,
        "sample_rate": 1.0,
    }

    def __init__(self):
        super().__init__()
        self._patcher: Optional[FlaskPatcher] = None

    def patch(self) -> bool:
        """
        应用 Flask 插桩

        Returns:
            bool: 插桩成功返回 True
        """
        if self._active:
            logger.warning("Flask 模块已处于活动状态")
            return True

        # 1. 检查依赖
        if not self.check_dependencies():
            logger.error("Flask 依赖检查失败")
            return False

        # 2. 检查是否已安装 Flask
        try:
            from flask import Flask
            import flask
            logger.info(f"检测到 Flask 版本：{flask.__version__}")
        except ImportError:
            logger.warning("Flask 未安装，跳过插桩")
            return False

        # 3. 合并配置
        config = {**self.default_config, **self._config}
        self.set_config(config)

        # 4. 创建并应用 patcher
        self._patcher = FlaskPatcher(
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
                logger.info("Flask 模块插桩成功")
            else:
                logger.error("Flask 模块插桩失败")
            return success

        except Exception as e:
            logger.exception(f"Flask 模块插桩异常：{e}")
            return False

    def unpatch(self) -> bool:
        """
        移除 Flask 插桩

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
                    logger.info("Flask 模块插桩已移除")
                return success
            return True

        except Exception as e:
            logger.exception(f"Flask 模块移除插桩异常：{e}")
            return False

    def _on_request(
        self,
        method: str,
        path: str,
        full_path: str,
        headers: Dict,
        trace_context: Optional[Dict],
        start_time: float,
        instance: Any
    ) -> None:
        """
        请求进入时的回调

        Args:
            method: HTTP 方法
            path: 请求路径
            full_path: 完整路径（含查询参数）
            headers: 请求头
            trace_context: Trace 上下文
            start_time: 开始时间
            instance: Flask 应用实例
        """
        logger.debug(f"[Flask] {method} {path}")

        # 创建 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()

            # 恢复 Trace 上下文
            if trace_context and self._config.get('inject_trace_context', True):
                from pylinkagent.core.context import TraceContext, Span
                context = TraceContext(
                    trace_id=trace_context.get('trace_id', ''),
                    root_span=Span(
                        trace_id=trace_context.get('trace_id', ''),
                        span_id=trace_context.get('parent_span_id', ''),
                        parent_span_id=None,
                        name="upstream"
                    )
                )
                context_manager.set_context(context)

            # 创建新的 Span
            context_manager.start_span(
                name=f"HTTP {method} {path}",
                attributes={
                    "http.method": method,
                    "http.url": full_path,
                    "http.route": path,
                    "http.request.start_time": start_time,
                    "span.kind": "server",
                    "framework.name": "flask",
                }
            )

    def _on_response(
        self,
        method: str,
        path: str,
        status_code: int,
        elapsed_ms: float,
        start_time: float,
        instance: Any
    ) -> None:
        """
        响应发出后的回调

        Args:
            method: HTTP 方法
            path: 请求路径
            status_code: 状态码
            elapsed_ms: 耗时（毫秒）
            start_time: 开始时间
            instance: Flask 应用实例
        """
        logger.debug(f"[Flask] {method} {path} -> {status_code} ({elapsed_ms:.2f}ms)")

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
        method: str,
        path: str,
        exception: Exception,
        elapsed_ms: float,
        start_time: float,
        instance: Any
    ) -> None:
        """
        请求处理错误的回调

        Args:
            method: HTTP 方法
            path: 请求路径
            exception: 异常对象
            elapsed_ms: 耗时（毫秒）
            start_time: 开始时间
            instance: Flask 应用实例
        """
        logger.error(f"[Flask] {method} {path} 错误：{exception}")

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
