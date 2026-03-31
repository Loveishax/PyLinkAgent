"""
ModuleRegistry - 模块注册表

负责管理所有可用插桩模块的注册和发现
"""

from typing import Dict, Type, Optional, Any
import logging

from instrument_modules.base import InstrumentModule


logger = logging.getLogger(__name__)


class ModuleRegistry:
    """
    模块注册表

    单例模式，全局可访问
    """

    _instance: Optional["ModuleRegistry"] = None
    _registry: Dict[str, Type[InstrumentModule]] = {}

    def __new__(cls) -> "ModuleRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, module_class: Type[InstrumentModule]) -> Type[InstrumentModule]:
        """
        注册模块类

        通常作为装饰器使用：

        @ModuleRegistry.instance().register
        class MyModule(InstrumentModule):
            name = "my_module"
            ...

        Args:
            module_class: 模块类

        Returns:
            模块类（用于装饰器）
        """
        name = getattr(module_class, "name", None)
        if not name:
            logger.error(f"模块类 {module_class.__name__} 缺少 name 属性")
            return module_class

        self._registry[name] = module_class
        logger.debug(f"注册模块：{name}")
        return module_class

    def get_module(self, name: str) -> Optional[Type[InstrumentModule]]:
        """
        获取模块类

        Args:
            name: 模块名称

        Returns:
            模块类，不存在返回 None
        """
        return self._registry.get(name)

    def list_modules(self) -> Dict[str, Type[InstrumentModule]]:
        """列出所有已注册的模块"""
        return dict(self._registry)

    def is_registered(self, name: str) -> bool:
        """检查模块是否已注册"""
        return name in self._registry

    @classmethod
    def instance(cls) -> "ModuleRegistry":
        """获取单例实例"""
        return cls()

    @classmethod
    def clear(cls) -> None:
        """清空注册表（仅用于测试）"""
        cls._registry.clear()
