"""
PyLinkAgent Shadow Database Module
影子数据库模块 - 支持全链路压测中的影子库/影子表路由

核心功能:
- 流量染色识别 (通过 Header/上下文)
- 影子库配置管理 (支持 YAML/环境变量/API/远程配置)
- 影子表名映射
- 数据库连接路由
- SQL 拦截与重写
"""

from .config import ShadowDatabaseConfig, ShadowConfigManager
from .config_center import (
    ShadowConfigCenter,
    ShadowConfigSource,
    init_config_center,
    get_config_center,
    load_from_file,
    load_from_env,
    register_config,
    get_config,
)
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
    # 配置类
    "ShadowDatabaseConfig",
    "ShadowConfigManager",
    # 配置中心
    "ShadowConfigCenter",
    "ShadowConfigSource",
    "init_config_center",
    "get_config_center",
    "load_from_file",
    "load_from_env",
    "register_config",
    "get_config",
    # 上下文
    "ShadowContext",
    "ShadowContextManager",
    "get_shadow_context",
    "is_pressure_test",
    "create_new_context",
    "set_shadow_context",
    # 路由
    "ShadowRouter",
    "get_router",
    "route_sql",
    "route_url",
    "should_use_shadow",
    # 拦截器
    "ShadowInterceptor",
    "SQLAlchemyShadowInterceptor",
    "DBAPI2ShadowInterceptor",
]
