"""
ConfigManager - 配置管理

负责：
- 接收远程配置下发
- 配置热更新
- 配置版本管理
"""

from typing import Dict, Any, Optional
import logging
import copy

from pylinkagent.config import Config


logger = logging.getLogger(__name__)


class ConfigManager:
    """
    配置管理器

    管理配置的更新和同步
    """

    def __init__(self, config: Config):
        """
        初始化配置管理器

        Args:
            config: 当前配置
        """
        self._base_config = config
        self._config_history: list = []
        self._version = 0

    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新配置

        Args:
            updates: 配置更新项

        Returns:
            更新结果
        """
        try:
            # 保存历史版本
            self._config_history.append({
                "version": self._version,
                "config": copy.deepcopy(vars(self._base_config))
            })

            # 限制历史记录数量
            if len(self._config_history) > 10:
                self._config_history.pop(0)

            # 应用更新
            for key, value in updates.items():
                if hasattr(self._base_config, key):
                    setattr(self._base_config, key, value)
                    logger.info(f"配置更新：{key}={value}")

            self._version += 1

            return {
                "success": True,
                "version": self._version,
                "updated_keys": list(updates.keys())
            }

        except Exception as e:
            logger.exception(f"配置更新失败：{e}")
            return {"success": False, "error": str(e)}

    def get_config(self) -> Config:
        """获取当前配置"""
        return self._base_config

    def get_version(self) -> int:
        """获取当前配置版本"""
        return self._version

    def rollback(self, version: int) -> Dict[str, Any]:
        """
        回滚配置到指定版本

        Args:
            version: 目标版本

        Returns:
            回滚结果
        """
        for record in reversed(self._config_history):
            if record["version"] == version:
                # 恢复配置
                config_dict = record["config"]
                for key, value in config_dict.items():
                    if hasattr(self._base_config, key):
                        setattr(self._base_config, key, value)

                self._version = version
                logger.info(f"配置已回滚到版本 {version}")

                return {"success": True, "version": version}

        return {"success": False, "error": f"版本 {version} 不存在"}
