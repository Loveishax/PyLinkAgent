"""
HealthChecker - 健康检查模块

负责：
- 定期检查探针健康状态
- 上报健康状态到平台
- 自动恢复机制
"""

from typing import Dict, Any, Optional, List
import threading
import time
import logging

from pylinkagent.config import Config


logger = logging.getLogger(__name__)


class HealthChecker:
    """
    健康检查器

    定期检查探针各组件的健康状态
    """

    def __init__(self, config: Config):
        """
        初始化健康检查器

        Args:
            config: 配置对象
        """
        self.config = config
        self._running = False
        self._check_interval = 60.0  # 60 秒检查一次
        self._check_thread: Optional[threading.Thread] = None
        self._last_status: Dict[str, Any] = {}
        self._check_callbacks: List[Any] = []

    def start(self) -> None:
        """启动健康检查"""
        if self._running:
            return

        self._running = True
        self._check_thread = threading.Thread(
            target=self._check_loop,
            daemon=True,
            name="pylinkagent-healthcheck"
        )
        self._check_thread.start()
        logger.info("健康检查已启动")

    def stop(self) -> None:
        """停止健康检查"""
        self._running = False
        if self._check_thread:
            self._check_thread.join(timeout=5.0)
        logger.info("健康检查已停止")

    def add_check_callback(self, callback: Any) -> None:
        """
        添加健康检查回调

        Args:
            callback: 回调函数，签名：callback() -> Dict[str, Any]
        """
        self._check_callbacks.append(callback)

    def get_health_status(self) -> Dict[str, Any]:
        """获取当前健康状态"""
        return self._last_status

    def _check_loop(self) -> None:
        """健康检查循环"""
        while self._running:
            try:
                status = self._perform_check()
                self._last_status = status

                # 如果健康检查失败，记录警告
                if not status.get("healthy", True):
                    logger.warning(f"健康检查异常：{status}")

            except Exception as e:
                logger.error(f"健康检查失败：{e}")

            time.sleep(self._check_interval)

    def _perform_check(self) -> Dict[str, Any]:
        """
        执行健康检查

        Returns:
            健康状态字典
        """
        status = {
            "healthy": True,
            "timestamp": time.time(),
            "components": {}
        }

        # 1. 检查内存使用
        memory_status = self._check_memory()
        status["components"]["memory"] = memory_status

        # 2. 检查线程状态
        thread_status = self._check_threads()
        status["components"]["threads"] = thread_status

        # 3. 执行自定义检查回调
        for callback in self._check_callbacks:
            try:
                result = callback()
                if not result.get("healthy", True):
                    status["healthy"] = False
                status["components"][callback.__name__] = result
            except Exception as e:
                logger.error(f"检查回调失败：{e}")
                status["healthy"] = False

        return status

    def _check_memory(self) -> Dict[str, Any]:
        """检查内存使用"""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            usage_mb = memory_info.rss / 1024 / 1024
            percent = memory_info.rss / memory_info.vms if memory_info.vms > 0 else 0

            return {
                "healthy": usage_mb < 1024,  # 阈值 1GB
                "usage_mb": round(usage_mb, 2),
                "percent": round(percent * 100, 2)
            }
        except ImportError:
            return {"healthy": True, "info": "psutil not available"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def _check_threads(self) -> Dict[str, Any]:
        """检查线程状态"""
        try:
            import threading

            thread_count = threading.active_count()

            return {
                "healthy": thread_count < 100,  # 阈值 100 线程
                "count": thread_count,
                "threads": [t.name for t in threading.enumerate()]
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
