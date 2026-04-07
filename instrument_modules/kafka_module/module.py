"""
KafkaModule - Kafka 消息队列插桩实现

负责管理 Kafka 模块的插桩生命周期
"""

from typing import Dict, Any, Optional
import logging
import time

from instrument_modules.base import InstrumentModule
from .patcher import KafkaPatcher


logger = logging.getLogger(__name__)


class KafkaModule(InstrumentModule):
    """
    Kafka 消息队列插桩模块

    插桩目标:
    - Producer.produce (消息生产)
    - Consumer.poll (消息消费)
    - Consumer.consume (批量消费)

    采集数据:
    - Topic 名称
    - 消息 Key/Value
    - 消息大小
    - 生产/消费耗时
    - Trace 上下文传播
    """

    name = "kafka"
    version = "1.0.0"
    description = "Kafka 消息队列插桩模块"

    # 依赖的库版本
    dependencies = {"confluent-kafka": ">=2.0.0"}

    # 默认配置
    default_config = {
        "capture_message_value": False,
        "max_message_size": 1024,  # 1KB
        "ignored_topics": ["_internal", "_metrics"],
        "inject_trace_context": True,
        "sample_rate": 1.0,
    }

    def __init__(self):
        super().__init__()
        self._patcher: Optional[KafkaPatcher] = None

    def patch(self) -> bool:
        """
        应用 Kafka 插桩

        Returns:
            bool: 插桩成功返回 True
        """
        if self._active:
            logger.warning("Kafka 模块已处于活动状态")
            return True

        # 1. 检查依赖
        if not self.check_dependencies():
            logger.error("Kafka 依赖检查失败")
            return False

        # 2. 检查是否已安装 confluent-kafka
        try:
            from confluent_kafka import Producer, Consumer
            logger.info(f"检测到 confluent-kafka 库")
        except ImportError:
            logger.warning("confluent-kafka 未安装，跳过插桩")
            return False

        # 3. 合并配置
        config = {**self.default_config, **self._config}
        self.set_config(config)

        # 4. 创建并应用 patcher
        self._patcher = KafkaPatcher(
            module_name=self.name,
            config=config,
            on_produce=self._on_produce,
            on_consume=self._on_consume,
            on_error=self._on_error,
        )

        # 5. 执行插桩
        try:
            success = self._patcher.patch()
            if success:
                self._active = True
                logger.info("Kafka 模块插桩成功")
            else:
                logger.error("Kafka 模块插桩失败")
            return success

        except Exception as e:
            logger.exception(f"Kafka 模块插桩异常：{e}")
            return False

    def unpatch(self) -> bool:
        """
        移除 Kafka 插桩

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
                    logger.info("Kafka 模块插桩已移除")
                return success
            return True

        except Exception as e:
            logger.exception(f"Kafka 模块移除插桩异常：{e}")
            return False

    def _on_produce(
        self,
        topic: str,
        key: Any,
        value: Any,
        headers: Any,
        message_size: int,
        elapsed_ms: float,
        success: bool,
        instance: Any
    ) -> None:
        """
        消息生产后的回调

        Args:
            topic: Topic 名称
            key: 消息 Key
            value: 消息 Value
            headers: 消息 Headers
            message_size: 消息大小
            elapsed_ms: 耗时
            success: 是否成功
            instance: Producer 实例
        """
        logger.debug(f"[Kafka] Produce -> {topic} ({message_size} bytes, {elapsed_ms:.2f}ms)")

        # 创建 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            span = context_manager.end_span()
            if span:
                span.set_attribute("messaging.system", "kafka")
                span.set_attribute("messaging.destination", topic)
                span.set_attribute("messaging.kafka.message_size", message_size)
                span.set_attribute("messaging.operation", "produce")

        # 上报数据
        self._report_data(
            operation="produce",
            topic=topic,
            message_size=message_size,
            elapsed_ms=elapsed_ms,
            success=success,
        )

    def _on_consume(
        self,
        topic: str,
        partition: int,
        offset: int,
        key: Any,
        value: Any,
        headers: Any,
        trace_context: Optional[Dict],
        elapsed_ms: float,
        instance: Any
    ) -> None:
        """
        消息消费后的回调

        Args:
            topic: Topic 名称
            partition: 分区
            offset: 偏移量
            key: 消息 Key
            value: 消息 Value
            headers: 消息 Headers
            trace_context: Trace 上下文
            elapsed_ms: 耗时
            instance: Consumer 实例
        """
        logger.debug(f"[Kafka] Consume <- {topic}[{partition}]@{offset}")

        # 恢复 Trace 上下文
        if trace_context and self._config.get('inject_trace_context', True):
            from pylinkagent import get_agent
            from pylinkagent.core.context import TraceContext, Span

            agent = get_agent()
            if agent:
                context_manager = agent.get_context_manager()
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

        # 创建 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            context_manager.start_span(
                name=f"Kafka Consume {topic}",
                attributes={
                    "messaging.system": "kafka",
                    "messaging.destination": topic,
                    "messaging.kafka.partition": partition,
                    "messaging.kafka.offset": offset,
                    "messaging.operation": "consume",
                }
            )

        # 上报数据
        self._report_data(
            operation="consume",
            topic=topic,
            partition=partition,
            offset=offset,
            elapsed_ms=elapsed_ms,
        )

    def _on_error(
        self,
        topic: str,
        key: Any,
        exception: Exception,
        elapsed_ms: float,
        instance: Any
    ) -> None:
        """
        错误回调

        Args:
            topic: Topic 名称
            key: 消息 Key
            exception: 异常对象
            elapsed_ms: 耗时
            instance: Producer/Consumer 实例
        """
        logger.error(f"[Kafka] {topic} 错误：{exception}")

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
        topic: str,
        elapsed_ms: float,
        **kwargs: Any
    ) -> None:
        """
        上报采集数据

        Args:
            operation: 操作类型 (produce/consume)
            topic: Topic 名称
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
            "type": "kafka",
            "operation": operation,
            "topic": topic,
            "elapsed_ms": round(elapsed_ms, 2),
            **kwargs
        }

        # 上报
        reporter = agent.get_reporter()
        reporter.report(DataPoint(
            data_type=DataType.SPAN,
            data=data
        ))
