"""
Kafka 影子路由拦截器

包装 KafkaProducer.__init__() / KafkaConsumer.__init__()，
在压测流量时自动路由到影子 Kafka 集群。
"""

import logging

try:
    import wrapt
    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False

logger = logging.getLogger(__name__)


class KafkaShadowInterceptor:
    """
    Kafka 影子路由拦截器

    包装 KafkaProducer 和 KafkaConsumer，压测流量时:
    - 替换 bootstrap_servers
    - 映射 topic 到影子 topic
    - 给 consumer group 加 _shadow 后缀
    """

    def __init__(self, router):
        """
        Args:
            router: ShadowRouter 实例
        """
        self.router = router
        self._original_producer = None
        self._original_consumer = None
        self._patched = False

    def patch(self) -> bool:
        """启用 Kafka 拦截"""
        if self._patched:
            return True
        if not WRAPT_AVAILABLE:
            logger.warning("wrapt 不可用，无法启用 Kafka 拦截")
            return False

        try:
            from kafka import KafkaProducer, KafkaConsumer
            self._original_producer = KafkaProducer
            self._original_consumer = KafkaConsumer

            import kafka
            kafka.KafkaProducer = self._wrapped_producer_class(self._original_producer)
            kafka.KafkaConsumer = self._wrapped_consumer_class(self._original_consumer)
            self._patched = True
            logger.info("Kafka 影子拦截已启用")
            return True
        except ImportError:
            logger.warning("kafka-python 未安装，跳过 Kafka 拦截")
            return False
        except Exception as e:
            logger.error(f"启用 Kafka 拦截失败: {e}")
            return False

    def unpatch(self) -> None:
        """恢复原始 Kafka"""
        if self._patched:
            try:
                import kafka
                if self._original_producer:
                    kafka.KafkaProducer = self._original_producer
                if self._original_consumer:
                    kafka.KafkaConsumer = self._original_consumer
                self._patched = False
                logger.info("Kafka 影子拦截已恢复")
            except ImportError:
                pass

    def _wrapped_producer_class(self, original_cls):
        """包装 KafkaProducer"""
        class ShadowKafkaProducer(original_cls):
            def __init__(self, *args, **kwargs):
                bootstrap = kwargs.get('bootstrap_servers', '')
                if isinstance(bootstrap, list):
                    bootstrap = ','.join(bootstrap)

                shadow = self._router.route_kafka(bootstrap_servers=bootstrap)
                if shadow:
                    kwargs['bootstrap_servers'] = shadow['bootstrap_servers']
                    logger.info(f"Kafka Producer 路由到影子: {shadow['bootstrap_servers']}")

                super().__init__(*args, **kwargs)

            @property
            def _router(self):
                return self.__class__._shadow_router

        ShadowKafkaProducer._shadow_router = self.router
        return ShadowKafkaProducer

    def _wrapped_consumer_class(self, original_cls):
        """包装 KafkaConsumer"""
        class ShadowKafkaConsumer(original_cls):
            def __init__(self, *args, **kwargs):
                bootstrap = kwargs.get('bootstrap_servers', '')
                if isinstance(bootstrap, list):
                    bootstrap = ','.join(bootstrap)

                topic = kwargs.get('topic', '')
                group_id = kwargs.get('group_id', '')

                shadow = self._router.route_kafka(
                    bootstrap_servers=bootstrap,
                    topic=topic,
                    group_id=group_id,
                )

                if shadow:
                    kwargs['bootstrap_servers'] = shadow['bootstrap_servers']
                    if shadow.get('topic'):
                        kwargs['topic'] = shadow['topic']
                    if shadow.get('group_id'):
                        kwargs['group_id'] = shadow['group_id']
                    logger.info(
                        f"Kafka Consumer 路由到影子: "
                        f"{shadow['bootstrap_servers']}, "
                        f"topic={shadow.get('topic', topic)}, "
                        f"group={shadow.get('group_id', group_id)}"
                    )

                super().__init__(*args, **kwargs)

            @property
            def _router(self):
                return self.__class__._shadow_router

        ShadowKafkaConsumer._shadow_router = self.router
        return ShadowKafkaConsumer
