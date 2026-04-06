"""
影子路由器

核心路由逻辑：
- 根据流量标记决定是否使用影子库
- 表名映射和 SQL 重写
- 数据库连接切换
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass
import logging

from .config import ShadowDatabaseConfig, ShadowConfigManager
from .context import get_shadow_context, is_pressure_test, ShadowContext

logger = logging.getLogger(__name__)


@dataclass
class DataSourceMeta:
    """数据源元信息"""
    url: str
    username: str
    driver: str
    shadow_url: Optional[str] = None
    shadow_username: Optional[str] = None
    shadow_password: Optional[str] = None


class ShadowRouter:
    """
    影子路由器

    负责根据流量标记和配置，将数据库操作路由到影子库/影子表
    """

    def __init__(self, config_manager: Optional[ShadowConfigManager] = None):
        self.config_manager = config_manager or ShadowConfigManager()
        self._shadow_connections: Dict[str, Any] = {}
        self._enabled = True

    def enable(self) -> None:
        """启用影子路由"""
        self._enabled = True
        logger.info("Shadow routing enabled")

    def disable(self) -> None:
        """禁用影子路由"""
        self._enabled = False
        logger.info("Shadow routing disabled")

    def is_enabled(self) -> bool:
        """检查影子路由是否启用"""
        return self._enabled

    def should_use_shadow(self) -> bool:
        """
        判断是否应该使用影子库

        条件:
        1. 影子路由已启用
        2. 当前流量是压测流量
        3. 存在对应的影子库配置
        """
        if not self._enabled:
            return False

        if not is_pressure_test():
            return False

        return True

    def get_shadow_config(self, url: str, username: Optional[str] = None) -> Optional[ShadowDatabaseConfig]:
        """
        根据 URL 和用户名获取影子库配置

        Args:
            url: 数据库连接 URL
            username: 数据库用户名

        Returns:
            匹配的影子库配置，如果没有匹配则返回 None
        """
        return self.config_manager.get_shadow_config(url, username)

    def get_shadow_connection_info(self, url: str, username: Optional[str] = None) -> Optional[DataSourceMeta]:
        """
        获取影子连接信息

        Args:
            url: 业务库 URL
            username: 业务库用户名

        Returns:
            影子连接信息，如果无配置返回 None
        """
        config = self.get_shadow_config(url, username)
        if not config:
            return None

        return DataSourceMeta(
            url=url,
            username=username or "",
            driver="",  # 可从配置获取
            shadow_url=config.shadow_url,
            shadow_username=config.get_shadow_username(username),
            shadow_password=config.get_shadow_password(config.password),
        )

    def rewrite_sql(self, sql: str, url: str, username: Optional[str] = None) -> str:
        """
        重写 SQL 中的表名

        如果是压测流量且配置了影子表，则替换表名

        Args:
            sql: 原始 SQL
            url: 数据库 URL
            username: 数据库用户名

        Returns:
            重写后的 SQL
        """
        if not self.should_use_shadow():
            return sql

        config = self.get_shadow_config(url, username)
        if not config:
            return sql

        # 影子表模式：只替换表名
        if config.is_shadow_table() or config.is_shadow_database_with_table():
            return config.rewrite_table_name(sql)

        # 影子库模式：可能也需要替换表名
        if config.business_shadow_tables:
            return config.rewrite_table_name(sql)

        return sql

    def get_target_url(self, url: str, username: Optional[str] = None) -> str:
        """
        获取目标数据库 URL

        Args:
            url: 业务库 URL
            username: 业务库用户名

        Returns:
            目标 URL (影子库 URL 或原 URL)
        """
        if not self.should_use_shadow():
            return url

        config = self.get_shadow_config(url, username)
        if config and config.is_shadow_database():
            return config.shadow_url

        return url

    def get_target_credentials(self, url: str, username: Optional[str] = None, password: Optional[str] = None) -> tuple:
        """
        获取目标数据库凭据

        Args:
            url: 业务库 URL
            username: 业务库用户名
            password: 业务库密码

        Returns:
            (username, password) 元组
        """
        if not self.should_use_shadow():
            return username or "", password or ""

        config = self.get_shadow_config(url, username)
        if config and config.is_shadow_database():
            return (
                config.get_shadow_username(username),
                config.get_shadow_password(password)
            )

        return username or "", password or ""

    def register_config(self, config: ShadowDatabaseConfig) -> None:
        """注册影子库配置"""
        self.config_manager.register_config(config)
        logger.info(f"Registered shadow config: {config}")

    def unregister_config(self, url: str, username: Optional[str] = None) -> None:
        """注销影子库配置"""
        self.config_manager.unregister_config(url, username)
        logger.info(f"Unregistered shadow config for url={url}, username={username}")

    def clear_configs(self) -> None:
        """清空所有配置"""
        self.config_manager.clear_configs()
        self._shadow_connections.clear()
        logger.info("Cleared all shadow configs")


# 全局路由实例
_global_router: Optional[ShadowRouter] = None


def get_router() -> ShadowRouter:
    """获取全局影子路由器"""
    global _global_router
    if _global_router is None:
        _global_router = ShadowRouter()
    return _global_router


def set_router(router: ShadowRouter) -> None:
    """设置全局影子路由器"""
    global _global_router
    _global_router = router


def route_sql(sql: str, url: str, username: Optional[str] = None) -> str:
    """路由 SQL (重写表名)"""
    return get_router().rewrite_sql(sql, url, username)


def route_url(url: str, username: Optional[str] = None) -> str:
    """路由到目标 URL"""
    return get_router().get_target_url(url, username)


def should_use_shadow() -> bool:
    """判断是否使用影子库"""
    return get_router().should_use_shadow()
