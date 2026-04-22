"""
PyLinkAgent 影子路由 - 零侵入的影子数据库/服务器路由

在压测流量下自动将请求路由到影子数据库/服务器。
支持: MySQL, Redis, Elasticsearch, Kafka, HTTP 客户端。
"""

from .config_center import (
    ShadowDatabaseConfig,
    ShadowRedisConfig,
    ShadowEsConfig,
    ShadowKafkaConfig,
    ShadowConfigCenter,
)
from .router import ShadowRouter
from .sql_rewriter import ShadowSQLRewriter
from .context import ShadowRoutingContext

__all__ = [
    "ShadowDatabaseConfig",
    "ShadowRedisConfig",
    "ShadowEsConfig",
    "ShadowKafkaConfig",
    "ShadowConfigCenter",
    "ShadowRouter",
    "ShadowSQLRewriter",
    "ShadowRoutingContext",
    "get_config_center",
    "get_router",
    "init_config_center",
    "register_config",
]

_config_center: ShadowConfigCenter = None
_router: ShadowRouter = None


def init_config_center(config_center: ShadowConfigCenter = None) -> ShadowConfigCenter:
    """初始化影子配置中心"""
    global _config_center, _router
    if _config_center is None:
        _config_center = config_center or ShadowConfigCenter()
        _router = ShadowRouter(_config_center)
    return _config_center


def get_config_center() -> ShadowConfigCenter:
    """获取全局配置中心单例"""
    global _config_center, _router
    if _config_center is None:
        _config_center = ShadowConfigCenter()
        _router = ShadowRouter(_config_center)
    return _config_center


def get_router() -> ShadowRouter:
    """获取全局路由器单例"""
    get_config_center()
    return _router


def register_config(config: ShadowDatabaseConfig) -> None:
    """运行时注册影子库配置"""
    get_config_center().register_db_config(config)
