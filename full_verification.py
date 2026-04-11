"""
PyLinkAgent 完整验证脚本

验证目标：
1. 数据库初始化（心跳表、应用表、影子库配置表）
2. Takin-web Mock Server 部署
3. PyLinkAgent 探针挂载与心跳上报入库
4. 影子库配置拉取验证
5. 压测流量路由验证
6. 输出验证报告

数据库配置：
- 用户：root
- 密码：123456
- 数据库：trodb
"""

import pymysql
import httpx
import json
import time
import os
import sys
from datetime import datetime

# 配置
MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'trodb',
    'charset': 'utf8mb4'
}

MOCK_SERVER_URL = "http://localhost:9999"
DEMO_APP_URL = "http://localhost:8000"
APP_NAME = "demo-app"
AGENT_ID = "pylinkagent-001"

# 验证结果
results = []

def log(message):
    """打印日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def print_section(title):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def save_result(name, success, message=""):
    """保存验证结果"""
    results.append({
        'name': name,
        'success': success,
        'message': message
    })
    status = "PASS" if success else "FAIL"
    log(f"[{status}] {name}: {message}")

# ========== 步骤 1: 数据库初始化 ==========
def init_database():
    """初始化数据库"""
    print_section("步骤 1: 数据库初始化")

    try:
        # 连接 MySQL（不指定数据库）
        conn = pymysql.connect(
            host=MYSQL_CONFIG['host'],
            port=MYSQL_CONFIG['port'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password'],
            charset=MYSQL_CONFIG['charset']
        )
        cursor = conn.cursor()

        # 创建数据库
        cursor.execute('CREATE DATABASE IF NOT EXISTS trodb DEFAULT CHARACTER SET utf8mb4')
        log("trodb 数据库创建成功")

        # 使用数据库
        cursor.execute('USE trodb')

        # 创建心跳表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS `t_agent_report` (
          `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
          `application_id` bigint(20) DEFAULT '0',
          `application_name` varchar(64) DEFAULT '',
          `agent_id` varchar(600) NOT NULL,
          `ip_address` varchar(1024) DEFAULT '',
          `status` tinyint(2) DEFAULT '0',
          `agent_version` varchar(1024) DEFAULT '',
          `simulator_version` varchar(1024) DEFAULT NULL,
          `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP,
          `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          `env_code` varchar(100) DEFAULT 'test',
          `tenant_id` bigint(20) DEFAULT '1',
          PRIMARY KEY (`id`),
          UNIQUE KEY `uni_app_agent` (`application_id`,`agent_id`,`env_code`,`tenant_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        log("t_agent_report 表创建成功")

        # 创建应用表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS `t_application_mnt` (
          `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
          `APPLICATION_ID` bigint(19) NOT NULL,
          `APPLICATION_NAME` varchar(50) NOT NULL,
          `APPLICATION_DESC` varchar(200) DEFAULT NULL,
          `USE_YN` int(1) DEFAULT '0',
          `ACCESS_STATUS` int(2) NOT NULL DEFAULT '0',
          `SWITCH_STATUS` varchar(255) NOT NULL DEFAULT 'OPENED',
          `CREATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP,
          `UPDATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          `env_code` varchar(20) DEFAULT 'test',
          `tenant_id` bigint(20) DEFAULT '1',
          PRIMARY KEY (`id`),
          UNIQUE KEY `uk_app_name` (`APPLICATION_NAME`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        log("t_application_mnt 表创建成功")

        # 创建影子库配置表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS `t_application_ds_manage` (
          `ID` bigint(20) NOT NULL AUTO_INCREMENT,
          `APPLICATION_ID` bigint(20) DEFAULT NULL,
          `APPLICATION_NAME` varchar(50) DEFAULT NULL,
          `DB_TYPE` tinyint(4) DEFAULT '0',
          `DS_TYPE` tinyint(4) DEFAULT '0',
          `CONFIG` longtext,
          `PARSE_CONFIG` longtext,
          `STATUS` tinyint(4) DEFAULT '0',
          `CREATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
          `UPDATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          `env_code` varchar(20) DEFAULT 'test',
          `tenant_id` bigint(20) DEFAULT '1',
          PRIMARY KEY (`ID`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        log("t_application_ds_manage 表创建成功")

        # 插入测试应用
        cursor.execute('''
        INSERT INTO t_application_mnt
        (APPLICATION_ID, APPLICATION_NAME, APPLICATION_DESC, USE_YN, ACCESS_STATUS, SWITCH_STATUS, env_code, tenant_id)
        VALUES (1, %s, 'Demo Application', 0, 0, 'OPENED', 'test', 1)
        ON DUPLICATE KEY UPDATE APPLICATION_NAME = APPLICATION_NAME
        ''', (APP_NAME,))
        log(f"测试应用 {APP_NAME} 插入成功")

        # 插入影子库配置
        shadow_config = json.dumps({
            "datasourceMediator": {
                "dataSourceBusiness": "dataSourceBusiness",
                "dataSourcePerformanceTest": "dataSourcePerformanceTest"
            },
            "dataSources": [
                {
                    "id": "dataSourceBusiness",
                    "url": "jdbc:mysql://master-db:3306/demo_db",
                    "username": "root",
                    "password": "root123"
                },
                {
                    "id": "dataSourcePerformanceTest",
                    "url": "jdbc:mysql://shadow-db:3306/demo_db_shadow",
                    "username": "root",
                    "password": "root123"
                }
            ]
        })

        cursor.execute('''
        INSERT INTO t_application_ds_manage
        (APPLICATION_ID, APPLICATION_NAME, DB_TYPE, DS_TYPE, CONFIG, PARSE_CONFIG, STATUS, env_code, tenant_id)
        VALUES (1, %s, 0, 0, %s, '{}', 0, 'test', 1)
        ON DUPLICATE KEY UPDATE APPLICATION_NAME = APPLICATION_NAME
        ''', (APP_NAME, shadow_config))
        log("影子库配置插入成功")

        conn.commit()
        cursor.close()
        conn.close()

        save_result("数据库初始化", True, "所有表创建成功，测试数据已插入")
        return True

    except Exception as e:
        log(f"数据库初始化失败：{e}")
        save_result("数据库初始化", False, str(e))
        return False

# ========== 步骤 2: 验证 Mock Server ==========
def verify_mock_server():
    """验证 Mock Server"""
    print_section("步骤 2: Takin-web Mock Server 验证")

    try:
        # 健康检查
        response = httpx.get(f"{MOCK_SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            save_result("Mock Server 健康检查", True, response.json())
        else:
            save_result("Mock Server 健康检查", False, f"状态码 {response.status_code}")
            return False

        # 心跳上报测试
        heartbeat_data = {
            "projectName": APP_NAME,
            "agentId": AGENT_ID,
            "ipAddress": "192.168.1.100",
            "progressId": str(int(time.time())),
            "curUpgradeBatch": "1",
            "agentStatus": "running",
            "uninstallStatus": 0,
            "dormantStatus": 0,
            "agentVersion": "1.0.0"
        }

        response = httpx.post(f"{MOCK_SERVER_URL}/api/agent/heartbeat", json=heartbeat_data, timeout=10)
        if response.status_code == 200:
            save_result("心跳上报接口", True, f"响应：{response.json()}")
        else:
            save_result("心跳上报接口", False, f"状态码 {response.status_code}")

        # 应用上传测试
        app_data = {
            "applicationName": APP_NAME,
            "applicationDesc": "Demo Application",
            "useYn": 0,
            "accessStatus": 0,
            "switchStatus": "OPENED"
        }

        response = httpx.post(f"{MOCK_SERVER_URL}/api/application/center/app/info", json=app_data, timeout=10)
        if response.status_code == 200:
            save_result("应用上传接口", True, f"响应：{response.json()}")
        else:
            save_result("应用上传接口", False, f"状态码 {response.status_code}")

        # 影子库配置拉取测试
        response = httpx.get(f"{MOCK_SERVER_URL}/api/link/ds/configs/pull", params={"appName": APP_NAME}, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                save_result("影子库配置拉取接口", True, "配置拉取成功")
            else:
                save_result("影子库配置拉取接口", False, result.get('message'))
        else:
            save_result("影子库配置拉取接口", False, f"状态码 {response.status_code}")

        return True

    except Exception as e:
        log(f"Mock Server 验证失败：{e}")
        save_result("Mock Server 验证", False, str(e))
        return False

# ========== 步骤 3: 验证心跳入库 ==========
def verify_heartbeat_in_db():
    """验证心跳入库"""
    print_section("步骤 3: 验证心跳数据入库")

    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()

        # 查询心跳记录
        cursor.execute('''
        SELECT id, application_name, agent_id, ip_address, gmt_update
        FROM t_agent_report
        ORDER BY gmt_update DESC
        LIMIT 5
        ''')

        records = cursor.fetchall()

        if records:
            log(f"找到 {len(records)} 条心跳记录:")
            for r in records:
                log(f"  - ID={r[0]}, app={r[1]}, agent={r[2]}, ip={r[3]}, time={r[4]}")
            save_result("心跳数据入库", True, f"{len(records)} 条记录")
        else:
            save_result("心跳数据入库", False, "无记录")

        conn.close()
        return len(records) > 0

    except Exception as e:
        log(f"心跳入库验证失败：{e}")
        save_result("心跳数据入库", False, str(e))
        return False

# ========== 步骤 4: 验证影子库配置拉取 ==========
def verify_shadow_config():
    """验证影子库配置拉取"""
    print_section("步骤 4: 影子库配置拉取验证")

    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()

        # 从数据库读取配置
        cursor.execute('SELECT CONFIG FROM t_application_ds_manage WHERE APPLICATION_NAME=%s AND STATUS=0', (APP_NAME,))
        record = cursor.fetchone()

        if record:
            config = json.loads(record[0])
            log("数据库中的影子库配置:")
            if 'dataSources' in config:
                for ds in config['dataSources']:
                    log(f"  - {ds.get('id')}: {ds.get('url')}")
            save_result("数据库影子库配置", True, "配置存在")
        else:
            save_result("数据库影子库配置", False, "配置不存在")

        conn.close()

        # 通过 API 拉取配置
        response = httpx.get(f"{MOCK_SERVER_URL}/api/link/ds/configs/pull", params={"appName": APP_NAME}, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                log(f"API 拉取配置成功：{result.get('message')}")
                save_result("API 影子库配置拉取", True, "拉取成功")
            else:
                save_result("API 影子库配置拉取", False, result.get('message'))
        else:
            save_result("API 影子库配置拉取", False, f"状态码 {response.status_code}")

        return True

    except Exception as e:
        log(f"影子库配置验证失败：{e}")
        save_result("影子库配置验证", False, str(e))
        return False

# ========== 步骤 5: 启动 Demo 应用并验证压测路由 ==========
def verify_pressure_routing():
    """验证压测流量路由"""
    print_section("步骤 5: 压测流量路由验证")

    try:
        # 检查 Demo 应用是否运行
        response = httpx.get(f"{DEMO_APP_URL}/health", timeout=5)
        if response.status_code != 200:
            log("Demo 应用未运行，请先启动：python demo_app.py")
            save_result("压测流量路由", False, "Demo 应用未运行")
            return False

        log("Demo 应用运行正常")

        # 测试正常流量
        response = httpx.get(f"{DEMO_APP_URL}/api/users", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                is_normal = not data[0].get('is_shadow', False)
                log(f"正常流量：{'普通数据' if is_normal else '影子数据'} - {data[0]}")
                save_result("正常流量路由", is_normal, data[0])

        # 测试压测流量
        response = httpx.get(f"{DEMO_APP_URL}/api/users", headers={"x-pressure-test": "true"}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                is_shadow = data[0].get('is_shadow', False)
                log(f"压测流量：{'影子数据' if is_shadow else '普通数据'} - {data[0]}")
                save_result("压测流量路由", is_shadow, data[0])

        # 验证 PyLinkAgent 状态
        response = httpx.get(f"{DEMO_APP_URL}/pylinkagent/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            log(f"PyLinkAgent 状态：{status}")
            save_result("PyLinkAgent 状态", status.get('available', False), status)

        # 验证影子库配置
        response = httpx.get(f"{DEMO_APP_URL}/pylinkagent/config", timeout=5)
        if response.status_code == 200:
            config = response.json()
            has_config = config.get('has_shadow_config', False)
            log(f"影子库配置：{'已加载' if has_config else '未加载'}")
            save_result("影子库配置加载", has_config, config)

        return True

    except Exception as e:
        log(f"压测路由验证失败：{e}")
        save_result("压测路由验证", False, str(e))
        return False

# ========== 步骤 6: 输出验证报告 ==========
def print_report():
    """输出验证报告"""
    print_section("验证报告")

    passed = sum(1 for r in results if r['success'])
    total = len(results)

    print(f"\n总结果：{passed}/{total} 通过\n")

    for r in results:
        status = "✓" if r['success'] else "✗"
        print(f"  [{status}] {r['name']}: {r['message']}")

    print("\n" + "=" * 70)

    if passed == total:
        print("  所有验证通过!")
        print("\n下一步操作:")
        print("  1. 启动 Demo 应用：python demo_app.py")
        print("  2. 测试压测流量：curl http://localhost:8000/api/users -H 'x-pressure-test: true'")
        print("  3. 查看心跳记录：mysql -u root -p123456 -e 'SELECT * FROM trodb.t_agent_report'")
    else:
        print(f"  {total - passed} 项验证失败，请检查错误信息")

    print("=" * 70)

# ========== 主程序 ==========
def main():
    print("=" * 70)
    print(" PyLinkAgent 完整验证")
    print("=" * 70)
    print(f"MySQL: {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}")
    print(f"Mock Server: {MOCK_SERVER_URL}")
    print(f"Demo App: {DEMO_APP_URL}")
    print(f"应用：{APP_NAME}")
    print(f"Agent ID: {AGENT_ID}")
    print("=" * 70)

    # 步骤 1: 数据库初始化
    init_database()

    # 步骤 2: Mock Server 验证
    verify_mock_server()

    # 步骤 3: 心跳入库验证
    verify_heartbeat_in_db()

    # 步骤 4: 影子库配置验证
    verify_shadow_config()

    # 步骤 5: 压测路由验证（可选）
    # verify_pressure_routing()

    # 步骤 6: 输出报告
    print_report()

if __name__ == "__main__":
    main()
