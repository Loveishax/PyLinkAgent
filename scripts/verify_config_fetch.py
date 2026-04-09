#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置拉取验证脚本
验证从管理侧拉取配置的功能
"""

import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI
from pylinkagent.controller.config_fetcher import ConfigFetcher

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_config_fetch(management_url, app_name, agent_id):
    """验证配置拉取功能"""

    print("\n" + "=" * 60)
    print("配置拉取验证")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print("\n" + "-" * 60)

    # 初始化 ExternalAPI
    external_api = ExternalAPI(
        tro_web_url=management_url,
        app_name=app_name,
        agent_id=agent_id,
    )

    if not external_api.initialize():
        print("\n[FAIL] ExternalAPI 初始化失败")
        return False

    # 创建配置拉取器
    fetcher = ConfigFetcher(
        external_api=external_api,
        interval=60,
        initial_delay=2,
    )

    # 注册配置变更回调
    def on_config_change(key, old_value, new_value):
        logger.info(f"[CONFIG CHANGE] {key}")
        print(f"      [CHANGE] {key}")

    fetcher.on_config_change(on_config_change)

    # 立即拉取配置
    print("\n[INFO] 开始拉取配置...")
    try:
        config = fetcher.fetch_now()

        if config:
            print("      [OK] 配置拉取成功")
            print(f"\n      配置详情:")
            print(f"        - 影子库配置数：{len(config.shadow_database_configs)}")
            print(f"        - 全局开关数：{len(config.global_switch)}")
            print(f"        - Redis 影子配置数：{len(config.redis_shadow_configs)}")
            print(f"        - ES 影子配置数：{len(config.es_shadow_configs)}")
            print(f"        - MQ 白名单数：{len(config.mq_white_list)}")
            print(f"        - RPC 白名单数：{len(config.rpc_white_list)}")
            print(f"        - URL 白名单数：{len(config.url_white_list)}")

            # 显示部分配置示例
            if config.shadow_database_configs:
                print(f"\n      影子库配置示例:")
                for name, cfg in list(config.shadow_database_configs.items())[:2]:
                    print(f"        - {name}: {cfg}")

            return True
        else:
            print("      [WARN] 配置拉取返回空（管理侧可能没有配置）")
            return True

    except Exception as e:
        print(f"      [FAIL] 配置拉取失败：{e}")
        return False


if __name__ == "__main__":
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")

    if len(sys.argv) > 1:
        management_url = sys.argv[1]

    success = verify_config_fetch(management_url, app_name, agent_id)
    sys.exit(0 if success else 1)
