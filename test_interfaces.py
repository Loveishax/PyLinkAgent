"""
PyLinkAgent 接口验证脚本（不依赖数据库）

验证目标：
1. 心跳上报接口正常工作
2. 应用上传接口正常工作
3. 影子库配置拉取接口正常工作
4. Mock Server 与原始 Takin-web 接口一致
"""

import httpx
import json
import time

MOCK_SERVER_URL = "http://localhost:9999"
APP_NAME = "demo-app"
AGENT_ID = "pylinkagent-001"


def print_result(success: bool, message: str):
    """打印结果"""
    status = "OK" if success else "FAIL"
    print(f"[{status}] {message}")


def test_heartbeat():
    """测试心跳上报"""
    print("\n" + "=" * 50)
    print("测试 1: 心跳上报接口")
    print("=" * 50)

    heartbeat_data = {
        "projectName": APP_NAME,
        "agentId": AGENT_ID,
        "ipAddress": "127.0.0.1",
        "progressId": str(int(time.time())),
        "curUpgradeBatch": "1",
        "agentStatus": "running",
        "agentErrorInfo": "",
        "simulatorStatus": "running",
        "simulatorErrorInfo": "",
        "uninstallStatus": 0,
        "dormantStatus": 0,
        "agentVersion": "1.0.0",
        "simulatorVersion": "1.0.0",
        "dependencyInfo": "",
        "flag": "shulieEnterprise"
    }

    try:
        response = httpx.post(
            f"{MOCK_SERVER_URL}/api/agent/heartbeat",
            json=heartbeat_data,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print_result(True, f"心跳上报成功")
            print(f"     响应数据：{result}")
            print(f"     说明：心跳数据会写入 t_agent_report 表")
            return True
        else:
            print_result(False, f"心跳上报失败：{response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"心跳上报异常：{e}")
        return False


def test_application_upload():
    """测试应用上传"""
    print("\n" + "=" * 50)
    print("测试 2: 应用上传接口")
    print("=" * 50)

    app_data = {
        "applicationName": APP_NAME,
        "applicationDesc": "Demo Application for PyLinkAgent",
        "useYn": 0,
        "accessStatus": 0,
        "switchStatus": "OPENED",
        "envCode": "test",
        "tenantId": 1
    }

    try:
        response = httpx.post(
            f"{MOCK_SERVER_URL}/api/application/center/app/info",
            json=app_data,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print_result(True, f"应用上传成功")
            print(f"     响应数据：{result}")
            print(f"     说明：应用数据会写入 t_application_mnt 表")
            return True
        else:
            print_result(False, f"应用上传失败：{response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"应用上传异常：{e}")
        return False


def test_shadow_config_fetch():
    """测试影子库配置拉取"""
    print("\n" + "=" * 50)
    print("测试 3: 影子库配置拉取接口")
    print("=" * 50)

    try:
        response = httpx.get(
            f"{MOCK_SERVER_URL}/api/link/ds/configs/pull",
            params={"appName": APP_NAME},
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print_result(True, f"影子库配置拉取成功")
                config_data = result.get('data', {})
                print(f"     配置内容:")
                print(f"     {json.dumps(config_data, indent=2, ensure_ascii=False)}")
                print(f"     说明：配置从 t_application_ds_manage 表读取")
                return True
            else:
                print_result(False, f"影子库配置拉取失败：{result}")
                return False
        else:
            print_result(False, f"影子库配置拉取失败：{response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"影子库配置拉取异常：{e}")
        return False


def test_command_pull():
    """测试命令拉取"""
    print("\n" + "=" * 50)
    print("测试 4: 命令拉取接口")
    print("=" * 50)

    try:
        response = httpx.get(
            f"{MOCK_SERVER_URL}/api/agent/application/node/probe/operate",
            params={"applicationName": APP_NAME, "agentId": AGENT_ID},
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print_result(True, f"命令拉取成功")
            print(f"     响应数据：{result}")
            print(f"     说明：无待执行命令时返回空数组")
            return True
        else:
            print_result(False, f"命令拉取失败：{response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"命令拉取异常：{e}")
        return False


def test_command_result_report():
    """测试命令结果上报"""
    print("\n" + "=" * 50)
    print("测试 5: 命令结果上报接口")
    print("=" * 50)

    report_data = {
        "appName": APP_NAME,
        "agentId": AGENT_ID,
        "commandId": 1,
        "success": True,
        "errorMsg": ""
    }

    try:
        response = httpx.post(
            f"{MOCK_SERVER_URL}/api/agent/application/node/probe/operateResult",
            json=report_data,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print_result(True, f"命令结果上报成功")
                print(f"     响应数据：{result}")
                print(f"     说明：结果会写入 t_application_node_probe 表")
                return True
            else:
                print_result(False, f"命令结果上报失败：{result}")
                return False
        else:
            print_result(False, f"命令结果上报失败：{response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"命令结果上报异常：{e}")
        return False


def test_health_check():
    """测试健康检查"""
    print("\n" + "=" * 50)
    print("测试 0: Mock Server 健康检查")
    print("=" * 50)

    try:
        response = httpx.get(f"{MOCK_SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            result = response.json()
            print_result(True, f"Mock Server 运行正常")
            print(f"     状态：{result.get('status')}")
            print(f"     时间戳：{result.get('timestamp')}")
            return True
        else:
            print_result(False, f"Mock Server 状态异常：{response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Mock Server 不可访问：{e}")
        return False


def main():
    print("#" * 60)
    print("# PyLinkAgent 接口验证")
    print("#" * 60)
    print(f"Mock Server: {MOCK_SERVER_URL}")
    print(f"测试应用：{APP_NAME}")
    print(f"Agent ID: {AGENT_ID}")
    print("#" * 60)

    results = []

    # 测试健康检查
    results.append(("健康检查", test_health_check()))

    # 测试心跳上报
    results.append(("心跳上报", test_heartbeat()))

    # 测试应用上传
    results.append(("应用上传", test_application_upload()))

    # 测试影子库配置拉取
    results.append(("影子库配置拉取", test_shadow_config_fetch()))

    # 测试命令拉取
    results.append(("命令拉取", test_command_pull()))

    # 测试命令结果上报
    results.append(("命令结果上报", test_command_result_report()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\n总计：{passed}/{total} 通过")

    if passed == total:
        print("\n所有接口验证通过!")
        print("\n数据库表对应关系:")
        print("  1. 心跳上报 -> t_agent_report")
        print("  2. 应用上传 -> t_application_mnt")
        print("  3. 影子库配置 -> t_application_ds_manage")
        print("  4. 命令结果 -> t_application_node_probe")
        print("\n要验证完整数据库流程，请:")
        print("  1. 确保 MySQL 服务已启动")
        print("  2. 执行：mysql -u root -p < database/end_to_end_init.sql")
        print("  3. 运行：python verify_full_cycle.py --mysql-password your_password")
        return True
    else:
        print(f"\n{total - passed} 个测试失败，请检查 Mock Server 状态")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
