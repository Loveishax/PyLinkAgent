"""
PyLinkAgent Demo 应用

演示如何使用 PyLinkAgent 连接到管理侧
"""

import sys
import os
import time
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.heartbeat import HeartbeatReporter
from pylinkagent.controller.config_fetcher import ConfigFetcher
from pylinkagent.pradar import Pradar, PradarSwitcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 配置 ====================

# 管理侧地址
MANAGEMENT_URL = os.getenv("MANAGEMENT_URL", "http://localhost:9999")

# 应用信息
APP_NAME = os.getenv("APP_NAME", "demo-app")
AGENT_ID = os.getenv("AGENT_ID", "demo-agent-001")

# 心跳间隔 (秒)
HEARTBEAT_INTERVAL = 30

# 配置拉取间隔 (秒)
CONFIG_FETCH_INTERVAL = 60


def main():
    """主函数"""

    print("\n" + "=" * 60)
    print("PyLinkAgent Demo 应用")
    print("=" * 60)
    print(f"\n管理侧地址：{MANAGEMENT_URL}")
    print(f"应用名称：{APP_NAME}")
    print(f"Agent ID: {AGENT_ID}")
    print("\n" + "-" * 60)

    # 1. 初始化 ExternalAPI
    print("\n[1/5] 初始化 ExternalAPI...")
    external_api = ExternalAPI(
        tro_web_url=MANAGEMENT_URL,
        app_name=APP_NAME,
        agent_id=AGENT_ID,
    )

    if not external_api.initialize():
        print("[FAIL] ExternalAPI 初始化失败")
        return

    print("[OK] ExternalAPI 初始化成功")

    # 2. 启动心跳上报
    print("\n[2/5] 启动心跳上报...")
    heartbeat_reporter = HeartbeatReporter(
        external_api=external_api,
        interval=HEARTBEAT_INTERVAL,
    )

    if heartbeat_reporter.start():
        print("[OK] 心跳上报已启动")
    else:
        print("[FAIL] 心跳上报启动失败")

    # 3. 启动配置拉取
    print("\n[3/5] 启动配置拉取...")
    config_fetcher = ConfigFetcher(
        external_api=external_api,
        interval=CONFIG_FETCH_INTERVAL,
        initial_delay=5,
    )

    # 注册配置变更回调
    def on_config_change(key, old_value, new_value):
        logger.info(f"[配置变更] {key}")
        print(f"[配置变更] {key}")

    config_fetcher.on_config_change(on_config_change)

    if config_fetcher.start():
        print("[OK] 配置拉取已启动")
    else:
        print("[FAIL] 配置拉取启动失败")

    # 4. 初次配置拉取
    print("\n[4/5] 初次配置拉取...")
    config = config_fetcher.fetch_now()
    if config:
        print("[OK] 配置拉取成功")
        print(f"     影子库配置：{len(config.shadow_database_configs)}")
        print(f"     全局开关：{len(config.global_switch)}")
        print(f"     URL 白名单：{len(config.url_white_list)}")
    else:
        print("[WARN] 配置拉取返回空")

    # 5. 模拟业务运行
    print("\n[5/5] 模拟业务运行...")
    print("[INFO] 按 Ctrl+C 退出\n")

    try:
        # 模拟业务运行，每 10 秒打印一次状态
        start_time = time.time()
        iteration = 0

        while True:
            iteration += 1
            elapsed = int(time.time() - start_time)

            # 获取心跳成功次数
            success_count = heartbeat_reporter.external_api._client and getattr(
                heartbeat_reporter.external_api, '_success_heartbeat_count',
                heartbeat_reporter._executor is not None
            )

            print(f"[状态] 运行 {elapsed}秒 - 心跳正常 - 配置拉取正常")

            # 演示 Pradar 链路追踪
            if iteration % 3 == 0:
                # 开始追踪
                ctx = Pradar.start_trace(APP_NAME, "demo-service", "demo-method")

                # 设置压测标识
                if PradarSwitcher.is_cluster_test_enabled():
                    Pradar.set_cluster_test(True)

                # 设置用户数据
                Pradar.set_user_data("iteration", str(iteration))

                # 模拟业务处理
                time.sleep(0.1)

                # 结束追踪
                Pradar.end_trace()

                print(f"  [Pradar] 完成追踪：trace_id={ctx.trace_id[:20]}...")

            time.sleep(10)

    except KeyboardInterrupt:
        print("\n\n[INFO] 用户中断，正在关闭...")
    finally:
        # 关闭服务
        print("\n[INFO] 关闭心跳上报...")
        heartbeat_reporter.stop()

        print("[INFO] 关闭配置拉取...")
        config_fetcher.stop()

        print("[INFO] 关闭 ExternalAPI...")
        external_api.shutdown()

        print("\n[OK] Demo 应用已退出")


if __name__ == "__main__":
    main()
