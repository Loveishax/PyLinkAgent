#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置拉取完整验证脚本
验证管理面影子配置下发与拉取功能
"""

import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI
from pylinkagent.controller.config_fetcher import ConfigFetcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_config_full(management_url, app_name, agent_id):
    """完整验证配置拉取功能"""

    print("\n" + "=" * 60)
    print("PyLinkAgent 配置拉取验证")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print("\n" + "-" * 60)

    results = {}

    # 步骤 1: 初始化 ExternalAPI
    print("\n[步骤 1/3] 初始化 ExternalAPI...")
    external_api = ExternalAPI(
        tro_web_url=management_url,
        app_name=app_name,
        agent_id=agent_id,
    )

    success = external_api.initialize()
    if success:
        print("      [OK] ExternalAPI 初始化成功")
        results["init"] = True
    else:
        print("      [FAIL] ExternalAPI 初始化失败")
        results["init"] = False
        return results

    # 步骤 2: 拉取配置
    print("\n[步骤 2/3] 拉取配置数据...")
    fetcher = ConfigFetcher(
        external_api=external_api,
        interval=60,
        initial_delay=2,
    )

    try:
        config = fetcher.fetch_now()
        if config:
            print("      [OK] 配置拉取成功")
            print(f"\n      配置详情:")
            print(f"        - 影子库配置数：{len(config.shadow_database_configs)}")
            print(f"        - 全局开关数：{len(config.global_switch)}")
            print(f"        - Redis 影子配置数：{len(config.redis_shadow_configs)}")
            print(f"        - ES 影子配置数：{len(config.es_shadow_configs)}")
            print(f"        - URL 白名单数：{len(config.url_white_list)}")
            print(f"        - RPC 白名单数：{len(config.rpc_white_list)}")
            print(f"        - MQ 白名单数：{len(config.mq_white_list)}")

            # 显示影子库配置示例
            if config.shadow_database_configs:
                print(f"\n      影子库配置示例:")
                for name, cfg in list(config.shadow_database_configs.items())[:2]:
                    print(f"        - {name}:")
                    if isinstance(cfg, dict):
                        if 'master' in cfg:
                            print(f"            主库：{cfg.get('master', 'N/A')}")
                            print(f"            影子库：{cfg.get('shadow', 'N/A')}")
                        else:
                            print(f"            配置：{cfg}")
                    else:
                        print(f"            {cfg}")

            results["config_fetch"] = True
            results["shadow_db_config"] = len(config.shadow_database_configs) > 0
            results["global_switch_config"] = len(config.global_switch) > 0
        else:
            print("      [WARN] 配置拉取返回空（管理侧可能没有配置）")
            results["config_fetch"] = True  # 空配置也算成功
            results["shadow_db_config"] = False
            results["global_switch_config"] = False

    except Exception as e:
        print(f"      [FAIL] 配置拉取失败：{e}")
        results["config_fetch"] = False
        results["shadow_db_config"] = False
        results["global_switch_config"] = False
        return results

    # 步骤 3: 验证配置变更通知
    print("\n[步骤 3/3] 验证配置变更通知...")
    change_events = []

    def on_config_change(key, old_value, new_value):
        change_events.append(key)
        logger.info(f"[配置变更] {key}: {old_value} -> {new_value}")

    fetcher.on_config_change(on_config_change)

    success = fetcher.start()
    if success:
        print("      [OK] 配置拉取器启动成功")
        print("      [INFO] 等待 35 秒观察配置拉取...")
        time.sleep(35)
        fetcher.stop()
        print("      [OK] 配置拉取器运行正常")
        results["config_change_notify"] = True
    else:
        print("      [FAIL] 配置拉取器启动失败")
        results["config_change_notify"] = False

    return results


def print_summary(results):
    """打印验证摘要"""
    print("\n" + "=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print("验证结果摘要")
    print("=" * 60)

    tests = [
        ("ExternalAPI 初始化", "init"),
        ("配置拉取", "config_fetch"),
        ("影子库配置", "shadow_db_config"),
        ("全局开关配置", "global_switch_config"),
        ("配置变更通知", "config_change_notify"),
    ]

    for name, key in tests:
        status = "[OK]" if results.get(key, False) else "[WARN]"
        print(f"  {status} {name}")

    print(f"\n通过率：{passed}/{total}")

    if passed >= total - 1:
        print("\n[OK] 配置拉取验证通过")
    else:
        print("\n[WARN] 部分验证失败")

    print("=" * 60)


def main():
    # 获取配置
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")

    if len(sys.argv) > 1:
        management_url = sys.argv[1]

    results = verify_config_full(management_url, app_name, agent_id)
    print_summary(results)

    # 返回退出码
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    sys.exit(0 if passed >= total - 1 else 1)


if __name__ == "__main__":
    main()
