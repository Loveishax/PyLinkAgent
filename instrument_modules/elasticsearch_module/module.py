"""
ElasticsearchModule - Elasticsearch 搜索引擎插桩实现

负责管理 Elasticsearch 模块的插桩生命周期
"""

from typing import Dict, Any, Optional
import logging
import time

from instrument_modules.base import InstrumentModule
from .patcher import ElasticsearchPatcher


logger = logging.getLogger(__name__)


class ElasticsearchModule(InstrumentModule):
    """
    Elasticsearch 搜索引擎插桩模块

    插桩目标:
    - Elasticsearch.index (索引文档)
    - Elasticsearch.get (获取文档)
    - Elasticsearch.search (搜索)
    - Elasticsearch.update (更新文档)
    - Elasticsearch.delete (删除文档)
    - Elasticsearch.bulk (批量操作)

    采集数据:
    - 操作类型
    - 索引名称
    - 文档 ID
    - 请求/响应大小
    - 操作耗时
    """

    name = "elasticsearch"
    version = "1.0.0"
    description = "Elasticsearch 搜索引擎插桩模块"

    # 依赖的库版本
    dependencies = {"elasticsearch7": ">=7.0.0"}

    # 默认配置
    default_config = {
        "capture_body": False,
        "capture_result": False,
        "max_body_size": 1024,  # 1KB
        "ignored_indices": [".monitoring", ".security"],
        "sample_rate": 1.0,
    }

    def __init__(self):
        super().__init__()
        self._patcher: Optional[ElasticsearchPatcher] = None

    def patch(self) -> bool:
        """
        应用 Elasticsearch 插桩

        Returns:
            bool: 插桩成功返回 True
        """
        if self._active:
            logger.warning("Elasticsearch 模块已处于活动状态")
            return True

        # 1. 检查依赖
        if not self.check_dependencies():
            logger.error("Elasticsearch 依赖检查失败")
            return False

        # 2. 检查是否已安装 elasticsearch7
        try:
            from elasticsearch7 import Elasticsearch
            logger.info(f"检测到 elasticsearch7 库")
        except ImportError:
            logger.warning("elasticsearch7 未安装，跳过插桩")
            return False

        # 3. 合并配置
        config = {**self.default_config, **self._config}
        self.set_config(config)

        # 4. 创建并应用 patcher
        self._patcher = ElasticsearchPatcher(
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
                logger.info("Elasticsearch 模块插桩成功")
            else:
                logger.error("Elasticsearch 模块插桩失败")
            return success

        except Exception as e:
            logger.exception(f"Elasticsearch 模块插桩异常：{e}")
            return False

    def unpatch(self) -> bool:
        """
        移除 Elasticsearch 插桩

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
                    logger.info("Elasticsearch 模块插桩已移除")
                return success
            return True

        except Exception as e:
            logger.exception(f"Elasticsearch 模块移除插桩异常：{e}")
            return False

    def _on_request(
        self,
        operation: str,
        index: str,
        doc_id: Optional[str],
        body: Optional[Any],
        start_time: float,
        instance: Any,
        **kwargs
    ) -> None:
        """
        请求发送前的回调

        Args:
            operation: 操作类型
            index: 索引名称
            doc_id: 文档 ID
            body: 请求体
            start_time: 开始时间
            instance: Elasticsearch 实例
        """
        body_size = kwargs.get('body_size', 0)
        bulk_count = kwargs.get('bulk_count', None)

        logger.debug(f"[ES] {operation.upper()} {index}/{doc_id or ''} ({body_size} bytes)")

        # 创建 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            context_manager.start_span(
                name=f"ES {operation.upper()} {index}",
                attributes={
                    "db.system": "elasticsearch",
                    "db.operation": operation.upper(),
                    "db.elasticsearch.index": index,
                    "db.elasticsearch.doc_id": doc_id,
                    "db.elasticsearch.body_size": body_size,
                    "start_time": start_time,
                }
            )

    def _on_response(
        self,
        operation: str,
        index: str,
        doc_id: Optional[str],
        result: Any,
        elapsed_ms: float,
        instance: Any,
        **kwargs
    ) -> None:
        """
        收到响应后的回调

        Args:
            operation: 操作类型
            index: 索引名称
            doc_id: 文档 ID
            result: 响应结果
            elapsed_ms: 耗时
            instance: Elasticsearch 实例
        """
        result_size = kwargs.get('result_size', 0)
        bulk_count = kwargs.get('bulk_count', None)

        logger.debug(f"[ES] {operation.upper()} {index} -> OK ({elapsed_ms:.2f}ms)")

        # 结束 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            span = context_manager.end_span()
            if span:
                span.set_attribute("db.elasticsearch.status_code", "OK")
                span.set_attribute("db.response.time", elapsed_ms)
                if result_size:
                    span.set_attribute("db.elasticsearch.result_size", result_size)
                if bulk_count:
                    span.set_attribute("db.elasticsearch.bulk_count", bulk_count)

        # 上报数据
        self._report_data(
            operation=operation,
            index=index,
            elapsed_ms=elapsed_ms,
            result_size=result_size,
            **kwargs
        )

    def _on_error(
        self,
        operation: str,
        index: str,
        doc_id: Optional[str],
        exception: Exception,
        elapsed_ms: float,
        instance: Any
    ) -> None:
        """
        请求错误回调

        Args:
            operation: 操作类型
            index: 索引名称
            doc_id: 文档 ID
            exception: 异常对象
            elapsed_ms: 耗时
            instance: Elasticsearch 实例
        """
        logger.error(f"[ES] {operation.upper()} {index} 错误：{exception}")

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
        operation: str,
        index: str,
        elapsed_ms: float,
        **kwargs: Any
    ) -> None:
        """
        上报采集数据

        Args:
            operation: 操作类型
            index: 索引名称
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
            "type": "elasticsearch",
            "operation": operation,
            "index": index,
            "elapsed_ms": round(elapsed_ms, 2),
            **kwargs
        }

        # 上报
        reporter = agent.get_reporter()
        reporter.report(DataPoint(
            data_type=DataType.SPAN,
            data=data
        ))
