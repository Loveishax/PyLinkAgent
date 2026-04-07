"""
PyLinkAgent 影子库配置中心使用示例

展示如何使用灵活的配置方案管理影子库配置
"""

# ============================================
# 示例 1: 使用 YAML 配置文件
# ============================================

def example_yaml_config():
    """使用 YAML 配置文件"""
    from pylinkagent.shadow import init_config_center, ShadowConfigSource

    # 创建配置源
    source = ShadowConfigSource(
        config_file="shadow_config.yaml"  # 配置文件路径
    )

    # 初始化并加载所有配置
    config_center = init_config_center(source)

    print(f"加载了 {len(config_center.get_all_configs())} 个影子库配置")
    return config_center


# ============================================
# 示例 2: 使用环境变量
# ============================================

def example_env_config():
    """使用环境变量"""
    import os
    from pylinkagent.shadow import init_config_center, ShadowConfigSource

    # 方式 1: JSON 数组格式
    os.environ["PYLINKAGENT_SHADOW_CONFIGS"] = '''
    [
        {
            "ds_type": 0,
            "url": "jdbc:mysql://localhost:3306/test",
            "username": "root",
            "shadow_url": "jdbc:mysql://localhost:3307/shadow_test",
            "shadow_username": "PT_root",
            "shadow_account_prefix": "PT_",
            "business_shadow_tables": {
                "users": "shadow_users",
                "orders": "shadow_orders"
            }
        }
    ]
    '''

    # 方式 2: 单个配置
    os.environ["PYLINKAGENT_SHADOW_URL"] = "jdbc:mysql://localhost:3306/test"
    os.environ["PYLINKAGENT_SHADOW_SHADOW_URL"] = "jdbc:mysql://localhost:3307/shadow_test"
    os.environ["PYLINKAGENT_SHADOW_USERNAME"] = "root"
    os.environ["PYLINKAGENT_SHADOW_SHADOW_USERNAME"] = "PT_root"
    os.environ["PYLINKAGENT_SHADOW_ACCOUNT_PREFIX"] = "PT_"
    os.environ["PYLINKAGENT_SHADOW_TABLE_MAPPING"] = "users:shadow_users,orders:shadow_orders"

    source = ShadowConfigSource(env_enabled=True)
    config_center = init_config_center(source)

    return config_center


# ============================================
# 示例 3: 使用 API 动态注册
# ============================================

def example_api_config():
    """使用 API 动态注册配置"""
    from pylinkagent.shadow import (
        init_config_center,
        ShadowConfigSource,
        ShadowDatabaseConfig
    )

    # 启动 API 服务器
    source = ShadowConfigSource(
        api_enabled=True,
        api_host="0.0.0.0",
        api_port=8081
    )

    config_center = init_config_center(source)

    # 动态注册配置
    config = ShadowDatabaseConfig(
        ds_type=0,
        url="jdbc:mysql://localhost:3306/test",
        username="root",
        shadow_url="jdbc:mysql://localhost:3307/shadow_test",
        shadow_username="PT_root",
        shadow_account_prefix="PT_",
        business_shadow_tables={
            "users": "shadow_users",
            "orders": "shadow_orders"
        }
    )

    config_center.register_config(config)

    print("配置已注册，可通过 API 查询：http://localhost:8081/configs")

    return config_center


# ============================================
# 示例 4: 使用远程配置中心
# ============================================

def example_remote_config():
    """使用远程配置中心"""
    from pylinkagent.shadow import init_config_center, ShadowConfigSource

    source = ShadowConfigSource(
        remote_enabled=True,
        remote_url="http://control-center:8080/api/shadow-configs",
        remote_api_key="your-api-key",
        remote_poll_interval=60  # 60 秒同步一次
    )

    config_center = init_config_center(source)

    print("远程配置同步已启动")

    return config_center


# ============================================
# 示例 5: 混合配置方式
# ============================================

def example_hybrid_config():
    """混合配置方式：YAML + 环境变量 + API"""
    from pylinkagent.shadow import init_config_center, ShadowConfigSource

    source = ShadowConfigSource(
        config_file="shadow_config.yaml",  # 基础配置
        env_enabled=True,                   # 允许环境变量覆盖
        api_enabled=True,                   # 允许 API 动态注册
        api_host="0.0.0.0",
        api_port=8081
    )

    config_center = init_config_center(source)

    print(f"混合配置加载完成，共 {len(config_center.get_all_configs())} 个配置")

    return config_center


# ============================================
# 示例 6: 运行时动态配置
# ============================================

