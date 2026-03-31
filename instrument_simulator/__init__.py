"""
instrument-simulator - PyLinkAgent 探针框架

负责：
- 插桩模块生命周期管理
- 内置命令工具
- 命令行交互界面
"""

from .simulator import Simulator
from .module_loader import ModuleLoader
from .module_registry import ModuleRegistry

__all__ = [
    "Simulator",
    "ModuleLoader",
    "ModuleRegistry",
]
