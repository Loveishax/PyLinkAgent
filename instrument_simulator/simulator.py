"""
Simulator - 探针核心控制器

负责管理所有插桩模块的生命周期
"""

from typing import Dict, Any, Optional, List, Type
import logging
import importlib
from pathlib import Path

from pylinkagent.config import Config
from pylinkagent.core.agent import Agent
from .module_registry import ModuleRegistry
from .module_loader import ModuleLoader


logger = logging.getLogger(__name__)


class Simulator:
    """
    探针模拟器

    管理插桩模块的加载、卸载、热更新
    """

    def __init__(self, config: Config, agent: Agent):
        """
        初始化 Simulator

        Args:
            config: 配置对象
            agent: Agent 实例
        """
        self.config = config
        self.agent = agent

        self._registry = ModuleRegistry()
        self._loader = ModuleLoader()

        # 已加载的模块实例
        self._loaded_modules: Dict[str, Any] = {}

        self._running = False

        logger.info("Simulator 初始化完成")

    def start(self) -> bool:
        """
        启动探针

        Returns:
            bool: 启动成功返回 True
        """
        if self._running:
            return True

        try:
            # 1. 加载内置模块
            self._load_builtin_modules()

            # 2. 加载用户配置的模块
            for module_name in self.config.enabled_modules:
                self.load_module(module_name)

            self._running = True
            logger.info("Simulator 启动成功")
            return True

        except Exception as e:
            logger.exception(f"Simulator 启动失败：{e}")
            return False

    def stop(self) -> bool:
        """
        停止探针

        Returns:
            bool: 停止成功返回 True
        """
        if not self._running:
            return True

        try:
            # 卸载所有模块
            self.unload_all_modules()

            self._running = False
            logger.info("Simulator 已停止")
            return True

        except Exception as e:
            logger.exception(f"Simulator 停止失败：{e}")
            return False

    def load_module(self, module_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        加载插桩模块

        Args:
            module_name: 模块名称
            config: 模块配置

        Returns:
            bool: 加载成功返回 True
        """
        if module_name in self._loaded_modules:
            logger.warning(f"模块 {module_name} 已加载")
            return True

        try:
            logger.info(f"正在加载模块：{module_name}")

            # 1. 从注册表获取模块类
            module_class = self._registry.get_module(module_name)

            if module_class is None:
                # 尝试动态加载
                module_class = self._loader.load_module_class(module_name)

            if module_class is None:
                logger.error(f"找不到模块：{module_name}")
                return False

            # 2. 创建模块实例
            module_instance = module_class()

            # 3. 设置配置
            if config:
                module_instance.set_config(config)

            # 4. 执行 patch
            if not module_instance.patch():
                logger.error(f"模块 {module_name} patch 失败")
                return False

            # 5. 注册到 Agent
            self.agent.register_module(module_name, module_instance)

            # 6. 记录已加载模块
            self._loaded_modules[module_name] = module_instance

            logger.info(f"模块 {module_name} 加载成功")
            return True

        except Exception as e:
            logger.exception(f"加载模块 {module_name} 失败：{e}")
            return False

    def unload_module(self, module_name: str) -> Dict[str, Any]:
        """
        卸载插桩模块

        Args:
            module_name: 模块名称

        Returns:
            卸载结果
        """
        if module_name not in self._loaded_modules:
            return {"success": False, "error": f"模块 {module_name} 未加载"}

        try:
            logger.info(f"正在卸载模块：{module_name}")

            module_instance = self._loaded_modules[module_name]

            # 1. 执行 unpatch
            if not module_instance.unpatch():
                logger.error(f"模块 {module_name} unpatch 失败")
                return {"success": False, "error": "unpatch failed"}

            # 2. 从 Agent 注销
            self.agent.unregister_module(module_name)

            # 3. 移除引用
            del self._loaded_modules[module_name]

            logger.info(f"模块 {module_name} 卸载成功")
            return {"success": True}

        except Exception as e:
            logger.exception(f"卸载模块 {module_name} 失败：{e}")
            return {"success": False, "error": str(e)}

    def reload_module(self, module_name: str, module_path: Optional[str] = None) -> Dict[str, Any]:
        """
        热更新模块

        Args:
            module_name: 模块名称
            module_path: 新模块文件路径（可选）

        Returns:
            更新结果
        """
        logger.info(f"正在热更新模块：{module_name}")

        # 1. 先卸载
        unload_result = self.unload_module(module_name)
        if not unload_result.get("success"):
            return unload_result

        # 2. 如果有新路径，重新加载
        if module_path:
            # 这里应该从新路径加载模块
            # 简化处理，使用默认加载
            pass

        # 3. 重新加载
        return self.load_module(module_name)

    def unload_all_modules(self) -> None:
        """卸载所有模块"""
        for module_name in list(self._loaded_modules.keys()):
            self.unload_module(module_name)

    def get_loaded_modules(self) -> List[str]:
        """获取已加载的模块列表"""
        return list(self._loaded_modules.keys())

    def get_module_status(self, module_name: str) -> Optional[Dict[str, Any]]:
        """获取模块状态"""
        if module_name not in self._loaded_modules:
            return None

        module = self._loaded_modules[module_name]
        return {
            "name": module_name,
            "version": getattr(module, "version", "unknown"),
            "enabled": getattr(module, "enabled", True),
            "config": module.get_config() if hasattr(module, "get_config") else {}
        }

    def _load_builtin_modules(self) -> None:
        """加载内置模块到注册表"""
        # 内置模块会自动注册到 ModuleRegistry
        # 这里可以动态发现 instrument_modules 目录下的模块
        pass
