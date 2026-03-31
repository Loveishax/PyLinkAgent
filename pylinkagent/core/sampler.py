"""
PyLinkAgent 采样器

负责决定哪些 Trace/请求应该被采样和上报
支持固定采样率和动态采样
"""

import random
import threading
from typing import Optional
import logging

from pylinkagent.config import Config


logger = logging.getLogger(__name__)


class Sampler:
    """
    采样器

    提供多种采样策略：
    1. 固定比例采样
    2. 基于 TraceID 的确定性采样
    3. 动态采样（根据负载调整）

    Example:
        sampler = Sampler(config)
        if sampler.should_sample(trace_id):
            # 记录这个 trace
    """

    def __init__(self, config: Config):
        """
        初始化采样器

        Args:
            config: 配置对象
        """
        self.config = config
        self._trace_sample_rate = config.trace_sample_rate
        self._metric_sample_rate = 1.0
        self._error_sample_rate = 1.0
        self._dynamic_sampling = config.trace_sample_rate < 1.0
        self._lock = threading.Lock()

    def should_sample(self, trace_id: Optional[str] = None, sample_type: str = "trace") -> bool:
        """
        判断是否应该采样

        Args:
            trace_id: Trace ID（用于确定性采样）
            sample_type: 采样类型 (trace/metric/error)

        Returns:
            bool: 是否采样
        """
        rate = self._get_sample_rate(sample_type)

        if rate >= 1.0:
            return True
        if rate <= 0.0:
            return False

        # 如果有 trace_id，使用确定性采样
        if trace_id and self._dynamic_sampling:
            return self._deterministic_sample(trace_id, rate)

        # 否则使用随机采样
        return random.random() < rate

    def _get_sample_rate(self, sample_type: str) -> float:
        """获取指定类型的采样率"""
        if sample_type == "trace":
            return self._trace_sample_rate
        elif sample_type == "metric":
            return self._metric_sample_rate
        elif sample_type == "error":
            return self._error_sample_rate
        return self._trace_sample_rate

    def _deterministic_sample(self, trace_id: str, rate: float) -> bool:
        """
        确定性采样

        相同的 trace_id 总是得到相同的结果
        这对于调试和追踪很重要

        Args:
            trace_id: Trace ID
            rate: 采样率

        Returns:
            bool: 是否采样
        """
        # 使用 trace_id 的哈希值决定
        hash_value = hash(trace_id) % 10000
        threshold = int(rate * 10000)
        return hash_value < threshold

    def set_sample_rate(self, rate: float, sample_type: str = "trace") -> None:
        """
        设置采样率

        Args:
            rate: 采样率 (0.0 - 1.0)
            sample_type: 采样类型
        """
        if not 0.0 <= rate <= 1.0:
            logger.warning(f"无效的采样率：{rate}")
            return

        with self._lock:
            if sample_type == "trace":
                self._trace_sample_rate = rate
            elif sample_type == "metric":
                self._metric_sample_rate = rate
            elif sample_type == "error":
                self._error_sample_rate = rate

            logger.debug(f"采样率已更新 {sample_type}={rate}")

    def get_sample_rate(self, sample_type: str = "trace") -> float:
        """获取当前采样率"""
        return self._get_sample_rate(sample_type)
