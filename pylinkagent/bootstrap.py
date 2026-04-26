"""
PyLinkAgent bootstrapper.
"""

import atexit
import logging
import os
import signal
import time
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PyLinkAgentBootstrapper:
    """Initialize and manage the PyLinkAgent runtime."""

    def __init__(self):
        self._external_api = None
        self._config_fetcher = None
        self._heartbeat_reporter = None
        self._command_poller = None
        self._zk_integration = None
        self._app_registrator = None
        self._http_server_interceptor = None
        self._shadow_enabled = False
        self._shadow_interceptors = []
        self._is_running = False

    def bootstrap(self) -> bool:
        logger.info("=" * 60)
        logger.info("PyLinkAgent 启动中...")
        logger.info("=" * 60)

        try:
            if not self._init_external_api():
                logger.error("HTTP ExternalAPI 初始化失败")
                return False

            self._register_application()
            self._init_zookeeper()

            if not self._start_config_fetcher():
                logger.warning("配置拉取器启动失败，继续启动")

            self._init_runtime_config()
            self._init_http_server_tracing()
            self._init_shadow_routing()

            if not self._start_heartbeat_reporter():
                logger.error("心跳上报启动失败")
                return False

            if not self._start_command_poller():
                logger.warning("命令轮询器启动失败，继续启动")

            self._register_shutdown_hooks()
            self._is_running = True

            logger.info("=" * 60)
            logger.info("PyLinkAgent 启动完成")
            logger.info("  HTTP 心跳：启用")
            logger.info(
                "  入口染色：%s",
                "已启用" if self._http_server_interceptor else "未启用",
            )
            logger.info(
                "  影子路由：%s",
                "已启用" if self._shadow_enabled else "未启用",
            )
            logger.info(
                "  ZK 心跳：%s",
                "启用" if self._zk_integration and self._zk_integration.is_running() else "未启用",
            )
            logger.info(
                "  应用注册：%s",
                "已注册"
                if self._app_registrator and self._app_registrator.is_registered()
                else "跳过",
            )
            logger.info("=" * 60)
            return True
        except Exception as exc:
            logger.exception("PyLinkAgent 启动失败: %s", exc)
            return False

    def _init_external_api(self) -> bool:
        from .controller import ExternalAPI

        tro_web_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
        app_name = os.getenv("APP_NAME", "default-app")
        agent_id = os.getenv("AGENT_ID", f"pylinkagent-{os.getpid()}")

        extra_headers = {}
        user_app_key = os.getenv("USER_APP_KEY", "")
        if user_app_key:
            extra_headers["userAppKey"] = user_app_key

        tenant_app_key = os.getenv("TENANT_APP_KEY", "")
        if tenant_app_key:
            extra_headers["tenantAppKey"] = tenant_app_key

        user_id = os.getenv("USER_ID", "")
        if user_id:
            extra_headers["userId"] = user_id

        env_code = os.getenv("ENV_CODE", "test")
        if env_code:
            extra_headers["envCode"] = env_code

        logger.info("初始化 ExternalAPI:")
        logger.info("  控制台地址：%s", tro_web_url)
        logger.info("  应用名称：%s", app_name)
        logger.info("  Agent ID: %s", agent_id)
        if extra_headers:
            logger.info("  请求头配置：%s 个", len(extra_headers))

        self._external_api = ExternalAPI(
            tro_web_url=tro_web_url,
            app_name=app_name,
            agent_id=agent_id,
            extra_headers=extra_headers if extra_headers else None,
        )
        return self._external_api.initialize()

    def _register_application(self) -> None:
        from .controller import ApplicationRegistrator

        if os.getenv("AUTO_REGISTER_APP", "true").lower() != "true":
            logger.info("应用自动注册已禁用 (AUTO_REGISTER_APP=false)")
            return

        logger.info("注册应用...")
        try:
            self._app_registrator = ApplicationRegistrator(self._external_api)
            if self._app_registrator.register():
                logger.info("  应用注册成功")
            else:
                logger.warning("  应用注册失败，继续启动")
        except Exception as exc:
            logger.warning("  应用注册异常: %s", exc)

    def _init_zookeeper(self) -> None:
        from .controller import get_integration, initialize_zk

        logger.info("初始化 ZooKeeper 集成...")
        if initialize_zk():
            self._zk_integration = get_integration()
            logger.info("  ZooKeeper 集成已启用")
        else:
            logger.info("  ZooKeeper 集成未启用 (降级到 HTTP-only 模式)")

    def _init_http_server_tracing(self) -> None:
        if os.getenv("HTTP_SERVER_TRACING", "true").lower() != "true":
            logger.info("HTTP 入口染色已禁用 (HTTP_SERVER_TRACING=false)")
            return

        try:
            from .http_server_interceptor import HTTPServerTracingInterceptor

            interceptor = HTTPServerTracingInterceptor(
                app_name=os.getenv("APP_NAME", "default-app")
            )
            interceptor.start()
            self._http_server_interceptor = interceptor
            logger.info("HTTP 入口染色已启用")
        except Exception as exc:
            logger.warning("HTTP 入口染色初始化失败: %s", exc)

    def _init_shadow_routing(self) -> None:
        if os.getenv("SHADOW_ROUTING", "true").lower() != "true":
            logger.info("影子路由已禁用 (SHADOW_ROUTING=false)")
            return

        logger.info("初始化影子路由...")
        try:
            from .shadow import get_config_center, get_router
            from .shadow.es_interceptor import ESShadowInterceptor
            from .shadow.http_interceptor import HTTPShadowInterceptor
            from .shadow.kafka_interceptor import KafkaShadowInterceptor
            from .shadow.mysql_interceptor import MySQLShadowInterceptor
            from .shadow.redis_interceptor import RedisShadowInterceptor
            from .shadow.sqlalchemy_interceptor import SQLAlchemyShadowInterceptor

            config_center = get_config_center()
            router = get_router()

            if self._config_fetcher:
                self._config_fetcher.on_config_change(
                    lambda key, old, new: self._on_shadow_config_change(config_center)
                )

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
            logger.info(
                "  影子路由已启用 (%s/%s 个拦截器)",
                patched_count,
                len(interceptors),
            )
        except Exception as exc:
            logger.warning("  影子路由初始化失败: %s", exc)

    def _init_runtime_config(self) -> None:
        try:
            from .pradar import WhitelistManager

            WhitelistManager.init()
            if self._config_fetcher:
                self._config_fetcher.on_config_change(
                    lambda key, old, new: self._apply_runtime_config()
                )
                self._apply_runtime_config()
        except Exception as exc:
            logger.warning("Pradar 运行时配置初始化失败: %s", exc)

    def _on_shadow_config_change(self, config_center) -> None:
        try:
            if not self._config_fetcher:
                return
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
        except Exception as exc:
            logger.warning("影子配置变更处理失败: %s", exc)

    def _apply_runtime_config(self) -> None:
        try:
            if not self._config_fetcher:
                return

            from .pradar import MatchType, PradarSwitcher, WhitelistManager

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
                WhitelistManager.add_url_whitelist(
                    normalized, match_type_map[match_name], "remote-call-config"
                )
            for pattern in config.rpc_whitelist:
                normalized, match_name = self._normalize_whitelist_pattern(pattern)
                WhitelistManager.add_rpc_whitelist(
                    normalized, match_type_map[match_name], "remote-call-config"
                )
            for pattern in config.mq_whitelist:
                normalized, match_name = self._normalize_whitelist_pattern(pattern)
                WhitelistManager.add_mq_whitelist(
                    normalized, match_type_map[match_name], "remote-call-config"
                )
            for pattern in config.cache_key_whitelist:
                normalized, match_name = self._normalize_whitelist_pattern(pattern)
                WhitelistManager.add_cache_key_whitelist(
                    normalized, match_type_map[match_name], "remote-call-config"
                )

            logger.info(
                "Pradar 运行时配置已应用: clusterTest=%s, whitelistSwitch=%s, url=%s, rpc=%s, mq=%s, cache=%s",
                config.cluster_test_switch,
                config.whitelist_switch,
                len(config.url_whitelist),
                len(config.rpc_whitelist),
                len(config.mq_whitelist),
                len(config.cache_key_whitelist),
            )
        except Exception as exc:
            logger.warning("Pradar 运行时配置应用失败: %s", exc)

    @staticmethod
    def _normalize_whitelist_pattern(pattern: str):
        if pattern.startswith("*") and pattern.endswith("*") and len(pattern) > 2:
            return pattern[1:-1], "CONTAINS"
        if pattern.endswith("*") and len(pattern) > 1:
            return pattern[:-1], "PREFIX"
        if any(token in pattern for token in ["[", "]", "(", ")", "^", "$", "|"]):
            return pattern, "REGEX"
        return pattern, "EXACT"

    def _start_config_fetcher(self) -> bool:
        from .controller import ConfigFetcher

        if not self._external_api:
            return False
        interval = int(os.getenv("CONFIG_FETCH_INTERVAL", "60"))
        logger.info("启动配置拉取器 (间隔：%s秒)", interval)
        self._config_fetcher = ConfigFetcher(self._external_api, interval=interval)
        return self._config_fetcher.start()

    def _start_heartbeat_reporter(self) -> bool:
        from .controller import HeartbeatReporter

        if not self._external_api:
            return False
        interval = int(os.getenv("HEARTBEAT_INTERVAL", "60"))
        logger.info("启动 HTTP 心跳上报 (间隔：%s秒)", interval)
        self._heartbeat_reporter = HeartbeatReporter(self._external_api, interval=interval)
        return self._heartbeat_reporter.start()

    def _start_command_poller(self) -> bool:
        from .controller import CommandPoller

        if not self._external_api:
            return False
        interval = int(os.getenv("COMMAND_POLL_INTERVAL", "30"))
        logger.info("启动命令轮询 (间隔：%s秒)", interval)
        self._command_poller = CommandPoller(self._external_api, interval=interval)
        return self._command_poller.start()

    def _register_shutdown_hooks(self) -> None:
        def signal_handler(signum, frame):
            logger.info("收到信号：%s", signum)
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        atexit.register(self.shutdown)
        logger.info("已注册关闭钩子")

    def shutdown(self) -> None:
        if not self._is_running and not any(
            [
                self._heartbeat_reporter,
                self._config_fetcher,
                self._command_poller,
                self._zk_integration,
                self._http_server_interceptor,
                self._external_api,
            ]
        ):
            return

        logger.info("=" * 60)
        logger.info("PyLinkAgent 关闭中...")
        logger.info("=" * 60)

        self._is_running = False

        if self._heartbeat_reporter:
            self._heartbeat_reporter.stop()
            logger.info("  HTTP 心跳已停止")
            self._heartbeat_reporter = None

        if self._config_fetcher:
            self._config_fetcher.stop()
            logger.info("  配置拉取已停止")
            self._config_fetcher = None

        if self._command_poller:
            self._command_poller.stop()
            logger.info("  命令轮询已停止")
            self._command_poller = None

        if self._http_server_interceptor:
            try:
                self._http_server_interceptor.stop()
                logger.info("  HTTP 入口染色已关闭")
            except Exception:
                pass
            self._http_server_interceptor = None

        if self._zk_integration:
            from .controller import shutdown_zk

            shutdown_zk()
            logger.info("  ZooKeeper 已关闭")
            self._zk_integration = None

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

        if self._external_api:
            self._external_api.shutdown()
            logger.info("  ExternalAPI 已关闭")
            self._external_api = None

        self._app_registrator = None

        logger.info("=" * 60)
        logger.info("PyLinkAgent 已关闭")
        logger.info("=" * 60)

    def wait(self) -> None:
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


_global_bootstrapper: Optional[PyLinkAgentBootstrapper] = None


def bootstrap() -> PyLinkAgentBootstrapper:
    global _global_bootstrapper

    if _global_bootstrapper is None:
        _global_bootstrapper = PyLinkAgentBootstrapper()
        _global_bootstrapper.bootstrap()
    return _global_bootstrapper


def shutdown() -> None:
    global _global_bootstrapper

    if _global_bootstrapper:
        _global_bootstrapper.shutdown()
        _global_bootstrapper = None


def is_running() -> bool:
    return _global_bootstrapper is not None and _global_bootstrapper._is_running


def get_bootstrapper() -> Optional[PyLinkAgentBootstrapper]:
    return _global_bootstrapper
