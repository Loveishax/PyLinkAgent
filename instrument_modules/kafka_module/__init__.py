"""
Kafka Instrumentation Module

Kafka 消息队列插桩模块 - 支持 confluent-kafka 库的消息拦截和 Trace 传播
"""

from .module import KafkaModule
from .patcher import KafkaPatcher

__all__ = ["KafkaModule", "KafkaPatcher"]
