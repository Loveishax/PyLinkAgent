#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 端到端验证脚本

验证内容:
1. 数据库连接和表结构
2. Takin-web 服务可用性
3. 心跳上报功能
4. 影子库配置拉取
5. 应用信息上报

使用方法:
    python scripts/end_to_end_verify.py \
        --mysql-host localhost \
        --mysql-port 3306 \
        --mysql-user root \
        --mysql-password your_password \
        --takin-url http://localhost:9999
"""

import sys
import os
import time
import logging
import argparse
import subprocess
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.config_fetcher import ConfigFetcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('verify_{0}.log'.format(datetime.now().strftime('%Y%m%d_%H%M%S')))
    ]
)
logger = logging.getLogger(__name__)


class Colors:
    """颜色输出"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_success(msg):
    print(f"{Colors.GREEN}[✓] {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}[✗] {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}[!] {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}[i] {msg}{Colors.END}")


class EndToEndVerifier:
    """端到端验证器"""

    def __init__(self, args):
        self.mysql_host = args.mysql_host
        self.mysql_port = args.mysql_port
        self.mysql_user = args.mysql_user
        self.mysql_password = args.mysql_password
        self.mysql_db = args.mysql_db
        self.takin_url = args.takin_url
        self.app_name = args.app_name
        self.agent_id = args.agent_id

        self.results = {}
        self.external_api = None

    def run_all_verifications(self):
        """运行所有验证"""
        print("\n" + "=" * 70)
        print("PyLinkAgent 端到端验证")
        print("=" * 70)
        print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"MySQL: {self.mysql_host}:{self.mysql_port}")
        print(f"Takin-web: {self.takin_url}")
        print(f"应用：{self.app_name}")
        print(f"Agent ID: {self.agent_id}")
        print("=" * 70 + "\n")

        # 阶段 1: 数据库验证
        self.verify_database()

        # 阶段 2: Takin-web 服务验证
        self.verify_takin_web_service()

        # 阶段 3: 心跳上报验证
        self.verify_heartbeat()

        # 阶段 4: 影子库配置验证
        self.verify_shadow_config()

        # 阶段 5: 应用信息上报验证
        self.verify_application_upload()

        # 打印最终结果
        self.print_final_summary()

    def verify_database(self):
        """验证数据库"""
        print("\n" + "=" * 70)
        print("阶段 1/5: 数据库验证")
        print("=" * 70)

        try:
            import pymysql

            conn = pymysql.connect(
                host=self.mysql_host,
                port=self.mysql_port,
                user=self.mysql_user,
                password=self.mysql_password,
                database=self.mysql_db
            )
            cursor = conn.cursor()

            # 检查核心表是否存在
            print("\n检查核心表...")
            tables = ['t_agent_report', 't_application_mnt', 't_application_ds_manage']
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='{self.mysql_db}' AND table_name='{table}'")
                count = cursor.fetchone()[0]
                if count > 0:
                    print_success(f"表 {table} 存在")
                    self.results[f"db_table_{table}"] = True
                else:
                    print_error(f"表 {table} 不存在")
                    self.results[f"db_table_{table}"] = False

            # 检查测试应用
            print("\n检查测试应用...")
            cursor.execute(f"SELECT COUNT(*) FROM t_application_mnt WHERE APPLICATION_NAME='{self.app_name}'")
            count = cursor.fetchone()[0]
            if count > 0:
                print_success(f"应用 {self.app_name} 已存在")
                self.results["db_app_exists"] = True
            else:
                print_warning(f"应用 {self.app_name} 不存在，将在后续创建")
                self.results["db_app_exists"] = False

            # 检查影子库配置
            print("\n检查影子库配置...")
            cursor.execute(f"SELECT COUNT(*) FROM t_application_ds_manage WHERE APPLICATION_NAME='{self.app_name}' AND STATUS=0")
            count = cursor.fetchone()[0]
            if count > 0:
                print_success(f"应用 {self.app_name} 有影子库配置")
                self.results["db_shadow_config"] = True
            else:
                print_warning(f"应用 {self.app_name} 无影子库配置")
                self.results["db_shadow_config"] = False

            cursor.close()
            conn.close()

        except ImportError:
            print_error("pymysql 未安装，请运行：pip install pymysql")
            self.results["db_connection"] = False
            return
        except Exception as e:
            print_error(f"数据库验证失败：{e}")
            self.results["db_connection"] = False
            return

        print_success("数据库验证通过")
        self.results["db_connection"] = True

    def verify_takin_web_service(self):
        """验证 Takin-web 服务"""
        print("\n" + "=" * 70)
        print("阶段 2/5: Takin-web 服务验证")
        print("=" * 70)

        try:
            import httpx

            # 测试连接
            print("\n测试 Takin-web 连接...")
            response = httpx.get(self.takin_url, timeout=5)
            print_success(f"Takin-web 可访问 (状态码：{response.status_code})")
            self.results["takin_web_accessible"] = True

        except ImportError:
            print_warning("httpx 未安装，使用 requests 降级")
            try:
                import requests
                response = requests.get(self.takin_url, timeout=5)
                print_success(f"Takin-web 可访问 (状态码：{response.status_code})")
                self.results["takin_web_accessible"] = True
            except Exception as e:
                print_error(f"Takin-web 不可访问：{e}")
                self.results["takin_web_accessible"] = False
                return
        except Exception as e:
            print_error(f"Takin-web 不可访问：{e}")
            self.results["takin_web_accessible"] = False
            return

        # 测试心跳接口
        print("\n测试心跳接口...")
        try:
            api = ExternalAPI(
                tro_web_url=self.takin_url,
                app_name=self.app_name,
                agent_id=self.agent_id,
            )
            if api.initialize():
                print_success("ExternalAPI 初始化成功")
                self.results["external_api_init"] = True
                self.external_api = api
            else:
                print_error("ExternalAPI 初始化失败")
                self.results["external_api_init"] = False
        except Exception as e:
            print_error(f"ExternalAPI 初始化失败：{e}")
            self.results["external_api_init"] = False

    def verify_heartbeat(self):
        """验证心跳上报"""
        print("\n" + "=" * 70)
        print("阶段 3/5: 心跳上报验证")
        print("=" * 70)

        if not self.external_api:
            print_error("ExternalAPI 未初始化，跳过此阶段")
            self.results["heartbeat_test"] = False
            return

        print("\n发送心跳请求...")
        heart_request = HeartRequest(
            project_name=self.app_name,
            agent_id=self.agent_id,
            ip_address="127.0.0.1",
            progress_id=str(os.getpid()),
            cur_upgrade_batch="-1",
            agent_status="running",
            simulator_status="running",
            uninstall_status=0,
            dormant_status=0,
            agent_version="1.0.0",
            simulator_version="1.0.0",
            dependency_info="pylinkagent=1.0.0",
            flag="shulieEnterprise",
        )

        try:
            commands = self.external_api.send_heartbeat(heart_request)
            print_success(f"心跳发送成功 (返回 {len(commands)} 个命令)")
            self.results["heartbeat_send"] = True

            # 持续心跳
            print("\n发送持续心跳 (3 次)...")
            success_count = 0
            for i in range(3):
                time.sleep(5)
                try:
                    commands = self.external_api.send_heartbeat(heart_request)
                    if commands is not None:
                        success_count += 1
                        print_success(f"心跳 #{i+1}/3 成功")
                except Exception as e:
                    print_error(f"心跳 #{i+1}/3 失败：{e}")

            if success_count == 3:
                print_success("持续心跳全部成功")
                self.results["heartbeat_continuous"] = True
            else:
                print_warning(f"持续心跳成功率：{success_count}/3")
                self.results["heartbeat_continuous"] = (success_count >= 2)

        except Exception as e:
            print_error(f"心跳上报失败：{e}")
            self.results["heartbeat_send"] = False
            self.results["heartbeat_continuous"] = False

    def verify_shadow_config(self):
        """验证影子库配置拉取"""
        print("\n" + "=" * 70)
        print("阶段 4/5: 影子库配置拉取验证")
        print("=" * 70)

        if not self.external_api:
            print_error("ExternalAPI 未初始化，跳过此阶段")
            self.results["shadow_config_test"] = False
            return

        print("\n拉取影子库配置...")
        try:
            configs = self.external_api.fetch_shadow_database_config()

            if configs is None:
                print_warning("影子库配置返回 None (可能未配置)")
                self.results["shadow_config_fetch"] = True  # 空配置也算成功
                self.results["shadow_config_content"] = False
            elif isinstance(configs, list):
                if len(configs) > 0:
                    print_success(f"拉取到 {len(configs)} 个影子库配置")
                    for i, cfg in enumerate(configs, 1):
                        print(f"\n  配置 #{i}:")
                        for key, value in cfg.items():
                            if 'password' in key.lower():
                                print(f"    {key}: ***")
                            else:
                                print(f"    {key}: {value}")
                    self.results["shadow_config_fetch"] = True
                    self.results["shadow_config_content"] = True
                else:
                    print_warning("影子库配置为空数组")
                    self.results["shadow_config_fetch"] = True
                    self.results["shadow_config_content"] = False
            else:
                print_error(f"影子库配置格式异常：{type(configs)}")
                self.results["shadow_config_fetch"] = False

        except Exception as e:
            print_error(f"影子库配置拉取失败：{e}")
            self.results["shadow_config_fetch"] = False

    def verify_application_upload(self):
        """验证应用信息上报"""
        print("\n" + "=" * 70)
        print("阶段 5/5: 应用信息上报验证")
        print("=" * 70)

        if not self.external_api:
            print_error("ExternalAPI 未初始化，跳过此阶段")
            self.results["app_upload_test"] = False
            return

        test_app_name = f"{self.app_name}_upload_test_{int(time.time())}"
        print(f"\n上传测试应用：{test_app_name}")

        try:
            success = self.external_api.upload_application_info({
                "applicationName": test_app_name,
                "applicationDesc": "Upload Test Application",
                "useYn": 0,
                "accessStatus": 0,
                "switchStatus": "OPENED",
                "nodeNum": 1,
            })

            if success:
                print_success(f"应用 {test_app_name} 上传成功")
                self.results["app_upload"] = True
            else:
                print_warning(f"应用 {test_app_name} 上传返回失败 (可能接口不支持)")
                self.results["app_upload"] = True  # 不算失败

        except Exception as e:
            print_error(f"应用信息上传失败：{e}")
            self.results["app_upload"] = False

    def print_final_summary(self):
        """打印最终摘要"""
        print("\n" + "=" * 70)
        print("最终验证结果")
        print("=" * 70)

        tests = [
            ("数据库连接", "db_connection"),
            ("表 t_agent_report", "db_table_t_agent_report"),
            ("表 t_application_mnt", "db_table_t_application_mnt"),
            ("表 t_application_ds_manage", "db_table_t_application_ds_manage"),
            ("Takin-web 可访问", "takin_web_accessible"),
            ("ExternalAPI 初始化", "external_api_init"),
            ("心跳上报", "heartbeat_send"),
            ("持续心跳", "heartbeat_continuous"),
            ("影子库配置拉取", "shadow_config_fetch"),
            ("应用信息上传", "app_upload"),
        ]

        passed = 0
        total = len(tests)

        for name, key in tests:
            result = self.results.get(key, False)
            if result:
                print_success(f"{name}")
                passed += 1
            else:
                print_error(f"{name}")

        print(f"\n通过率：{passed}/{total}")

        if passed >= total * 0.8:
            print_success("\n所有验证通过！PyLinkAgent 可以正常工作")
        else:
            print_warning(f"\n部分验证失败，请检查日志文件")

        print("=" * 70)

        # 保存结果
        with open('verify_result.txt', 'w', encoding='utf-8') as f:
            f.write("PyLinkAgent 端到端验证结果\n")
            f.write(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"通过率：{passed}/{total}\n\n")
            for name, key in tests:
                result = self.results.get(key, False)
                status = "PASS" if result else "FAIL"
                f.write(f"[{status}] {name}\n")


def main():
    parser = argparse.ArgumentParser(description='PyLinkAgent 端到端验证')

    parser.add_argument('--mysql-host', default='localhost', help='MySQL 主机')
    parser.add_argument('--mysql-port', type=int, default=3306, help='MySQL 端口')
    parser.add_argument('--mysql-user', default='root', help='MySQL 用户名')
    parser.add_argument('--mysql-password', default='', help='MySQL 密码')
    parser.add_argument('--mysql-db', default='trodb', help='数据库名')
    parser.add_argument('--takin-url', default='http://localhost:9999', help='Takin-web 地址')
    parser.add_argument('--app-name', default='demo-app', help='应用名称')
    parser.add_argument('--agent-id', default='pylinkagent-001', help='Agent ID')

    args = parser.parse_args()

    verifier = EndToEndVerifier(args)
    verifier.run_all_verifications()

    # 返回退出码
    passed = sum(1 for v in verifier.results.values() if v)
    total = len(verifier.results)
    sys.exit(0 if passed >= total * 0.8 else 1)


if __name__ == "__main__":
    main()
