"""
KafkaPatcher - Kafka 消息队列插桩实现

负责拦截 Kafka 消息生产和消费并采集数据
"""

from typing import Any, Optional, Callable, Dict, List
import logging
import time
import json

import wrapt

logger = logging.getLogger(__name__)


class KafkaPatcher:
    """
    Kafka 消息队列插桩器

    支持 confluent-kafka 库的插桩:
    - Producer.produce
    - Consumer.poll
    - Consumer.consume
    """

    def __init__(
        self,
        module_name: str,
        config: Dict[str, Any],
        on_produce: Optional[Callable] = None,
        on_consume: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.module_name = module_name
        self.config = config
        self.on_produce = on_produce
        self.on_consume = on_consume
        self.on_error = on_error
        self._patched = False
        self._original_methods = {}

    def patch(self) -> bool:
        """应用 Kafka 插桩"""
        if self._patched:
            logger.warning("Kafka 已经处于插桩状态")
            return True

        try:
            from confluent_kafka import Producer, Consumer
        except ImportError:
            logger.warning("confluent-kafka 未安装，跳过插桩")
            return False

        logger.info(f"检测到 confluent-kafka 库")

        # 拦截 Producer.produce
        self._patch_producer()

        # 拦截 Consumer.poll 和 consume
        self._patch_consumer()

        self._patched = True
        logger.info("Kafka 插桩成功")
        return True

    def unpatch(self) -> bool:
        """移除 Kafka 插桩"""
        if not self._patched:
            return True

        try:
            from confluent_kafka import Producer, Consumer

            # 恢复原始方法
            for key, original in self._original_methods.items():
                if key == 'Producer.produce':
                    Producer.produce = original
                elif key == 'Consumer.poll':
                    Consumer.poll = original
                elif key == 'Consumer.consume':
                    Consumer.consume = original

            self._original_methods.clear()
            self._patched = False
            logger.info("Kafka 插桩已移除")
            return True

        except Exception as e:
            logger.exception(f"Kafka 插桩移除异常：{e}")
            return False

    def _patch_producer(self) -> None:
        """拦截 Producer.produce"""
        try:
            from confluent_kafka import Producer
        except ImportError:
            return

        self._original_methods['Producer.produce'] = Producer.produce

        @wrapt.decorator
        def produce_wrapper(wrapped, instance, args, kwargs):
            # 提取参数
            topic = args[0] if args else kwargs.get('topic', 'unknown')
            value = args[1] if len(args) > 1 else kwargs.get('value', '')
            key = args[2] if len(args) > 2 else kwargs.get('key', '')
            headers = kwargs.get('headers', None)

            # 检查是否忽略该 topic
            ignored_topics = self.config.get('ignored_topics', [])
            if topic in ignored_topics:
                return wrapped(*args, **kwargs)

            start_time = time.time()
            message_size = len(value) if value else 0

            # 提取 Trace 上下文并注入到 headers
            trace_context = self._extract_trace_context()
            if trace_context and self.config.get('inject_trace_context', True):
                headers = self._inject_trace_context(headers, trace_context)
                kwargs['headers'] = headers

            try:
                result = wrapped(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                # 后置钩子
                if self.on_produce:
                    self.on_produce(
                        topic=topic,
                        key=key,
                        value=value,
                        headers=headers,
                        message_size=message_size,
                        elapsed_ms=elapsed_ms,
                        success=True,
                        instance=instance
                    )

                return result

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000

                # 错误钩子
                if self.on_error:
                    self.on_error(
                        topic=topic,
                        key=key,
                        exception=e,
                        elapsed_ms=elapsed_ms,
                        instance=instance
                    )

                raise

        Producer.produce = produce_wrapper(Producer.produce)

    def _patch_consumer(self) -> None:
        """拦截 Consumer.poll 和 consume"""
        try:
            from confluent_kafka import Consumer
        except ImportError:
            return

        self._original_methods['Consumer.poll'] = Consumer.poll
        self._original_methods['Consumer.consume'] = Consumer.consume

        # 拦截 poll
        @wrapt.decorator
        def poll_wrapper(wrapped, instance, args, kwargs):
            start_time = time.time()
            timeout = args[0] if args else kwargs.get('timeout', 1.0)

            try:
                message = wrapped(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                if message:
                    # 提取 Trace 上下文
                    headers = message.headers()
                    trace_context = self._extract_trace_context_from_headers(headers)

                    # 消费钩子
                    if self.on_consume:
                        self.on_consume(
                            topic=message.topic(),
                            partition=message.partition(),
                            offset=message.offset(),
                            key=message.key(),
                            value=message.value(),
                            headers=headers,
                            trace_context=trace_context,
                            elapsed_ms=elapsed_ms,
                            instance=instance
                        )

                return message

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000

                if self.on_error:
                    self.on_error(
                        topic='unknown',
                        key=None,
                        exception=e,
                        elapsed_ms=elapsed_ms,
                        instance=instance
                    )

                raise

        Consumer.poll = poll_wrapper(Consumer.poll)

        # 拦截 consume (批量)
        @wrapt.decorator
        def consume_wrapper(wrapped, instance, args, kwargs):
            start_time = time.time()
            num_messages = args[0] if args else kwargs.get('num_messages', 1)
            timeout = args[1] if len(args) > 1 else kwargs.get('timeout', 1.0)

            try:
                messages = wrapped(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                # 批量消费钩子
                if self.on_consume and messages:
                    for msg in messages:
                        headers = msg.headers()
                        trace_context = self._extract_trace_context_from_headers(headers)

                        self.on_consume(
                            topic=msg.topic(),
                            partition=msg.partition(),
                            offset=msg.offset(),
                            key=msg.key(),
                            value=msg.value(),
                            headers=headers,
                            trace_context=trace_context,
                            elapsed_ms=elapsed_ms,
                            instance=instance
                        )

                return messages

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000

                if self.on_error:
                    self.on_error(
                        topic='unknown',
                        key=None,
                        exception=e,
                        elapsed_ms=elapsed_ms,
                        instance=instance
                    )

                raise

        Consumer.consume = consume_wrapper(Consumer.consume)

    def _extract_trace_context(self) -> Optional[Dict]:
        """从当前上下文提取 Trace 上下文"""
        from pylinkagent import get_agent

        agent = get_agent()
        if not agent:
            return None

        context_manager = agent.get_context_manager()
        context = context_manager.get_context()

        if context and hasattr(context, 'trace_id'):
            return {
                'trace_id': context.trace_id,
                'span_id': context.root_span.span_id if context.root_span else None
            }

        return None

    def _inject_trace_context(self, headers: Optional[List], trace_context: Dict) -> List:
        """注入 Trace 上下文到 headers"""
        if headers is None:
            headers = []

        # 转换为列表 (如果是元组)
        if isinstance(headers, tuple):
            headers = list(headers)

        # 添加 traceparent header
        if trace_context.get('trace_id'):
            traceparent = f"00-{trace_context['trace_id']}-{trace_context.get('span_id', '0' * 16)}-01"
            headers.append(('traceparent', traceparent.encode('utf-8')))

        return headers

    def _extract_trace_context_from_headers(self, headers: Optional[List]) -> Optional[Dict]:
        """从 Kafka headers 提取 Trace 上下文"""
        if not headers:
            return None

        # 查找 traceparent header
        for key, value in headers:
            if key == 'traceparent':
                if isinstance(value, bytes):
                    value = value.decode('utf-8')

                # 解析 W3C traceparent: version-trace_id-span_id-trace_flags
                parts = value.split('-')
                if len(parts) >= 4:
                    return {
                        'trace_id': parts[1],
                        'parent_span_id': parts[2],
                        'trace_flags': parts[3]
                    }

        return None
