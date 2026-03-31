"""
InstrumentModule - 插桩模块基类

所有插桩模块必须继承此基类并实现必要的方法
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging


logger = logging.getLogger(__name__)


class InstrumentModule(ABC):
    """
    插桩模块抽象基类

    生命周期：
    1. __init__(): 创建实例
    2. patch(): 应用插桩
    3. [运行中...]
    4. unpatch(): 移除插桩
    5. __del__(): 销毁
    """

    # 类属性 - 子类必须覆盖
    name: str = "base_module"
    version: str = "1.0.0"
    description: str = "基础插桩模块"
    enabled: bool = True

    # 依赖的库/框架版本要求
    dependencies: Dict[str, str] = {}  # {"requests": ">=2.20.0"}

    def __init__(self):
        """初始化模块"""
        self._config: Dict[str, Any] = {}
        self._patched_targets: List[tuple] = []  # 记录已 patch 的目标
        self._active = False
        logger.debug(f"初始化模块：{self.name}")

    @abstractmethod
    def patch(self) -> bool:
        """
        应用插桩

        子类必须实现此方法来执行实际的插桩逻辑

        Returns:
            bool: 插桩成功返回 True
        """
        pass

    @abstractmethod
    def unpatch(self) -> bool:
        """
        移除插桩

        子类必须实现此方法来恢复原始代码

        Returns:
            bool: 移除成功返回 True
        """
        pass

    def reload(self) -> bool:
        """
        热更新模块

        默认实现：先 unpatch 再 patch

        Returns:
            bool: 更新成功返回 True
        """
        if self.unpatch():
            return self.patch()
        return False

    def get_config(self) -> Dict[str, Any]:
        """获取模块配置"""
        return dict(self._config)

    def set_config(self, config: Dict[str, Any]) -> None:
        """
        设置模块配置

        Args:
            config: 配置字典
        """
        self._config.update(config)
        logger.debug(f"模块 {self.name} 配置更新：{config}")

    def is_active(self) -> bool:
        """检查模块是否处于活动状态"""
        return self._active

    def check_dependencies(self) -> bool:
        """
        检查依赖是否满足

        Returns:
            bool: 依赖满足返回 True
        """
        try:
            from packaging import version
            import importlib.metadata

            for lib_name, version_spec in self.dependencies.items():
                try:
                    installed_version = importlib.metadata.version(lib_name)
                    # 简化版本检查，实际应该解析版本表达式
                    if not self._check_version(installed_version, version_spec):
                        logger.error(f"依赖不满足：{lib_name} {version_spec}, 当前 {installed_version}")
                        return False
                except importlib.metadata.PackageNotFoundError:
                    logger.error(f"缺少依赖：{lib_name}")
                    return False

            return True

        except ImportError:
            logger.warning("无法检查依赖")
            return True

    def _check_version(self, installed: str, spec: str) -> bool:
        """简单的版本检查"""
        try:
            from packaging import version, specifiers
            return version.parse(installed) in specifiers.SpecifierSet(spec)
        except Exception:
            return True  # 无法检查时默认通过

    def _record_patch(self, target: Any, attr: str, original: Any) -> None:
        """记录 patch 以便 unpatch 时恢复"""
        self._patched_targets.append((target, attr, original))

    def _before_hook(
        self,
        wrapped: Any,
        instance: Any,
        args: tuple,
        kwargs: dict
    ) -> None:
        """
        前置钩子

        在目标函数调用前执行
        """
        pass

    def _after_hook(
        self,
        wrapped: Any,
        instance: Any,
        args: tuple,
        kwargs: dict,
        result: Any
    ) -> Any:
        """
        后置钩子

        在目标函数调用后执行，可以修改返回值
        """
        return result

    def _error_hook(
        self,
        wrapped: Any,
        instance: Any,
        args: tuple,
        kwargs: dict,
        exception: Exception
    ) -> None:
        """
        错误钩子

        在目标函数抛出异常时执行
        """
        pass
