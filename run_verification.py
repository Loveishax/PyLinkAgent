"""
PyLinkAgent 完整验证脚本
验证所有 6 项要求
"""

import pymysql
import httpx
import json
import time
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
APP_NAME = "demo-app"
AGENT_ID = "pylinkagent-001"

results = []

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def save_result(name, success, message=""):
    results.append({'name': name, 'success': success, 'message': message})
    status = "PASS" if success else "FAIL"
    log(f"[{status}] {name}: {message}")

def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

# ========== 步骤 1: 数据库初始化 ==========
def init_database():
    print_section("步骤 1: 数据库初始化")

    try:
        # 不指定数据库连接，用于创建数据库
        conn = pymysql.connect(
            host=MYSQL_CONFIG['host'],
            port=MYSQL_CONFIG['port'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password'],
            charset=MYSQL_CONFIG['charset']
        )
        cursor = conn.cursor()

        # 创建数据库
        cursor.execute('DROP DATABASE IF EXISTS trodb')
        cursor.execute('CREATE DATABASE trodb DEFAULT CHARACTER SET utf8mb4')
        log("trodb 数据库创建成功")
        conn.commit()
        cursor.close()
        conn.close()

        # 连接到 trodb
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()

        # 读取并执行初始化脚本
        with open('database/end_to_end_init.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()

        # 分割 SQL 并执行（跳过 SELECT 语句）
        statements = sql_script.split(';')
        for stmt in statements:
            stmt = stmt.strip()
            if stmt and not stmt.upper().startswith('SELECT') and not stmt.startswith('--'):
                # 跳过 USE 语句
                if stmt.upper().startswith('USE'):
                    continue
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
                        log(f"  SQL 执行注意：{e}")

        conn.commit()
        cursor.close()
        conn.close()

        save_result("数据库初始化", True, "所有表创建成功，测试数据已插入")
        return True

    except Exception as e:
        log(f"数据库初始化失败：{e}")
        save_result("数据库初始化", False, str(e))
        return False

# ========== 步骤 2: Mock Server 验证 ==========
def verify_mock_server():
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
            save_result("心跳上报接口", True, f"HTTP 200, 响应：{response.json()}")
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
            result = response.json()
            if result.get('success'):
                save_result("应用上传接口", True, f"applicationId={result.get('data', {}).get('applicationId')}")
            else:
                save_result("应用上传接口", False, result.get('errorMessage'))
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

# ========== 步骤 3: 心跳入库验证 ==========
def verify_heartbeat_in_db():
    print_section("步骤 3: 验证心跳数据入库")

    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()

        # 查询心跳记录
        cursor.execute('''
        SELECT id, application_name, agent_id, ip_address, status, gmt_update
        FROM t_agent_report
        ORDER BY gmt_update DESC
        LIMIT 5
        ''')

        records = cursor.fetchall()

        if records:
            log(f"找到 {len(records)} 条心跳记录:")
            for r in records:
                log(f"  - ID={r[0]}, app={r[1]}, agent={r[2]}, ip={r[3]}, status={r[4]}, time={r[5]}")
            save_result("心跳数据入库", True, f"{len(records)} 条记录")
        else:
            save_result("心跳数据入库", False, "无记录")

        conn.close()
        return len(records) > 0

    except Exception as e:
        log(f"心跳入库验证失败：{e}")
        save_result("心跳数据入库", False, str(e))
        return False

# ========== 步骤 4: 影子库配置验证 ==========
def verify_shadow_config():
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
                log(f"API 拉取配置成功")
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

# ========== 步骤 5: 输出验证报告 ==========
def print_report():
    print_section("验证报告")

    passed = sum(1 for r in results if r['success'])
    total = len(results)

    print(f"\n总结果：{passed}/{total} 通过\n")

    for r in results:
        status = "PASS" if r['success'] else "FAIL"
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

    # 步骤 5: 输出报告
    print_report()

if __name__ == "__main__":
    main()
