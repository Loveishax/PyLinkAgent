"""
PyLinkAgent Shadow Database Module
影子数据库模块 - 支持全链路压测中的影子库/影子表路由

核心功能:
- 流量染色识别 (通过 Header/上下文)
- 影子库配置管理
- 影子表名映射
- 数据库连接路由
- SQL 拦截与重写
"""

from .config import ShadowDatabaseConfig, ShadowConfigManager
from .context import (
    ShadowContext,
    ShadowContextManager,
    get_shadow_context,
    is_pressure_test,
    create_new_context,
    set_shadow_context,
)
from .router import ShadowRouter, get_router, route_sql, route_url, should_use_shadow
from .interceptor import ShadowInterceptor, SQLAlchemyShadowInterceptor, DBAPI2ShadowInterceptor

__all__ = [
    "ShadowDatabaseConfig",
    "ShadowConfigManager",
    "ShadowContext",
    "ShadowContextManager",
    "get_shadow_context",
    "is_pressure_test",
    "ShadowRouter",
    "get_router",
    "route_sql",
    "route_url",
    "should_use_shadow",
    "ShadowInterceptor",
    "SQLAlchemyShadowInterceptor",
    "DBAPI2ShadowInterceptor",
]
