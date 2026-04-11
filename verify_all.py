"""
PyLinkAgent 完整验证脚本 - 所有 6 项要求
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
    print(msg)

def save_result(name, success, message=""):
    results.append({'name': name, 'success': success, 'message': message})
    status = "PASS" if success else "FAIL"
    log(f"[{status}] {name}: {message}")

def print_section(title):
    log("\n" + "=" * 70)
    log(f"  {title}")
    log("=" * 70)

# ========== 步骤 1: 数据库初始化 ==========
def init_database():
    print_section("步骤 1: 数据库初始化验证")

    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()

        # 检查所有表是否存在
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['t_agent_report', 't_application_mnt', 't_application_ds_manage', 't_application_node_probe']
        all_exist = all(t in tables for t in required_tables)

        if all_exist:
            log(f"表列表：{tables}")
            save_result("数据库表结构", True, f"4 个核心表已创建：{', '.join(required_tables)}")
        else:
            save_result("数据库表结构", False, f"缺少表：{[t for t in required_tables if t not in tables]}")

        # 检查测试数据
        cursor.execute("SELECT APPLICATION_NAME FROM t_application_mnt WHERE APPLICATION_NAME='demo-app'")
        app = cursor.fetchone()
        if app:
            save_result("测试应用数据", True, "demo-app 已插入")
        else:
            save_result("测试应用数据", False, "demo-app 不存在")

        # 检查影子库配置
        cursor.execute("SELECT ID FROM t_application_ds_manage WHERE APPLICATION_NAME='demo-app' AND STATUS=0")
        config = cursor.fetchone()
        if config:
            save_result("影子库配置数据", True, "配置已插入")
        else:
            save_result("影子库配置数据", False, "配置不存在")

        cursor.close()
        conn.close()
        return all_exist

    except Exception as e:
        log(f"数据库初始化验证失败：{e}")
        save_result("数据库初始化验证", False, str(e))
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
            save_result("心跳数据入库", False, "无记录 - 请检查 Mock Server 日志")

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
                data = result.get('data', {})
                log(f"API 拉取配置成功:")
                if 'dataSources' in data:
                    for ds in data['dataSources']:
                        log(f"  - {ds.get('id')}: {ds.get('url')}")
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

# ========== 步骤 5: 压测流量路由验证 ==========
def verify_pressure_routing():
    print_section("步骤 5: 压测流量路由验证")

    try:
        # 检查 Demo 应用是否运行
        try:
            response = httpx.get("http://localhost:8000/health", timeout=5)
            if response.status_code != 200:
                log("Demo 应用未运行，跳过压测路由测试")
                save_result("压测流量路由", False, "Demo 应用未运行")
                return True
        except:
            log("Demo 应用未运行，跳过压测路由测试")
            save_result("压测流量路由", False, "Demo 应用不可访问")
            return True

        log("Demo 应用运行正常")

        # 测试正常流量
        response = httpx.get("http://localhost:8000/api/users", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                is_normal = not data[0].get('is_shadow', False)
                log(f"正常流量：{'普通数据' if is_normal else '影子数据'} - {data[0]}")
                save_result("正常流量路由", is_normal, data[0])

        # 测试压测流量
        response = httpx.get("http://localhost:8000/api/users", headers={"x-pressure-test": "true"}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                is_shadow = data[0].get('is_shadow', False)
                log(f"压测流量：{'影子数据' if is_shadow else '普通数据'} - {data[0]}")
                save_result("压测流量路由", is_shadow, data[0])

        # 验证 PyLinkAgent 状态
        response = httpx.get("http://localhost:8000/pylinkagent/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            log(f"PyLinkAgent 状态：{status}")
            save_result("PyLinkAgent 状态", status.get('available', False), status)

        return True

    except Exception as e:
        log(f"压测路由验证失败：{e}")
        save_result("压测路由验证", False, str(e))
        return False

# ========== 步骤 6: 输出验证报告 ==========
def print_report():
    print_section("验证报告")

    passed = sum(1 for r in results if r['success'])
    total = len(results)

    log(f"\n总结果：{passed}/{total} 通过\n")

    for r in results:
        status = "PASS" if r['success'] else "FAIL"
        log(f"  [{status}] {r['name']}: {r['message']}")

    log("\n" + "=" * 70)

    if passed == total:
        log("  所有验证通过!")
        log("\n下一步操作:")
        log("  1. 启动 Demo 应用：python demo_app.py")
        log("  2. 测试压测流量：curl http://localhost:8000/api/users -H 'x-pressure-test: true'")
        log("  3. 查看心跳记录：mysql -u root -p123456 -e 'SELECT * FROM trodb.t_agent_report'")
    else:
        log(f"  {total - passed} 项验证失败，请检查错误信息")

    log("=" * 70)

# ========== 主程序 ==========
def main():
    log("=" * 70)
    log(" PyLinkAgent 完整验证")
    log("=" * 70)
    log(f"MySQL: {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']} (root/123456)")
    log(f"Mock Server: {MOCK_SERVER_URL}")
    log(f"应用：{APP_NAME}")
    log(f"Agent ID: {AGENT_ID}")
    log("=" * 70)

    # 步骤 1: 数据库初始化验证
    init_database()

    # 步骤 2: Mock Server 验证
    verify_mock_server()

    # 步骤 3: 心跳入库验证
    verify_heartbeat_in_db()

    # 步骤 4: 影子库配置验证
    verify_shadow_config()

    # 步骤 5: 压测路由验证（可选）
    verify_pressure_routing()

    # 步骤 6: 输出报告
    print_report()

if __name__ == "__main__":
    main()
