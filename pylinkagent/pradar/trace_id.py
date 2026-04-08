"""
TraceIdGenerator - Trace ID 生成器

参考 Java LinkAgent 的 TraceIdGenerator 实现，生成全局唯一的追踪 ID。
"""

import time
import random
import socket
import threading
from typing import Optional


class TraceIdGenerator:
    """
    Trace ID 生成器

    生成格式：{时间戳}-{主机标识}-{线程 ID}-{自增序列}
    例如：20260409123456789-192168110-12345-0001
    """

    # 主机标识（IP 地址哈希）
    _host_id: Optional[str] = None

    # 自增序列
    _sequence = 0
    _sequence_lock = threading.Lock()

    # 起始时间戳（用于缩短时间戳长度）
    _start_timestamp = 1640000000000  # 2022-01-01 00:00:00 UTC

    @classmethod
    def _get_host_id(cls) -> str:
        """获取主机标识"""
        if cls._host_id is None:
            try:
                # 获取本机 IP 地址
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                # 将 IP 转换为数字标识
                parts = ip.split(".")
                cls._host_id = "".join(f"{int(p):03d}" for p in parts)
            except Exception:
                cls._host_id = "000000000000"
        return cls._host_id

    @classmethod
    def _get_thread_id(cls) -> str:
        """获取线程 ID"""
        return f"{threading.current_thread().ident % 100000:05d}"

    @classmethod
    def _get_next_sequence(cls) -> str:
        """获取下一个自增序列"""
        with cls._sequence_lock:
            cls._sequence = (cls._sequence + 1) % 10000
            return f"{cls._sequence:04d}"

    @classmethod
    def generate(cls) -> str:
        """
        生成 Trace ID

        Returns:
            str: Trace ID
        """
        # 时间戳（毫秒）
        timestamp = int(time.time() * 1000) - cls._start_timestamp
        timestamp_str = f"{timestamp:015d}"

        # 主机标识
        host_id = cls._get_host_id()

        # 线程 ID
        thread_id = cls._get_thread_id()

        # 自增序列
        sequence = cls._get_next_sequence()

        return f"{timestamp_str}{host_id}{thread_id}{sequence}"

    @classmethod
    def generate_with_prefix(cls, prefix: str = "") -> str:
        """
        生成带前缀的 Trace ID

        Args:
            prefix: 前缀

        Returns:
            str: Trace ID
        """
        trace_id = cls.generate()
        if prefix:
            return f"{prefix}{trace_id}"
        return trace_id

    @classmethod
    def generate_cluster_test(cls) -> str:
        """
        生成压测 Trace ID

        Returns:
            str: 带压测前缀的 Trace ID
        """
        return cls.generate_with_prefix("1")


def generate_trace_id() -> str:
    """生成 Trace ID 的便捷函数"""
    return TraceIdGenerator.generate()
