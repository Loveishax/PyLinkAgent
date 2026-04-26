"""
PyLinkAgent 主启动器

整合 HTTP 心跳和 ZooKeeper 心跳，提供完整的 Agent 启动流程
"""

import os
import sys
import time
import signal
import logging
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PyLinkAgentBootstrapper:
    """
    PyLinkAgent 启动器

    负责初始化和管理 Agent 的完整生命周期
    """

    def __init__(self):
        """初始化启动器"""
        self._external_api = None
        self._config_fetcher = None
        self._heartbeat_reporter = None
        self._command_poller = None
        self._zk_integration = None
        self._app_registrator = None
        self._shadow_enabled = False
        self._shadow_interceptors = []
        self._is_running = False
        self._shutdown_hooks = []

    def bootstrap(self) -> bool:
        """
        启动 Agent

        Returns:
            bool: 启动成功返回 True
        """
        logger.info("=" * 60)
        logger.info("PyLinkAgent 启动中...")
        logger.info("=" * 60)

        try:
            # 1. 初始化 HTTP ExternalAPI
            if not self._init_external_api():
                logger.error("HTTP ExternalAPI 初始化失败")
                return False

            # 2. 应用自动注册 (P0 任务)
            self._register_application()

            # 3. 初始化 ZooKeeper (P0 任务)
            self._init_zookeeper()

            # 4. 启动配置拉取器
            if not self._start_config_fetcher():
                logger.warning("配置拉取器启动失败，继续启动")

            # 5. 初始化运行时开关和白名单
            self._init_runtime_config()

            # 6. 启动影子路由 (P0 核心功能)
            self._init_shadow_routing()

            # 7. 启动心跳上报 (HTTP)
            if not self._start_heartbeat_reporter():
                logger.error("心跳上报启动失败")
                return False

            # 8. 启动命令轮询器
            if not self._start_command_poller():
                logger.warning("命令轮询器启动失败，继续启动")

            # 9. 注册关闭钩子
            self._register_shutdown_hooks()

            self._is_running = True
            logger.info("=" * 60)
            logger.info("PyLinkAgent 启动完成")
            logger.info(f"  HTTP 心跳：启用")
            logger.info(f"  影子路由：{'已启用' if self._shadow_enabled else '未启用'}")
            logger.info(f"  ZK 心跳：{'启用' if self._zk_integration and self._zk_integration.is_running() else '未启用'}")
            logger.info(f"  应用注册：{'已注册' if self._app_registrator and self._app_registrator.is_registered() else '跳过'}")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"PyLinkAgent 启动失败：{e}")
            import traceback
            traceback.print_exc()
            return False

    def _init_external_api(self) -> bool:
        """初始化 ExternalAPI"""
        from .controller import ExternalAPI

        tro_web_url = os.getenv('MANAGEMENT_URL', 'http://localhost:9999')
        app_name = os.getenv('APP_NAME', 'default-app')
        agent_id = os.getenv('AGENT_ID', f'pylinkagent-{os.getpid()}')

        # 构建请求头（从环境变量读取）
        extra_headers = {}

        # 从环境变量读取关键字段
        user_app_key = os.getenv('USER_APP_KEY', '')
        if user_app_key:
            extra_headers['userAppKey'] = user_app_key

        tenant_app_key = os.getenv('TENANT_APP_KEY', '')
        if tenant_app_key:
            extra_headers['tenantAppKey'] = tenant_app_key

        user_id = os.getenv('USER_ID', '')
        if user_id:
            extra_headers['userId'] = user_id

        env_code = os.getenv('ENV_CODE', 'test')
        if env_code:
            extra_headers['envCode'] = env_code

        logger.info(f"初始化 ExternalAPI:")
        logger.info(f"  控制台地址：{tro_web_url}")
        logger.info(f"  应用名称：{app_name}")
        logger.info(f"  Agent ID: {agent_id}")
        if extra_headers:
            logger.info(f"  请求头配置：{len(extra_headers)} 个")

        self._external_api = ExternalAPI(
            tro_web_url=tro_web_url,
            app_name=app_name,
            agent_id=agent_id,
            extra_headers=extra_headers if extra_headers else None,
        )

        return self._external_api.initialize()

    def _register_application(self) -> None:
        """注册应用 (P0 任务：应用自动注册)"""
        from .controller import ApplicationRegistrator

        # 检查是否启用应用注册
        auto_register = os.getenv('AUTO_REGISTER_APP', 'true').lower() == 'true'
        if not auto_register:
            logger.info("应用自动注册已禁用 (AUTO_REGISTER_APP=false)")
            return

        logger.info("注册应用...")

        try:
            self._app_registrator = ApplicationRegistrator(self._external_api)
            if self._app_registrator.register():
                logger.info("  应用注册成功")
            else:
                logger.warning("  应用注册失败，继续启动 (可能需要在控制台手动创建应用)")
        except Exception as e:
            logger.warning(f"  应用注册异常：{e}")

    def _init_zookeeper(self) -> None:
        """初始化 ZooKeeper 集成"""
        from .controller import initialize_zk, get_integration

        logger.info("初始化 ZooKeeper 集成...")

        if initialize_zk():
            self._zk_integration = get_integration()
            logger.info("  ZooKeeper 集成已启用")
        else:
            logger.info("  ZooKeeper 集成未启用 (降级到 HTTP-only 模式)")

    def _init_shadow_routing(self) -> None:
        """初始化影子路由 (P0 核心功能)"""
        shadow_enabled = os.getenv('SHADOW_ROUTING', 'true').lower() == 'true'
        if not shadow_enabled:
            logger.info("影子路由已禁用 (SHADOW_ROUTING=false)")
            return

        logger.info("初始化影子路由...")

        try:
            from .shadow import get_config_center, get_router
            from .shadow.mysql_interceptor import MySQLShadowInterceptor
            from .shadow.redis_interceptor import RedisShadowInterceptor
            from .shadow.es_interceptor import ESShadowInterceptor
            from .shadow.kafka_interceptor import KafkaShadowInterceptor
            from .shadow.http_interceptor import HTTPShadowInterceptor
            from .shadow.sqlalchemy_interceptor import SQLAlchemyShadowInterceptor

            # 获取配置中心和路由器
            config_center = get_config_center()
            router = get_router()

            # 注册配置变更回调 (ConfigFetcher 拉取到影子配置后自动更新)
            if self._config_fetcher:
                self._config_fetcher.on_config_change(
                    lambda key, old, new: self._on_shadow_config_change(config_center)
                )

            # 启动所有拦截器
            interceptors = [
                MySQLShadowInterceptor(router),
                RedisShadowInterceptor(router),
                ESShadowInterceptor(router),
                KafkaShadowInterceptor(router),
                HTTPShadowInterceptor(router),
                SQLAlchemyShadowInterceptor(router),
            ]

            patched_count = 0
            for interceptor in interceptors:
                if interceptor.patch():
                    patched_count += 1

            self._shadow_interceptors = interceptors
            self._on_shadow_config_change(config_center)
            self._shadow_enabled = True
            logger.info(f"  影子路由已启用 ({patched_count}/{len(interceptors)} 个拦截器)")

        except Exception as e:
            logger.warning(f"  影子路由初始化失败: {e} (降级到正常模式)")

    def _init_runtime_config(self) -> None:
        """初始化 Pradar 运行时配置"""
        try:
            from .pradar import WhitelistManager

            WhitelistManager.init()

            if self._config_fetcher:
                self._config_fetcher.on_config_change(
                    lambda key, old, new: self._apply_runtime_config()
                )
                self._apply_runtime_config()
        except Exception as e:
            logger.warning(f"Pradar 运行时配置初始化失败: {e}")

    def _on_shadow_config_change(self, config_center) -> None:
        """处理影子配置变更"""
        try:
            # 从 ConfigFetcher 获取最新配置并更新 config_center
            if self._config_fetcher:
                config = self._config_fetcher.get_config()
                config_center.load_db_configs(list(config.shadow_database_configs.values()))
                config_center.load_redis_configs(list(config.shadow_redis_configs.values()))
                config_center.load_es_configs(dict(config.shadow_es_configs))
                config_center.load_kafka_configs(list(config.shadow_kafka_configs.values()))
                logger.info(
                    "影子配置已更新: db=%s, redis=%s, es=%s, kafka=%s",
                    len(config.shadow_database_configs),
                    len(config.shadow_redis_configs),
                    len(config.shadow_es_configs),
                    len(config.shadow_kafka_configs),
                )
        except Exception as e:
            logger.warning(f"影子配置变更处理失败: {e}")

    def _apply_runtime_config(self) -> None:
        """把远程配置应用到 Pradar 运行时"""
        try:
            if not self._config_fetcher:
                return

            from .pradar import PradarSwitcher, WhitelistManager, MatchType

            config = self._config_fetcher.get_config()

            if config.cluster_test_switch is True:
                PradarSwitcher.clear_cluster_test_unable()
                PradarSwitcher.turn_cluster_test_switch_on()
            elif config.cluster_test_switch is False:
                PradarSwitcher.turn_cluster_test_switch_off()

            if config.whitelist_switch is True:
                PradarSwitcher.turn_white_list_switch_on()
                WhitelistManager.enable_whitelist()
            elif config.whitelist_switch is False:
                PradarSwitcher.turn_white_list_switch_off()
                WhitelistManager.disable_whitelist()

            WhitelistManager.init()

            match_type_map = {
                "EXACT": MatchType.EXACT,
                "PREFIX": MatchType.PREFIX,
                "REGEX": MatchType.REGEX,
                "CONTAINS": MatchType.CONTAINS,
            }

            for pattern in config.url_whitelist:
                normalized, match_name = self._normalize_whitelist_pattern(pattern)
                WhitelistManager.add_url_whitelist(normalized, match_type_map[match_name], "remote-call-config")
            for pattern in config.rpc_whitelist:
                normalized, match_name = self._normalize_whitelist_pattern(pattern)
                WhitelistManager.add_rpc_whitelist(normalized, match_type_map[match_name], "remote-call-config")
            for pattern in config.mq_whitelist:
                normalized, match_name = self._normalize_whitelist_pattern(pattern)
                WhitelistManager.add_mq_whitelist(normalized, match_type_map[match_name], "remote-call-config")
            for pattern in config.cache_key_whitelist:
                normalized, match_name = self._normalize_whitelist_pattern(pattern)
                WhitelistManager.add_cache_key_whitelist(normalized, match_type_map[match_name], "remote-call-config")

            logger.info(
                "Pradar 运行时配置已应用: clusterTest=%s, whitelistSwitch=%s, url=%s, rpc=%s, mq=%s, cache=%s",
                config.cluster_test_switch,
                config.whitelist_switch,
                len(config.url_whitelist),
                len(config.rpc_whitelist),
                len(config.mq_whitelist),
                len(config.cache_key_whitelist),
            )
        except Exception as e:
            logger.warning(f"Pradar 运行时配置应用失败: {e}")

    @staticmethod
    def _normalize_whitelist_pattern(pattern: str):
        """根据简单规则把远程配置转换为 WhitelistManager 匹配模式"""
        if pattern.startswith("*") and pattern.endswith("*") and len(pattern) > 2:
            return pattern[1:-1], "CONTAINS"
        if pattern.endswith("*") and len(pattern) > 1:
            return pattern[:-1], "PREFIX"
        if any(token in pattern for token in ["[", "]", "(", ")", "^", "$", "|"]):
            return pattern, "REGEX"
        return pattern, "EXACT"

    def _start_config_fetcher(self) -> bool:
        """启动配置拉取器"""
        from .controller import ConfigFetcher

        if not self._external_api:
            return False

        interval = int(os.getenv('CONFIG_FETCH_INTERVAL', '60'))

        logger.info(f"启动配置拉取器 (间隔：{interval}秒)")

        self._config_fetcher = ConfigFetcher(self._external_api, interval=interval)
        return self._config_fetcher.start()

    def _start_heartbeat_reporter(self) -> bool:
        """启动心跳上报器"""
        from .controller import HeartbeatReporter

        if not self._external_api:
            return False

        interval = int(os.getenv('HEARTBEAT_INTERVAL', '60'))

        logger.info(f"启动 HTTP 心跳上报 (间隔：{interval}秒)")

        self._heartbeat_reporter = HeartbeatReporter(
            self._external_api,
            interval=interval
        )
        return self._heartbeat_reporter.start()

    def _start_command_poller(self) -> bool:
        """启动命令轮询器"""
        from .controller import CommandPoller

        if not self._external_api:
            return False

        interval = int(os.getenv('COMMAND_POLL_INTERVAL', '30'))

        logger.info(f"启动命令轮询 (间隔：{interval}秒)")

        self._command_poller = CommandPoller(
            self._external_api,
            interval=interval
        )
        return self._command_poller.start()

    def _register_shutdown_hooks(self) -> None:
        """注册关闭钩子"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号：{signum}")
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        import atexit
        atexit.register(self.shutdown)

        logger.info("已注册关闭钩子")

    def shutdown(self) -> None:
        """关闭 Agent"""
        if not self._is_running and not any([
            self._heartbeat_reporter,
            self._config_fetcher,
            self._command_poller,
            self._zk_integration,
            self._external_api,
        ]):
            return

        logger.info("=" * 60)
        logger.info("PyLinkAgent 关闭中...")
        logger.info("=" * 60)

        self._is_running = False

        # 1. 停止 HTTP 心跳
        if self._heartbeat_reporter:
            self._heartbeat_reporter.stop()
            logger.info("  HTTP 心跳已停止")
            self._heartbeat_reporter = None

        # 2. 停止配置拉取
        if self._config_fetcher:
            self._config_fetcher.stop()
            logger.info("  配置拉取已停止")
            self._config_fetcher = None

        # 3. 停止命令轮询
        if self._command_poller:
            self._command_poller.stop()
            logger.info("  命令轮询已停止")
            self._command_poller = None

        # 4. 关闭 ZooKeeper (如果启用)
        if self._zk_integration:
            from .controller import shutdown_zk
            shutdown_zk()
            logger.info("  ZooKeeper 已关闭")
            self._zk_integration = None

        # 5. 关闭影子路由
        if self._shadow_enabled:
            try:
                for interceptor in self._shadow_interceptors:
                    try:
                        interceptor.unpatch()
                    except Exception:
                        pass
                self._shadow_interceptors = []
                logger.info("  影子路由已关闭")
            except Exception:
                pass
            self._shadow_enabled = False

        # 6. 关闭 ExternalAPI
        if self._external_api:
            self._external_api.shutdown()
            logger.info("  ExternalAPI 已关闭")
            self._external_api = None

        self._app_registrator = None

        logger.info("=" * 60)
        logger.info("PyLinkAgent 已关闭")
        logger.info("=" * 60)

    def wait(self) -> None:
        """等待 Agent 关闭"""
        if not self._is_running:
            return

        logger.info("Agent 运行中... (Ctrl+C 停止)")

        try:
            while self._is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到中断信号")
        finally:
            self.shutdown()


# ==================== 全局启动器 ====================

_global_bootstrapper: Optional[PyLinkAgentBootstrapper] = None


def bootstrap() -> PyLinkAgentBootstrapper:
    """
    启动 PyLinkAgent

    Returns:
        PyLinkAgentBootstrapper 实例
    """
    global _global_bootstrapper

    if _global_bootstrapper is None:
        _global_bootstrapper = PyLinkAgentBootstrapper()
        _global_bootstrapper.bootstrap()

    return _global_bootstrapper


def shutdown() -> None:
    """关闭 PyLinkAgent"""
    global _global_bootstrapper

    if _global_bootstrapper:
        _global_bootstrapper.shutdown()
        _global_bootstrapper = None


def is_running() -> bool:
    """检查 Agent 是否运行"""
    return _global_bootstrapper is not None and _global_bootstrapper._is_running


def get_bootstrapper() -> Optional[PyLinkAgentBootstrapper]:
    """获取全局启动器实例"""
    return _global_bootstrapper
