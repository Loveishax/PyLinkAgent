"""
PyLinkAgent 与管理侧对接验证测试

验证 PyLinkAgent 能否：
1. 正常上报心跳到管理侧
2. 从管理侧成功拉取影子配置
3. 接收并处理命令
"""

import logging
import time
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.heartbeat import HeartbeatReporter
from pylinkagent.controller.config_fetcher import ConfigFetcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 配置 ====================

# 管理侧地址
MANAGEMENT_URL = "http://localhost:9999"

# 应用信息
APP_NAME = "test-app"
AGENT_ID = "test-agent-001"

# 心跳间隔 (秒)
HEARTBEAT_INTERVAL = 10

# 配置拉取间隔 (秒)
CONFIG_FETCH_INTERVAL = 15


def test_external_api_connection():
    """测试 1: 测试 ExternalAPI 连接"""
    print("\n" + "=" * 60)
    print("测试 1: 测试 ExternalAPI 连接")
    print("=" * 60)

    external_api = ExternalAPI(
        tro_web_url=MANAGEMENT_URL,
        app_name=APP_NAME,
        agent_id=AGENT_ID,
    )

    # 尝试初始化
    logger.info(f"正在连接管理侧：{MANAGEMENT_URL}")
    success = external_api.initialize()

    if success:
        print("[OK] ExternalAPI 初始化成功")
        return external_api
    else:
        print("[FAIL] ExternalAPI 初始化失败")
        print("  可能原因:")
        print("  1. 管理侧服务未启动")
        print("  2. 网络不通")
        print("  3. API 路径不匹配")
        return None


def test_heartbeat(external_api):
    """测试 2: 测试心跳上报"""
    print("\n" + "=" * 60)
    print("测试 2: 测试心跳上报")
    print("=" * 60)

    # 构建心跳请求
    heart_request = HeartRequest(
        project_name=external_api.app_name,
        agent_id=external_api.agent_id,
        ip_address="127.0.0.1",
        progress_id=str(os.getpid()),
        agent_status="running",
        agent_version="1.0.0",
    )

    logger.info("发送心跳请求...")
    try:
        commands = external_api.send_heartbeat(heart_request)
        print(f"[OK] 心跳发送成功")
        print(f"  返回命令数：{len(commands)}")
        return True
    except Exception as e:
        print(f"[FAIL] 心跳发送失败：{e}")
        return False


def test_heartbeat_reporter(external_api):
    """测试 3: 测试心跳上报器"""
    print("\n" + "=" * 60)
    print("测试 3: 测试心跳上报器 (自动心跳)")
    print("=" * 60)

    reporter = HeartbeatReporter(
        external_api=external_api,
        interval=HEARTBEAT_INTERVAL,
    )

    # 启动心跳
    logger.info("启动心跳上报器...")
    success = reporter.start()

    if success:
        print(f"[OK] 心跳上报器启动成功 (interval={HEARTBEAT_INTERVAL}s)")
        print("  等待 30 秒观察心跳...")
        time.sleep(30)
        reporter.stop()
        print("[OK] 心跳上报器已停止")
        return True
    else:
        print("[FAIL] 心跳上报器启动失败")
        return False


def test_config_fetcher(external_api):
    """测试 4: 测试配置拉取"""
    print("\n" + "=" * 60)
    print("测试 4: 测试配置拉取")
    print("=" * 60)

    fetcher = ConfigFetcher(
        external_api=external_api,
        interval=CONFIG_FETCH_INTERVAL,
    )

    # 立即拉取一次
    logger.info("立即拉取配置...")
    try:
        config = fetcher.fetch_now()
        if config:
            print("[OK] 配置拉取成功")
            print(f"  影子库配置数：{len(config.shadow_database_configs)}")
            print(f"  全局开关数：{len(config.global_switch)}")
            print(f"  Redis 影子配置数：{len(config.redis_shadow_configs)}")
            print(f"  MQ 白名单数：{len(config.mq_white_list)}")
            print(f"  RPC 白名单数：{len(config.rpc_white_list)}")
            print(f"  URL 白名单数：{len(config.url_white_list)}")
            return True
        else:
            print("[WARN] 配置拉取返回空 (可能管理侧没有配置)")
            return True
    except Exception as e:
        print(f"[FAIL] 配置拉取失败：{e}")
        return False


def test_config_fetcher_loop(external_api):
    """测试 5: 测试配置拉取器 (自动轮询)"""
    print("\n" + "=" * 60)
    print("测试 5: 测试配置拉取器 (自动轮询)")
    print("=" * 60)

    fetcher = ConfigFetcher(
        external_api=external_api,
        interval=CONFIG_FETCH_INTERVAL,
        initial_delay=5,
    )

    # 注册配置变更回调
    def on_config_change(key, old_value, new_value):
        logger.info(f"配置变更：{key}")
        print(f"  [配置变更] {key}")

    fetcher.on_config_change(on_config_change)

    # 启动拉取
    logger.info("启动配置拉取器...")
    success = fetcher.start()

    if success:
        print(f"[OK] 配置拉取器启动成功 (interval={CONFIG_FETCH_INTERVAL}s)")
        print("  等待 45 秒观察配置拉取...")
        time.sleep(45)
        fetcher.stop()
        print("[OK] 配置拉取器已停止")
        return True
    else:
        print("[FAIL] 配置拉取器启动失败")
        return False


def test_full_integration():
    """完整集成测试"""
    print("\n")
    print("#" * 60)
    print("# PyLinkAgent 与管理侧对接验证测试")
    print("#" * 60)
    print(f"\n管理侧地址：{MANAGEMENT_URL}")
    print(f"应用名称：{APP_NAME}")
    print(f"Agent ID: {AGENT_ID}")

    results = {
        "ExternalAPI 连接": False,
        "心跳上报": False,
        "心跳上报器": False,
        "配置拉取": False,
        "配置拉取器": False,
    }

    # 测试 1: ExternalAPI 连接
    external_api = test_external_api_connection()
    if external_api:
        results["ExternalAPI 连接"] = True

    if not external_api:
        print("\n" + "=" * 60)
        print("由于 ExternalAPI 初始化失败，后续测试已跳过")
        print("=" * 60)
        print_results(results)
        return False

    time.sleep(2)

    # 测试 2: 心跳上报
    results["心跳上报"] = test_heartbeat(external_api)
    time.sleep(2)

    # 测试 3: 心跳上报器
    results["心跳上报器"] = test_heartbeat_reporter(external_api)
    time.sleep(2)

    # 测试 4: 配置拉取
    results["配置拉取"] = test_config_fetcher(external_api)
    time.sleep(2)

    # 测试 5: 配置拉取器
    results["配置拉取器"] = test_config_fetcher_loop(external_api)

    # 打印结果
    print_results(results)

    # 判断是否全部通过
    all_passed = all(results.values())
    if all_passed:
        print("\n✓ 所有测试通过！")
    else:
        print("\n✗ 部分测试失败")

    return all_passed


def print_results(results):
    """打印测试结果"""
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {test_name}: {'通过' if passed else '失败'}")

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"\n通过率：{passed_count}/{total_count}")


if __name__ == "__main__":
    try:
        success = test_full_integration()
        if success:
            print("\n[OK] 所有测试通过！")
        else:
            print("\n[FAIL] 部分测试失败")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n测试异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
