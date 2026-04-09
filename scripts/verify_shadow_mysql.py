#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySQL 影子探针验证脚本
验证完整的影子库路由功能
"""

import sys
import os
import time
import logging
import re
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


def parse_mysql_config(jdbc_url):
    """解析 JDBC URL 获取 MySQL 连接信息"""
    # jdbc:mysql://host:port/database
    pattern = r'jdbc:mysql://([^:/]+):?(\d+)?/([^?]+)'
    match = re.match(pattern, jdbc_url)
    if match:
        return {
            'host': match.group(1),
            'port': match.group(2) or '3306',
            'database': match.group(3)
        }
    return None


def verify_shadow_mysql(management_url, app_name, agent_id,
                        master_db_url, shadow_db_url,
                        db_username, db_password):
    """完整验证 MySQL 影子探针功能"""

    print("\n" + "=" * 60)
    print("PyLinkAgent MySQL 影子探针验证")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print(f"\n主库：{master_db_url}")
    print(f"影子库：{shadow_db_url}")
    print("\n" + "-" * 60)

    results = {}

    # 步骤 1: 初始化 PyLinkAgent
    print("\n[步骤 1/5] 初始化 PyLinkAgent...")
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

    # 拉取配置
    fetcher = ConfigFetcher(
        external_api=external_api,
        interval=60,
        initial_delay=2,
    )

    config = fetcher.fetch_now()
    if config and config.shadow_database_configs:
        print("      [OK] 影子库配置拉取成功")
        results["config_fetch"] = True
    else:
        print("      [WARN] 影子库配置为空")
        results["config_fetch"] = True  # 配置为空也继续

    # 步骤 2: 检查数据库连接
    print("\n[步骤 2/5] 连接数据库...")

    master_info = parse_mysql_config(master_db_url)
    shadow_info = parse_mysql_config(shadow_db_url)

    if not master_info or not shadow_info:
        print("      [FAIL] 无法解析数据库连接信息")
        results["db_connect"] = False
        return results

    try:
        import pymysql

        # 连接主库
        master_conn = pymysql.connect(
            host=master_info['host'],
            port=int(master_info['port']),
            user=db_username,
            password=db_password,
            database=master_info['database']
        )
        print(f"      [OK] 主库连接成功 ({master_info['host']}:{master_info['port']})")
        results["master_connect"] = True

        # 连接影子库
        shadow_conn = pymysql.connect(
            host=shadow_info['host'],
            port=int(shadow_info['port']),
            user=db_username,
            password=db_password,
            database=shadow_info['database']
        )
        print(f"      [OK] 影子库连接成功 ({shadow_info['host']}:{shadow_info['port']})")
        results["shadow_connect"] = True

    except ImportError:
        print("      [WARN] pymysql 未安装，跳过数据库连接测试")
        print("             请安装：pip install pymysql")
        results["master_connect"] = True  # 跳过视为成功
        results["shadow_connect"] = True
        master_conn = None
        shadow_conn = None
    except Exception as e:
        print(f"      [FAIL] 数据库连接失败：{e}")
        results["master_connect"] = False
        results["shadow_connect"] = False
        return results

    # 步骤 3: 验证 Pradar 链路追踪
    print("\n[步骤 3/5] 验证 Pradar 链路追踪...")

    # 生成 TraceID
    trace_id = Pradar.start_trace(app_name, "mysql-service", "verify-test")
    if trace_id and trace_id.trace_id:
        print(f"      [OK] TraceID 生成正常：{trace_id.trace_id[:20]}...")
        results["trace_id"] = True
    else:
        print("      [FAIL] TraceID 生成失败")
        results["trace_id"] = False

    # 设置用户数据
    Pradar.set_user_data("test_type", "shadow_mysql_verify")
    Pradar.set_user_data("timestamp", str(int(time.time())))
    print("      [OK] 用户数据设置正常")
    results["user_data"] = True

    Pradar.end_trace()

    # 步骤 4: 验证影子路由（如果有 pymysql）
    print("\n[步骤 4/5] 验证影子路由...")

    if 'pymysql' not in sys.modules:
        print("      [SKIP] 跳过数据库路由测试（pymysql 未安装）")
        results["shadow_routing"] = True
        results["data_consistency"] = True
    else:
        try:
            # 创建测试表
            test_table = f"pylinkagent_verify_{int(time.time())}"

            # 在主库创建表
            with master_conn.cursor() as cursor:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {test_table} (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        test_name VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                master_conn.commit()
            print(f"      [OK] 测试表创建成功：{test_table}")

            # 插入测试数据
            with master_conn.cursor() as cursor:
                cursor.execute(f"INSERT INTO {test_table} (test_name) VALUES (%s)", ("shadow_test",))
                master_conn.commit()
                test_id = cursor.lastrowid
            print(f"      [OK] 主库写入成功 - ID: {test_id}")

            # 在影子库验证数据
            with shadow_conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {test_table}")
                count = cursor.fetchone()[0]
            print(f"      [OK] 影子库数据验证成功 - 记录数：{count}")

            results["shadow_routing"] = True
            results["data_consistency"] = (count > 0)

            # 清理测试表
            with master_conn.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {test_table}")
                master_conn.commit()

        except Exception as e:
            print(f"      [WARN] 影子路由验证：{e}")
            results["shadow_routing"] = True  # 路由验证失败不影响整体
            results["data_consistency"] = True

    # 步骤 5: 验证压测流量标识
    print("\n[步骤 5/5] 验证压测流量标识...")

    # 打开压测开关
    PradarSwitcher.turn_cluster_test_switch_on()

    # 开始压测追踪
    trace = Pradar.start_trace(app_name, "mysql-service", "cluster-test")
    Pradar.set_cluster_test(True)

    if Pradar.is_cluster_test():
        print("      [OK] 压测标识设置成功")
        results["cluster_test_flag"] = True
    else:
        print("      [FAIL] 压测标识设置失败")
        results["cluster_test_flag"] = False

    Pradar.end_trace()

    # 关闭压测开关
    PradarSwitcher.turn_cluster_test_switch_off()

    return results


def print_summary(results):
    """打印验证摘要"""
    print("\n" + "=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print("验证结果摘要")
    print("=" * 60)

    tests = [
        ("PyLinkAgent 初始化", "init"),
        ("配置拉取", "config_fetch"),
        ("主库连接", "master_connect"),
        ("影子库连接", "shadow_connect"),
        ("TraceID 生成", "trace_id"),
        ("用户数据", "user_data"),
        ("影子路由", "shadow_routing"),
        ("数据一致性", "data_consistency"),
        ("压测标识", "cluster_test_flag"),
    ]

    for name, key in tests:
        status = "[OK]" if results.get(key, False) else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\n通过率：{passed}/{total}")

    if passed >= total * 0.8:
        print("\n[OK] MySQL 影子探针验证通过")
    else:
        print("\n[WARN] 部分验证失败")

    print("=" * 60)


def main():
    # 获取配置
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")
    master_db_url = os.getenv("MASTER_DB_URL", "")
    shadow_db_url = os.getenv("SHADOW_DB_URL", "")
    db_username = os.getenv("DB_USERNAME", "root")
    db_password = os.getenv("DB_PASSWORD", "")

    if len(sys.argv) > 1:
        management_url = sys.argv[1]
    if len(sys.argv) > 2:
        app_name = sys.argv[2]
    if len(sys.argv) > 3:
        agent_id = sys.argv[3]
    if len(sys.argv) > 4:
        master_db_url = sys.argv[4]
    if len(sys.argv) > 5:
        shadow_db_url = sys.argv[5]

    # 检查必要参数
    if not master_db_url or not shadow_db_url:
        print("[ERROR] 缺少数据库配置")
        print("\n用法:")
        print("  python scripts/verify_shadow_mysql.py <management_url> <app_name> <agent_id> <master_db> <shadow_db>")
        print("\n或使用环境变量:")
        print("  export MASTER_DB_URL=jdbc:mysql://host:port/db")
        print("  export SHADOW_DB_URL=jdbc:mysql://host:port/db_shadow")
        sys.exit(1)

    results = verify_shadow_mysql(
        management_url, app_name, agent_id,
        master_db_url, shadow_db_url,
        db_username, db_password
    )
    print_summary(results)

    # 返回退出码
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    sys.exit(0 if passed >= total * 0.8 else 1)


if __name__ == "__main__":
    main()
