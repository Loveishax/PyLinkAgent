"""
RequestsModule - requests 库插桩实现

负责管理 requests 模块的插桩生命周期
"""

from typing import Dict, Any, Optional
import logging
import time

from instrument_modules.base import InstrumentModule
from .patcher import RequestsPatcher


logger = logging.getLogger(__name__)


class RequestsModule(InstrumentModule):
    """
    requests 库插桩模块

    插桩目标：
    - requests.Session.request
    - requests.get/post/put/delete 等方法
    - requests.adapters.HTTPAdapter.send

    采集数据：
    - HTTP 方法、URL、状态码
    - 请求/响应耗时
    - 请求/响应头（可选）
    - 请求/响应体（可选，受大小限制）
    - Trace 上下文注入
    """

    name = "requests"
    version = "1.0.0"
    description = "requests HTTP 客户端插桩模块"

    # 依赖的 requests 版本
    dependencies = {"requests": ">=2.20.0"}

    # 默认配置
    default_config = {
        "capture_headers": True,
        "capture_body": False,
        "max_body_size": 1024,  # 1KB
        "ignored_hosts": ["localhost", "127.0.0.1"],
        "inject_trace_context": True,
        "sample_rate": 1.0,
    }

    def __init__(self):
        super().__init__()
        self._patcher: Optional[RequestsPatcher] = None

    def patch(self) -> bool:
        """
        应用 requests 插桩

        Returns:
            bool: 插桩成功返回 True
        """
        if self._active:
            logger.warning("requests 模块已处于活动状态")
            return True

        # 1. 检查依赖
        if not self.check_dependencies():
            logger.error("requests 依赖检查失败")
            return False

        # 2. 检查是否已安装 requests
        try:
            import requests
            logger.info(f"检测到 requests 版本：{requests.__version__}")
        except ImportError:
            logger.warning("requests 未安装，跳过插桩")
            return False

        # 3. 合并配置
        config = {**self.default_config, **self._config}
        self.set_config(config)

        # 4. 创建并应用 patcher
        self._patcher = RequestsPatcher(
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
                logger.info("requests 模块插桩成功")
            else:
                logger.error("requests 模块插桩失败")
            return success

        except Exception as e:
            logger.exception(f"requests 模块插桩异常：{e}")
            return False

    def unpatch(self) -> bool:
        """
        移除 requests 插桩

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
                    logger.info("requests 模块插桩已移除")
                return success
            return True

        except Exception as e:
            logger.exception(f"requests 模块移除插桩异常：{e}")
            return False

    def _on_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[bytes],
        start_time: float
    ) -> None:
        """
        请求发出前的回调

        Args:
            method: HTTP 方法
            url: 请求 URL
            headers: 请求头
            body: 请求体
            start_time: 开始时间
        """
        logger.debug(f"[requests] {method} {url}")

        # 这里可以创建 Span，开始记录 trace
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            context_manager.start_span(
                name=f"HTTP {method}",
                attributes={
                    "http.method": method,
                    "http.url": url,
                    "http.request.start_time": start_time,
                }
            )

    def _on_response(
        self,
        method: str,
        url: str,
        status_code: int,
        headers: Optional[Dict[str, str]],
        body: Optional[bytes],
        elapsed_ms: float,
        start_time: float
    ) -> None:
        """
        收到响应后的回调

        Args:
            method: HTTP 方法
            url: 请求 URL
            status_code: 状态码
            headers: 响应头
            body: 响应体
            elapsed_ms: 耗时（毫秒）
            start_time: 开始时间
        """
        logger.debug(f"[requests] {method} {url} -> {status_code} ({elapsed_ms:.2f}ms)")

        # 结束 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            span = context_manager.end_span()
            if span:
                span.set_attribute("http.status_code", status_code)
                span.set_attribute("http.response.time", elapsed_ms)

        # 上报数据
        self._report_data(
            method=method,
            url=url,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
            request_headers=headers,
        )

    def _on_error(
        self,
        method: str,
        url: str,
        exception: Exception,
        elapsed_ms: float
    ) -> None:
        """
        请求错误的回调

        Args:
            method: HTTP 方法
            url: 请求 URL
            exception: 异常对象
            elapsed_ms: 耗时（毫秒）
        """
        logger.error(f"[requests] {method} {url} 错误：{exception}")

        # 记录错误 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            span = context_manager.end_span()
            if span:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(exception))

    def _report_data(
        self,
        method: str,
        url: str,
        status_code: int,
        elapsed_ms: float,
        **kwargs: Any
    ) -> None:
        """
        上报采集数据

        Args:
            method: HTTP 方法
            url: 请求 URL
            status_code: 状态码
            elapsed_ms: 耗时
            **kwargs: 其他数据
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
            "type": "http_client",
            "method": method,
            "url": url,
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