def example_runtime_config():
    """运行时动态配置"""
    from pylinkagent.shadow import (
        get_config_center,
        ShadowDatabaseConfig,
        register_config
    )

    # 获取配置中心
    center = get_config_center()

    # 为新数据库注册影子库配置
    new_config = ShadowDatabaseConfig(
        ds_type=0,
        url="jdbc:mysql://new-db:3306/app",
        username="app_user",
        password="app_pass",
        shadow_url="jdbc:mysql://shadow-db:3306/app",
        shadow_username="PT_app_user",
        shadow_password="PT_app_pass",
        shadow_account_prefix="PT_",
        business_shadow_tables={
            "users": "PT_users",
            "orders": "PT_orders"
        }
    )

    center.register_config(new_config)
    print("新配置已注册")

    # 查询配置
    config = center.get_config("jdbc:mysql://new-db:3306/app")
    if config:
        print(f"找到配置：{config}")

    return center


# ============================================
# 示例 7: 多租户配置
# ============================================

def example_multi_tenant():
    """多租户影子库配置"""
    from pylinkagent.shadow import get_config_center, ShadowDatabaseConfig

    center = get_config_center()

    # 租户配置数据
    tenants = [
        {
            "id": "tenant_a",
            "url": "jdbc:mysql://db:3306/tenant_a",
            "shadow_url": "jdbc:mysql://shadow-db:3306/tenant_a",
            "tables": {"users": "shadow_users", "orders": "shadow_orders"}
        },
        {
            "id": "tenant_b",
            "url": "jdbc:mysql://db:3306/tenant_b",
            "shadow_url": "jdbc:mysql://shadow-db:3306/tenant_b",
            "tables": {"users": "shadow_users", "orders": "shadow_orders"}
        },
    ]

    # 为每个租户注册配置
    for tenant in tenants:
        config = ShadowDatabaseConfig(
            ds_type=0,
            url=tenant["url"],
            shadow_url=tenant["shadow_url"],
            shadow_username=f"PT_{tenant['id']}_user",
            shadow_account_prefix="PT_",
            business_shadow_tables=tenant["tables"]
        )
        center.register_config(config)
        print(f"租户 {tenant['id']} 配置已注册")

    return center


# ============================================
# 示例 8: 配置热更新
# ============================================

def example_hot_reload():
    """配置热更新"""
    import time
    import threading
    from pylinkagent.shadow import get_config_center

    center = get_config_center()

    def reload_config():
        """定时刷新配置"""
        while True:
            time.sleep(60)  # 每 60 秒刷新一次

            # 重新加载配置文件
            count = center._load_from_file("shadow_config.yaml")
            print(f"配置已刷新：{count} 个配置")

    # 启动后台刷新线程
    thread = threading.Thread(target=reload_config, daemon=True)
    thread.start()

    print("配置热更新已启动")

    return center


# ============================================
# 示例 9: 完整的 FastAPI 集成
# ============================================

def example_fastapi_integration():
    """FastAPI 集成示例"""
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from pylinkagent.shadow import (
        get_config_center,
        ShadowDatabaseConfig,
        init_config_center,
        ShadowConfigSource
    )

    app = FastAPI()

    # 初始化配置中心
    config_center = init_config_center(ShadowConfigSource(
        api_enabled=True,
        api_port=8081
    ))

    class ShadowConfigInput(BaseModel):
        ds_type: int = 0
        url: str
        shadow_url: str
        username: str = ""
        shadow_username: str = ""
        shadow_account_prefix: str = "PT_"
        business_shadow_tables: dict = {}

    @app.get("/shadow/configs")
    def list_configs():
        """列出所有影子库配置"""
        configs = config_center.get_all_configs()
        return {
            "count": len(configs),
            "configs": [
                {
                    "url": c.url,
                    "shadow_url": c.shadow_url,
                    "tables": c.business_shadow_tables
                }
                for c in configs
            ]
        }

    @app.post("/shadow/configs")
    def register_config(config_input: ShadowConfigInput):
        """注册新的影子库配置"""
        config = ShadowDatabaseConfig(
            ds_type=config_input.ds_type,
            url=config_input.url,
            shadow_url=config_input.shadow_url,
            username=config_input.username,
            shadow_username=config_input.shadow_username,
            shadow_account_prefix=config_input.shadow_account_prefix,
            business_shadow_tables=config_input.business_shadow_tables
        )
        config_center.register_config(config)
        return {"status": "success", "message": "配置已注册"}

    @app.delete("/shadow/configs/{url}")
    def unregister_config(url: str):
        """删除影子库配置"""
        if config_center.unregister_config(url):
            return {"status": "success", "message": "配置已删除"}
        raise HTTPException(status_code=404, detail="配置不存在")

    return app


# ============================================
# 主程序
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("PyLinkAgent 影子库配置中心使用示例")
    print("=" * 60)

    # 运行示例
    print("\n1. YAML 配置文件示例")
    # example_yaml_config()

    print("\n2. 环境变量示例")
    # example_env_config()

    print("\n3. API 动态注册示例")
    # example_api_config()

    print("\n4. 远程配置中心示例")
    # example_remote_config()

    print("\n5. 混合配置示例")
    # example_hybrid_config()

    print("\n6. 运行时动态配置示例")
    # example_runtime_config()

    print("\n7. 多租户配置示例")
    # example_multi_tenant()

    print("=" * 60)
    print("示例执行完成")
    print("=" * 60)
