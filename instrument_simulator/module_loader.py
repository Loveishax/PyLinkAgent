"""
ModuleLoader - 模块加载器

负责动态加载插桩模块
"""

from typing import Optional, Type, Any
import importlib
import logging
from pathlib import Path

from instrument_modules.base import InstrumentModule


logger = logging.getLogger(__name__)


class ModuleLoader:
    """
    模块加载器

    支持：
    1. 从包导入模块
    2. 从文件路径动态加载
    3. 从 zip/wheel 加载
    """

    def __init__(self):
        self._module_paths: list = []

    def load_module_class(self, module_name: str) -> Optional[Type[InstrumentModule]]:
        """
        加载模块类

        Args:
            module_name: 模块名称（如 'requests', 'fastapi'）

        Returns:
            模块类，加载失败返回 None
        """
        try:
            # 1. 尝试从 instrument_modules 包导入
            module_path = f"instrument_modules.{module_name}_module"
            return self._import_module(module_path)

        except ImportError:
            logger.warning(f"无法从包导入模块：{module_name}")

        try:
            # 2. 尝试从已知路径导入
            for path in self._module_paths:
                result = self._load_from_path(module_name, path)
                if result:
                    return result
        except Exception as e:
            logger.error(f"从路径加载失败：{e}")

        return None

    def add_module_path(self, path: str) -> None:
        """
        添加模块搜索路径

        Args:
            path: 目录路径
        """
        if path not in self._module_paths:
            self._module_paths.append(path)

    def _import_module(self, module_path: str) -> Optional[Type[InstrumentModule]]:
        """
        从模块路径导入

        Args:
            module_path: 模块路径（如 'instrument_modules.requests_module'）

        Returns:
            模块类
        """
        try:
            module = importlib.import_module(module_path)

            # 查找模块类（通常导出为 ModuleClass）
            if hasattr(module, "ModuleClass"):
                return module.ModuleClass

            # 或者查找第一个 InstrumentModule 子类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, InstrumentModule) and attr != InstrumentModule:
                    return attr

            return None

        except ImportError as e:
            logger.error(f"导入模块失败：{e}")
            return None

    def _load_from_path(self, module_name: str, base_path: str) -> Optional[Type[InstrumentModule]]:
        """
        从文件路径加载模块

        Args:
            module_name: 模块名称
            base_path: 基础路径

        Returns:
            模块类
        """
        import sys

        # 构建模块文件路径
        module_dir = Path(base_path) / f"{module_name}_module"
        module_file = module_dir / "__init__.py"

        if not module_file.exists():
            return None

        # 使用 importlib.util 动态加载
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            f"{module_name}_module",
            str(module_file)
        )

        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[f"{module_name}_module"] = module
        spec.loader.exec_module(module)

        # 查找模块类
        if hasattr(module, "ModuleClass"):
            return module.ModuleClass

        return None
