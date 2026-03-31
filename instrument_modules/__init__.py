"""
instrument-modules - 可插拔插桩模块集合

包含：
- base: 模块基类
- 各种中间件/框架的插桩模块

新增模块请参考 module-development.md
"""

from .base import InstrumentModule

__all__ = ["InstrumentModule"]
