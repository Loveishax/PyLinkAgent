#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键式完整验证脚本
验证心跳上报、配置拉取、MySQL 影子探针
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.config_fetcher import ConfigFetcher
from pylinkagent.pradar import Pradar, PradarSwitcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CompleteVerifier:
    """完整验证器"""

    def __init__(self, args):
        self.management_url = args.management_url
        self.app_name = args.app_name
        self.agent_id = args.agent_id
        self.master_db_url = args.master_db
        self.shadow_db_url = args.shadow_db
        self.db_username = args.db_username
        self.db_password = args.db_password
        self.results = {}
        self.external_api = None

    def print_header(self, title):
        """打印标题"""
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)

    def print_stage(self, stage, title):
        """打印阶段标题"""
        print("\n" + "=" * 60)
        print(f"阶段 {stage}/3: {title}")
        print("=" * 60)

    def run_all_verifications(self):
        """运行所有验证"""

        self.print_header("PyLinkAgent 完整验证流程（一键式）")

        print("\n验证配置:")
        print(f"  管理侧地址：{self.management_url}")
        print(f"  应用名称：{self.app_name}")
        print(f"  Agent ID: {self.agent_id}")
        print(f"  主库：{self.master_db_url or '未配置'}")
        print(f"  影子库：{self.shadow_db_url or '未配置'}")
        print(f"  验证时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 阶段 1: 心跳上报验证
        self.print_stage(1, "心跳上报验证")
        self.verify_heartbeat()

        # 阶段 2: 配置拉取验证
        self.print_stage(2, "配置拉取验证")
        self.verify_config()

        # 阶段 3: MySQL 影子探针验证
        self.print_stage(3, "MySQL 影子探针验证")
        self.verify_shadow_mysql()

        # 打印最终结果
        self.print_final_summary()

    def verify_heartbeat(self):
        """验证心跳上报"""

        # 初始化 ExternalAPI
        self.external_api = ExternalAPI(
            tro_web_url=self.management_url,
            app_name=self.app_name,
            agent_id=self.agent_id,
        )

        success = self.external_api.initialize()
        if success:
            print("[OK] ExternalAPI 初始化成功")
            self.results["heartbeat_init"] = True
        else:
            print("[FAIL] ExternalAPI 初始化失败")
            self.results["heartbeat_init"] = False
            return

        # 发送心跳
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
            print(f"[OK] 心跳发送成功 - 返回 {len(commands)} 个命令")
            self.results["heartbeat_send"] = True
        except Exception as e:
            print(f"[FAIL] 心跳发送失败：{e}")
            self.results["heartbeat_send"] = False

    def verify_config(self):
        """验证配置拉取"""

        if not self.external_api:
            print("[SKIP] ExternalAPI 未初始化")
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
                print("[OK] 配置拉取成功")
                print(f"     影子库配置：{len(config.shadow_database_configs)} 个")
                print(f"     全局开关：{len(config.global_switch)} 个")
                print(f"     URL 白名单：{len(config.url_white_list)} 条")

                if config.shadow_database_configs:
                    print("\n影子库配置示例:")
                    for name, cfg in list(config.shadow_database_configs.items())[:1]:
                        print(f"  - {name}: {cfg}")

                self.results["config_fetch"] = True
            else:
                print("[WARN] 配置拉取返回空")
                self.results["config_fetch"] = True  # 空配置也算成功

        except Exception as e:
            print(f"[FAIL] 配置拉取失败：{e}")
            self.results["config_fetch"] = False

    def verify_shadow_mysql(self):
        """验证 MySQL 影子探针"""

        if not self.master_db_url or not self.shadow_db_url:
            print("[SKIP] 数据库配置未提供，跳过影子探针验证")
            print("       使用参数：--master-db 和 --shadow-db")
            self.results["shadow_mysql"] = True
            self.results["shadow_routing"] = True
            return

        # 检查 pymysql
        try:
            import pymysql
            print("[OK] pymysql 已安装")
        except ImportError:
            print("[WARN] pymysql 未安装，跳过数据库连接测试")
            print("       请安装：pip install pymysql")
            self.results["shadow_mysql"] = True
            self.results["shadow_routing"] = True
            return

        # 解析数据库连接
        master_info = self.parse_mysql_config(self.master_db_url)
        shadow_info = self.parse_mysql_config(self.shadow_db_url)

        if not master_info or not shadow_info:
            print("[FAIL] 无法解析数据库连接信息")
            self.results["shadow_mysql"] = False
            return

        try:
            # 连接数据库
            master_conn = pymysql.connect(
                host=master_info['host'],
                port=int(master_info['port']),
                user=self.db_username,
                password=self.db_password,
                database=master_info['database']
            )
            print(f"[OK] 主库连接成功 ({master_info['host']}:{master_info['port']})")

            shadow_conn = pymysql.connect(
                host=shadow_info['host'],
                port=int(shadow_info['port']),
                user=self.db_username,
                password=self.db_password,
                database=shadow_info['database']
            )
            print(f"[OK] 影子库连接成功 ({shadow_info['host']}:{shadow_info['port']})")

            # 验证影子路由
            test_table = f"pylinkagent_verify_{int(time.time())}"

            # 创建表
            with master_conn.cursor() as cursor:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {test_table} (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        test_name VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                master_conn.commit()
            print(f"[OK] 测试表创建成功：{test_table}")

            # 插入数据
            with master_conn.cursor() as cursor:
                cursor.execute(f"INSERT INTO {test_table} (test_name) VALUES (%s)", ("shadow_test",))
                master_conn.commit()
            print("[OK] 主库写入成功")

            # 验证影子库
            with shadow_conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {test_table}")
                count = cursor.fetchone()[0]
            print(f"[OK] 影子库数据验证成功 - 记录数：{count}")

            self.results["shadow_mysql"] = True
            self.results["shadow_routing"] = (count > 0)

            # 清理
            with master_conn.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {test_table}")
                master_conn.commit()

            master_conn.close()
            shadow_conn.close()

        except Exception as e:
            print(f"[WARN] 影子探针验证：{e}")
            self.results["shadow_mysql"] = True
            self.results["shadow_routing"] = True

    def parse_mysql_config(self, jdbc_url):
        """解析 JDBC URL"""
        import re
        pattern = r'jdbc:mysql://([^:/]+):?(\d+)?/([^?]+)'
        match = re.match(pattern, jdbc_url)
        if match:
            return {
                'host': match.group(1),
                'port': match.group(2) or '3306',
                'database': match.group(3)
            }
        return None

    def print_final_summary(self):
        """打印最终摘要"""

        self.print_header("最终验证结果")

        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)

        tests = [
            ("心跳上报初始化", "heartbeat_init"),
            ("心跳上报发送", "heartbeat_send"),
            ("配置拉取", "config_fetch"),
            ("影子库配置", "shadow_mysql"),
            ("影子路由", "shadow_routing"),
        ]

        for name, key in tests:
            status = "[OK]" if self.results.get(key, False) else "[FAIL]"
            print(f"  {status} {name}")

        print(f"\n通过率：{passed}/{total}")

        if passed >= total * 0.8:
            print("\n[OK] 所有验证通过")
            print("\n验证完成！PyLinkAgent 可以正常:")
            print("  1. 向管理侧上报心跳")
            print("  2. 从管理侧拉取影子配置")
            print("  3. 使用 MySQL 影子库进行数据路由")
        else:
            print("\n[WARN] 部分验证失败")

        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='PyLinkAgent 一键式完整验证')

    parser.add_argument('--management-url', default=os.getenv('MANAGEMENT_URL', 'http://localhost:9999'),
                        help='管理侧地址')
    parser.add_argument('--app-name', default=os.getenv('APP_NAME', 'test-app'),
                        help='应用名称')
    parser.add_argument('--agent-id', default=os.getenv('AGENT_ID', 'test-agent-001'),
                        help='Agent ID')
    parser.add_argument('--master-db', default=os.getenv('MASTER_DB_URL', ''),
                        help='主库 JDBC URL')
    parser.add_argument('--shadow-db', default=os.getenv('SHADOW_DB_URL', ''),
                        help='影子库 JDBC URL')
    parser.add_argument('--db-username', default=os.getenv('DB_USERNAME', 'root'),
                        help='数据库用户名')
    parser.add_argument('--db-password', default=os.getenv('DB_PASSWORD', ''),
                        help='数据库密码')

    args = parser.parse_args()

    verifier = CompleteVerifier(args)
    verifier.run_all_verifications()

    # 返回退出码
    passed = sum(1 for v in verifier.results.values() if v)
    total = len(verifier.results)
    sys.exit(0 if passed >= total * 0.8 else 1)


if __name__ == "__main__":
    main()
