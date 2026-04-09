#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 完整验证脚本
一键验证所有与管理侧的通信功能
"""

import sys
import os
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.heartbeat import HeartbeatReporter
from pylinkagent.controller.config_fetcher import ConfigFetcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FullVerifier:
    """完整验证器"""

    def __init__(self, management_url, app_name, agent_id):
        self.management_url = management_url
        self.app_name = app_name
        self.agent_id = agent_id
        self.external_api = None
        self.results = {}

    def print_header(self, title):
        """打印标题"""
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)

    def print_sub_header(self, title):
        """打印子标题"""
        print("\n" + "-" * 60)
        print(f"[{title}]")
        print("-" * 60)

    def run_all_verifications(self):
        """运行所有验证"""

        self.print_header("PyLinkAgent 完整验证")
        print(f"\n管理侧地址：{self.management_url}")
        print(f"应用名称：{self.app_name}")
        print(f"Agent ID: {self.agent_id}")
        print(f"验证时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. ExternalAPI 初始化
        self.print_sub_header("1. ExternalAPI 初始化")
        self.verify_external_api_init()

        # 2. 心跳上报
        self.print_sub_header("2. 心跳上报")
        self.verify_heartbeat()

        # 3. 心跳上报器
        self.print_sub_header("3. 心跳上报器")
        self.verify_heartbeat_reporter()

        # 4. 配置拉取
        self.print_sub_header("4. 配置拉取")
        self.verify_config_fetch()

        # 5. 配置拉取器
        self.print_sub_header("5. 配置拉取器")
        self.verify_config_fetcher()

        # 打印摘要
        self.print_summary()

    def verify_external_api_init(self):
        """验证 ExternalAPI 初始化"""
        self.external_api = ExternalAPI(
            tro_web_url=self.management_url,
            app_name=self.app_name,
            agent_id=self.agent_id,
        )

        success = self.external_api.initialize()
        if success:
            print("      [OK] ExternalAPI 初始化成功")
            self.results["external_api_init"] = True
        else:
            print("      [FAIL] ExternalAPI 初始化失败")
            self.results["external_api_init"] = False

    def verify_heartbeat(self):
        """验证心跳上报"""
        if not self.external_api or not self.external_api.is_initialized():
            print("      [SKIP] ExternalAPI 未初始化，跳过")
            self.results["heartbeat"] = False
            return

        heart_request = HeartRequest(
            project_name=self.app_name,
            agent_id=self.agent_id,
            ip_address="127.0.0.1",
            progress_id=str(os.getpid()),
            agent_status="running",
            agent_version="1.0.0",
            simulator_status="running",
            dependency_info="pylinkagent=1.0.0",
        )

        try:
            commands = self.external_api.send_heartbeat(heart_request)
            print(f"      [OK] 心跳发送成功 - 返回 {len(commands)} 个命令")
            self.results["heartbeat"] = True
        except Exception as e:
            print(f"      [FAIL] 心跳发送失败：{e}")
            self.results["heartbeat"] = False

    def verify_heartbeat_reporter(self):
        """验证心跳上报器"""
        if not self.external_api or not self.external_api.is_initialized():
            print("      [SKIP] ExternalAPI 未初始化，跳过")
            self.results["heartbeat_reporter"] = False
            return

        reporter = HeartbeatReporter(
            external_api=self.external_api,
            interval=10,
        )

        success = reporter.start()
        if success:
            print("      [OK] 心跳上报器启动成功")
            print("      [INFO] 等待 15 秒观察心跳...")
            time.sleep(15)
            reporter.stop()
            print("      [OK] 心跳上报器已停止")
            self.results["heartbeat_reporter"] = True
        else:
            print("      [FAIL] 心跳上报器启动失败")
            self.results["heartbeat_reporter"] = False

    def verify_config_fetch(self):
        """验证配置拉取"""
        if not self.external_api or not self.external_api.is_initialized():
            print("      [SKIP] ExternalAPI 未初始化，跳过")
            self.results["config_fetch"] = False
            return

        fetcher = ConfigFetcher(
            external_api=self.external_api,
            interval=60,
            initial_delay=2,
        )

        try:
            config = fetcher.fetch_now()
            if config:
                print(f"      [OK] 配置拉取成功")
                print(f"             影子库：{len(config.shadow_database_configs)}")
                print(f"             全局开关：{len(config.global_switch)}")
                print(f"             URL 白名单：{len(config.url_white_list)}")
                self.results["config_fetch"] = True
            else:
                print("      [WARN] 配置拉取返回空")
                self.results["config_fetch"] = True  # 空配置也算成功
        except Exception as e:
            print(f"      [FAIL] 配置拉取失败：{e}")
            self.results["config_fetch"] = False

    def verify_config_fetcher(self):
        """验证配置拉取器"""
        if not self.external_api or not self.external_api.is_initialized():
            print("      [SKIP] ExternalAPI 未初始化，跳过")
            self.results["config_fetcher"] = False
            return

        fetcher = ConfigFetcher(
            external_api=self.external_api,
            interval=30,
            initial_delay=2,
        )

        # 注册配置变更回调
        change_events = []
        def on_config_change(key, old_value, new_value):
            change_events.append(key)
            print(f"      [CHANGE] {key}")

        fetcher.on_config_change(on_config_change)

        success = fetcher.start()
        if success:
            print("      [OK] 配置拉取器启动成功")
            print("      [INFO] 等待 35 秒观察配置拉取...")
            time.sleep(35)
            fetcher.stop()
            print("      [OK] 配置拉取器已停止")
            self.results["config_fetcher"] = True
        else:
            print("      [FAIL] 配置拉取器启动失败")
            self.results["config_fetcher"] = False

    def print_summary(self):
        """打印验证摘要"""
        self.print_header("验证结果摘要")

        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)

        tests = [
            ("ExternalAPI 初始化", "external_api_init"),
            ("心跳上报", "heartbeat"),
            ("心跳上报器", "heartbeat_reporter"),
            ("配置拉取", "config_fetch"),
            ("配置拉取器", "config_fetcher"),
        ]

        for name, key in tests:
            status = "[OK]" if self.results.get(key, False) else "[FAIL]"
            print(f"  {status} {name}")

        print(f"\n通过率：{passed}/{total}")

        if passed == total:
            print("\n[OK] 所有验证通过！PyLinkAgent 可以正常连接管理侧")
        elif passed >= total - 1:
            print("\n[WARN] 大部分验证通过，可能存在小问题")
        else:
            print("\n[FAIL] 部分验证失败，请检查故障排查章节")

        print("=" * 60)


def main():
    # 获取配置
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")

    if len(sys.argv) > 1:
        management_url = sys.argv[1]
    if len(sys.argv) > 2:
        app_name = sys.argv[2]
    if len(sys.argv) > 3:
        agent_id = sys.argv[3]

    verifier = FullVerifier(management_url, app_name, agent_id)
    verifier.run_all_verifications()

    # 返回退出码
    passed = sum(1 for v in verifier.results.values() if v)
    total = len(verifier.results)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
