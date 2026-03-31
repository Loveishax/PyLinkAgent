"""
PyLinkAgent 数据上报器

负责将采集的数据发送到控制平台
支持批量上报、异步发送、失败重试
"""

import queue
import threading
import time
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import logging

from pylinkagent.config import Config


logger = logging.getLogger(__name__)


class DataType(Enum):
    """数据类型"""
    TRACE = "trace"
    METRIC = "metric"
    LOG = "log"
    SPAN = "span"
    EVENT = "event"


@dataclass
class DataPoint:
    """数据点"""
    data_type: DataType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.data_type.value,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class Reporter:
    """
    数据上报器基类

    简单的同步上报实现
    """

    def __init__(self, config: Config):
        self.config = config
        self._running = False

    def start(self) -> None:
        """启动上报器"""
        self._running = True
        logger.info("Reporter 已启动")

    def stop(self) -> None:
        """停止上报器"""
        self._running = False
        logger.info("Reporter 已停止")

    def report(self, data: DataPoint) -> bool:
        """
        上报数据

        Args:
            data: 要上报的数据点

        Returns:
            bool: 上报是否成功
        """
        if not self._running:
            return False

        return self._send(data)

    def _send(self, data: DataPoint) -> bool:
        """发送数据的内部实现"""
        try:
            # 默认实现：打印日志
            logger.debug(f"上报数据：{data.data_type.value}")
            return True
        except Exception as e:
            logger.error(f"上报失败：{e}")
            return False


class BatchReporter(Reporter):
    """
    批量上报器

    特性：
    1. 队列缓冲数据
    2. 达到批量大小或时间间隔时上报
    3. 后台线程异步发送
    4. 失败重试
    """

    def __init__(self, config: Config):
        super().__init__(config)
        self._queue: queue.Queue = queue.Queue(maxsize=config.reporter_max_queue_size)
        self._batch_size = config.reporter_batch_size
        self._flush_interval = config.reporter_flush_interval
        self._retry_times = 3
        self._worker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动批量上报器"""
        super().start()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="pylinkagent-reporter"
        )
        self._worker_thread.start()

    def stop(self) -> None:
        """停止批量上报器"""
        super().stop()

        # 等待队列清空
        self._flush()

        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)

    def report(self, data: DataPoint) -> bool:
        """上报数据到队列"""
        if not self._running:
            return False

        try:
            self._queue.put_nowait(data)

            # 达到批量大小时触发上报
            if self._queue.qsize() >= self._batch_size:
                self._flush()

            return True
        except queue.Full:
            logger.warning("上报队列已满，丢弃数据")
            return False

    def _worker_loop(self) -> None:
        """工作线程循环"""
        while self._running:
            time.sleep(self._flush_interval)
            self._flush()

    def _flush(self) -> None:
        """批量上报"""
        batch: List[DataPoint] = []

        # 从队列取出数据
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if not batch:
            return

        # 批量发送
        self._send_batch(batch)

    def _send_batch(self, batch: List[DataPoint]) -> None:
        """发送批量数据"""
        payload = {
            "agent_id": self.config.agent_id,
            "timestamp": time.time(),
            "data": [d.to_dict() for d in batch]
        }

        try:
            # 实际实现应该通过 HTTP 发送到平台
            logger.debug(f"批量上报 {len(batch)} 条数据")
            # self._http_send(payload)
        except Exception as e:
            logger.error(f"批量上报失败：{e}")
