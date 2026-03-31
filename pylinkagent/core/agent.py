"""
PyLinkAgent Agent 主类

负责：
1. 探针生命周期管理
2. 模块协调
3. 数据流管理
"""

from typing import Optional, Dict, Any, List
import threading
import logging
import socket
import os
import time

from pylinkagent.config import Config
from pylinkagent.core.switch import GlobalSwitch
from pylinkagent.core.context import ContextManager
from pylinkagent.core.sampler import Sampler
from pylinkagent.core.reporter import Reporter


logger = logging.getLogger(__name__)


class Agent:
    """
    PyLinkAgent 探针主类

    Agent 是探针的核心控制器，负责：
    - 启动/停止探针
    - 管理上下文和采样
    - 协调数据上报
    - 暴露控制接口给 simulator-agent

    Example:
        config = Config()
        agent = Agent(config)
        agent.start()
        # ... 探针运行中 ...
        agent.stop()
    """

    def __init__(self, config: Config):
        """
        初始化 Agent

        Args:
            config: 探针配置
        """
        self.config = config
        self.agent_id = config.agent_id or self._generate_agent_id()

        # 核心组件
        self._switch = GlobalSwitch()
        self._context_manager = ContextManager()
        self._sampler = Sampler(config)
        self._reporter = Reporter(config)

        # 状态
        self._running = False
        self._lock = threading.Lock()

        # 模块列表（由 instrument-simulator 管理）
        self._modules: Dict[str, Any] = {}

        logger.info(f"Agent 初始化完成，agent_id={self.agent_id}")

    def start(self) -> bool:
        """
        启动 Agent

        Returns:
            bool: 启动成功返回 True
        """
        with self._lock:
            if self._running:
                logger.warning("Agent 已经在运行")
                return True

            try:
                # 1. 启用全局开关
                self._switch.enable()

                # 2. 启动上报器
                self._reporter.start()

                # 3. 初始化上下文管理器
                self._context_manager.initialize()

                # 4. 标记为运行中
                self._running = True

                logger.info("Agent 启动成功")
                return True

            except Exception as e:
                logger.exception(f"Agent 启动失败：{e}")
                return False

    def stop(self) -> bool:
        """
        停止 Agent

        Returns:
            bool: 停止成功返回 True
        """
        with self._lock:
            if not self._running:
                return True

            try:
                # 1. 禁用全局开关
                self._switch.disable()

                # 2. 停止上报器
                self._reporter.stop()

                # 3. 清理上下文
                self._context_manager.cleanup()

                # 4. 卸载所有模块
                self._unload_all_modules()

                # 5. 标记为已停止
                self._running = False

                logger.info("Agent 已停止")
                return True

            except Exception as e:
                logger.exception(f"Agent 停止失败：{e}")
                return False

    def is_running(self) -> bool:
        """检查 Agent 是否正在运行"""
        return self._running

    def get_switch(self) -> GlobalSwitch:
        """获取全局开关"""
        return self._switch

    def get_context_manager(self) -> ContextManager:
        """获取上下文管理器"""
        return self._context_manager

    def get_sampler(self) -> Sampler:
        """获取采样器"""
        return self._sampler

    def get_reporter(self) -> Reporter:
        """获取上报器"""
        return self._reporter

    def register_module(self, name: str, module: Any) -> None:
        """
        注册插桩模块

        Args:
            name: 模块名称
            module: 模块实例
        """
        self._modules[name] = module
        logger.debug(f"注册模块：{name}")

    def unregister_module(self, name: str) -> bool:
        """
        注销插桩模块

        Args:
            name: 模块名称

        Returns:
            bool: 是否成功注销
        """
        if name in self._modules:
            del self._modules[name]
            logger.debug(f"注销模块：{name}")
            return True
        return False

    def get_module(self, name: str) -> Optional[Any]:
        """获取模块实例"""
        return self._modules.get(name)

    def _unload_all_modules(self) -> None:
        """卸载所有模块"""
        for name, module in list(self._modules.items()):
            try:
                if hasattr(module, "unpatch"):
                    module.unpatch()
            except Exception as e:
                logger.error(f"卸载模块 {name} 失败：{e}")
        self._modules.clear()

    def _generate_agent_id(self) -> str:
        """
        生成 Agent ID

        格式：{hostname}-{pid}-{timestamp}
        """
        hostname = socket.gethostname()
        pid = os.getpid()
        timestamp = int(time.time() * 1000)

        return f"{hostname}-{pid}-{timestamp}"

    # ========= 控制接口 =========

    def enable(self) -> None:
        """启用探针"""
        self._switch.enable()
        logger.info("探针已启用")

    def disable(self) -> None:
        """禁用探针"""
        self._switch.disable()
        logger.info("探针已禁用")

    def set_sample_rate(self, rate: float) -> None:
        """
        设置采样率

        Args:
            rate: 采样率 (0.0 - 1.0)
        """
        self._sampler.set_sample_rate(rate)
        logger.info(f"采样率已更新：{rate}")

    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        更新配置

        Args:
            updates: 配置更新项
        """
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        # 特殊处理
        if "enabled" in updates:
            if updates["enabled"]:
                self.enable()
            else:
                self.disable()

        logger.info(f"配置已更新：{updates}")
