"""
PyLinkAgent 生命周期管理

负责探针和模块的生命周期管理
"""

from typing import Optional, Any
import logging
from enum import Enum

from pylinkagent.config import Config
from pylinkagent.core.agent import Agent


logger = logging.getLogger(__name__)


class LifecycleState(Enum):
    """生命周期状态"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    ACTIVE = "active"
    FAILED = "failed"
    UNLOADING = "unloading"


class LifecycleManager:
    """
    生命周期管理器

    管理 Agent 和模块的完整生命周期
    """

    def __init__(self, agent: Agent, config: Config):
        """
        初始化生命周期管理器

        Args:
            agent: Agent 实例
            config: 配置对象
        """
        self.agent = agent
        self.config = config
        self._state = LifecycleState.UNLOADED
        self._running = False

    def start(self) -> bool:
        """启动生命周期管理"""
        if self._running:
            return True

        try:
            self._state = LifecycleState.LOADING
            self._running = True
            self._state = LifecycleState.ACTIVE
            logger.info("LifecycleManager 已启动")
            return True
        except Exception as e:
            logger.exception(f"LifecycleManager 启动失败：{e}")
            self._state = LifecycleState.FAILED
            return False

    def stop(self) -> bool:
        """停止生命周期管理"""
        if not self._running:
            return True

        try:
            self._state = LifecycleState.UNLOADING
            self._running = False
            self._state = LifecycleState.UNLOADED
            logger.info("LifecycleManager 已停止")
            return True
        except Exception as e:
            logger.exception(f"LifecycleManager 停止失败：{e}")
            return False

    def get_state(self) -> LifecycleState:
        """获取当前状态"""
        return self._state

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
