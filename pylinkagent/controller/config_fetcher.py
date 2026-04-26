"""
ConfigFetcher - PyLinkAgent 配置拉取

参考 Java LinkAgent 的 ApplicationConfigHttpResolver 机制，从 Takin-web 拉取配置。

核心功能:
- 影子库配置拉取 (/api/link/ds/configs/pull)
- 远程调用配置拉取 (/api/remote/call/configs/pull)
- 定时配置拉取 (默认 60 秒)
- 配置变更检测
- 配置变更事件通知
"""

import logging
import time
import threading
from typing import Optional, Dict, Any, List, Callable, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from .external_api import ExternalAPI
from pylinkagent.shadow.config_center import (
    ShadowDatabaseConfig,
    ShadowRedisConfig,
    ShadowEsConfig,
    ShadowKafkaConfig,
)
from pylinkagent.shadow.config_center import ShadowConfigCenter


logger = logging.getLogger(__name__)


@dataclass
class ConfigData:
    """配置数据"""
    # 影子库配置 (key: datasourceName, value: ShadowDatabaseConfig)
    shadow_database_configs: Dict[str, ShadowDatabaseConfig] = field(default_factory=dict)
    shadow_redis_configs: Dict[str, ShadowRedisConfig] = field(default_factory=dict)
    shadow_es_configs: Dict[str, ShadowEsConfig] = field(default_factory=dict)
    shadow_kafka_configs: Dict[str, ShadowKafkaConfig] = field(default_factory=dict)
    shadow_job_configs: List[Dict[str, Any]] = field(default_factory=list)
    remote_call_config: Dict[str, Any] = field(default_factory=dict)
    url_whitelist: List[str] = field(default_factory=list)
    rpc_whitelist: List[str] = field(default_factory=list)
    mq_whitelist: List[str] = field(default_factory=list)
    cache_key_whitelist: List[str] = field(default_factory=list)
    block_list: List[str] = field(default_factory=list)
    search_whitelist: List[str] = field(default_factory=list)
    cluster_test_switch: Optional[bool] = None
    whitelist_switch: Optional[bool] = None

    # 原始配置数据
    raw_config: Dict[str, Any] = field(default_factory=dict)


class ConfigFetcher:
    """
    配置拉取器 - 定期从 Takin-web 拉取配置

    参考 Java LinkAgent 的 ApplicationConfigHttpResolver 实现
    """

    DEFAULT_INTERVAL = 60  # 默认拉取间隔 (秒)
    DEFAULT_INITIAL_DELAY = 5  # 默认初始延迟 (秒)

    def __init__(
        self,
        external_api: ExternalAPI,
        interval: int = DEFAULT_INTERVAL,
        initial_delay: int = DEFAULT_INITIAL_DELAY,
    ):
        """
        初始化配置拉取器

        Args:
            external_api: ExternalAPI 实例
            interval: 拉取间隔 (秒)，默认 60 秒
            initial_delay: 初始延迟 (秒)
        """
        self.external_api = external_api
        self.interval = interval
        self.initial_delay = initial_delay

        self._current_config = ConfigData()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self._stop_event = threading.Event()

        # 配置变更回调
        self._config_change_callbacks: List[Callable[[str, Any, Any], None]] = []

    def start(self) -> bool:
        """
        启动配置拉取

        Returns:
            bool: 启动成功返回 True
        """
        if self._running:
            logger.warning("配置拉取已在运行")
            return True

        if not self.external_api.is_initialized():
            logger.warning("ExternalAPI 未初始化，无法启动配置拉取")
            return False

        self._stop_event.clear()
        self._running = True
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="config-fetcher"
        )
        self._thread = self._executor.submit(self._fetch_loop)

        logger.info(f"配置拉取已启动：interval={self.interval}s, initial_delay={self.initial_delay}s")
        return True

    def stop(self) -> None:
        """停止配置拉取"""
        self._running = False
        self._stop_event.set()

        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

        logger.info("配置拉取已停止")

    def is_running(self) -> bool:
        """检查配置拉取是否运行中"""
        return self._running

    def get_config(self) -> ConfigData:
        """
        获取当前配置

        Returns:
            ConfigData: 当前配置数据
        """
        return self._current_config

    def get_shadow_database_config(self, datasource_name: str) -> Optional[ShadowDatabaseConfig]:
        """
        获取影子库配置

        Args:
            datasource_name: 数据源名称

        Returns:
            影子库配置，不存在返回 None
        """
        return self._current_config.shadow_database_configs.get(datasource_name)

    def get_all_shadow_database_configs(self) -> Dict[str, ShadowDatabaseConfig]:
        """
        获取所有影子库配置

        Returns:
            影子库配置字典
        """
        return self._current_config.shadow_database_configs

    def on_config_change(self, callback: Callable[[str, Any, Any], None]) -> None:
        """
        注册配置变更回调

        Args:
            callback: 回调函数 (config_key, old_value, new_value)
        """
        self._config_change_callbacks.append(callback)
        logger.debug(f"注册配置变更回调")

    def fetch_now(self) -> Optional[ConfigData]:
        """
        立即拉取一次配置

        Returns:
            ConfigData: 拉取到的配置，失败返回 None
        """
        if not self.external_api.is_initialized():
            logger.warning("ExternalAPI 未初始化")
            return None

        try:
            new_config = ConfigData()

            # 1. 拉取开关配置
            new_config.cluster_test_switch = self.external_api.fetch_cluster_test_switch()
            new_config.whitelist_switch = self.external_api.fetch_whitelist_switch()

            # 2. 拉取影子库配置
            shadow_db_data = self.external_api.fetch_shadow_database_config()
            if shadow_db_data:
                for item in shadow_db_data:
                    config = ShadowDatabaseConfig.from_dict(item)
                    if config.url:
                        key = ShadowConfigCenter._normalize_url(config.url)
                        new_config.shadow_database_configs[key] = config
                        logger.debug(f"解析影子库配置: {config.url}")

            # 3. 拉取远程调用配置
            remote_call_data = self.external_api.fetch_remote_call_config() or {}
            new_config.remote_call_config = remote_call_data
            (
                new_config.url_whitelist,
                new_config.rpc_whitelist,
                new_config.mq_whitelist,
                new_config.cache_key_whitelist,
                new_config.block_list,
                new_config.search_whitelist,
            ) = self._parse_remote_call_config(remote_call_data)

            # 4. 拉取 Redis/ES/Kafka/Job 影子配置
            shadow_redis_data = self.external_api.fetch_shadow_redis_config() or []
            for item in shadow_redis_data:
                config = ShadowRedisConfig.from_dict(item)
                if config.original_host:
                    key = f"{config.original_host}:{config.original_port}"
                    new_config.shadow_redis_configs[key] = config

            shadow_es_data = self.external_api.fetch_shadow_es_config() or []
            for index, item in enumerate(shadow_es_data):
                config = ShadowEsConfig.from_dict(item)
                if config.original_hosts:
                    key = ",".join(sorted(config.original_hosts))
                    new_config.shadow_es_configs[key or str(index)] = config

            shadow_kafka_data = self.external_api.fetch_shadow_kafka_config() or []
            for item in shadow_kafka_data:
                config = ShadowKafkaConfig.from_dict(item)
                if config.original_bootstrap_servers:
                    new_config.shadow_kafka_configs[config.original_bootstrap_servers] = config

            new_config.shadow_job_configs = self.external_api.fetch_shadow_job_config() or []

            # 5. 保存原始配置
            new_config.raw_config = {
                "cluster_test_switch": new_config.cluster_test_switch,
                "whitelist_switch": new_config.whitelist_switch,
                "shadow_database_configs": shadow_db_data or [],
                "remote_call_config": remote_call_data,
                "shadow_redis_configs": shadow_redis_data,
                "shadow_es_configs": shadow_es_data,
                "shadow_kafka_configs": shadow_kafka_data,
                "shadow_job_configs": new_config.shadow_job_configs,
            }

            # 6. 检测配置变更
            self._check_config_changes(new_config)

            # 7. 更新当前配置
            self._current_config = new_config

            logger.info(
                "配置拉取成功：db=%s, redis=%s, es=%s, kafka=%s, urlWhitelist=%s, clusterTestSwitch=%s",
                len(new_config.shadow_database_configs),
                len(new_config.shadow_redis_configs),
                len(new_config.shadow_es_configs),
                len(new_config.shadow_kafka_configs),
                len(new_config.url_whitelist),
                new_config.cluster_test_switch,
            )
            return new_config

        except Exception as e:
            logger.error(f"拉取配置失败：{e}")
            return None

    def _check_config_changes(self, new_config: ConfigData) -> None:
        """
        检测配置变更并触发回调

        Args:
            new_config: 新配置
        """
        tracked_fields = [
            ("clusterTestSwitch", self._current_config.cluster_test_switch, new_config.cluster_test_switch),
            ("whitelistSwitch", self._current_config.whitelist_switch, new_config.whitelist_switch),
            ("shadowDatabaseConfigs", self._current_config.shadow_database_configs, new_config.shadow_database_configs),
            ("shadowRedisConfigs", self._current_config.shadow_redis_configs, new_config.shadow_redis_configs),
            ("shadowEsConfigs", self._current_config.shadow_es_configs, new_config.shadow_es_configs),
            ("shadowKafkaConfigs", self._current_config.shadow_kafka_configs, new_config.shadow_kafka_configs),
            ("shadowJobConfigs", self._current_config.shadow_job_configs, new_config.shadow_job_configs),
            ("remoteCallConfig", self._current_config.remote_call_config, new_config.remote_call_config),
            ("urlWhitelist", self._current_config.url_whitelist, new_config.url_whitelist),
            ("rpcWhitelist", self._current_config.rpc_whitelist, new_config.rpc_whitelist),
            ("mqWhitelist", self._current_config.mq_whitelist, new_config.mq_whitelist),
            ("cacheKeyWhitelist", self._current_config.cache_key_whitelist, new_config.cache_key_whitelist),
            ("blockList", self._current_config.block_list, new_config.block_list),
            ("searchWhitelist", self._current_config.search_whitelist, new_config.search_whitelist),
        ]

        for key, old_value, new_value in tracked_fields:
            if old_value != new_value:
                self._notify_config_change(key, old_value, new_value)

    @staticmethod
    def _parse_remote_call_config(remote_call_data: Dict[str, Any]) -> Tuple[
        List[str],
        List[str],
        List[str],
        List[str],
        List[str],
        List[str],
    ]:
        """解析 Takin-web 远程调用配置"""
        url_whitelist: List[str] = []
        rpc_whitelist: List[str] = []
        mq_whitelist: List[str] = []
        cache_key_whitelist: List[str] = []
        block_list: List[str] = []
        search_whitelist: List[str] = []

        if not remote_call_data:
            return (
                url_whitelist,
                rpc_whitelist,
                mq_whitelist,
                cache_key_whitelist,
                block_list,
                search_whitelist,
            )

        for blacklist in remote_call_data.get("newBlists", []) or []:
            if isinstance(blacklist, dict):
                for key in blacklist.get("blacklists", []) or []:
                    if key:
                        cache_key_whitelist.append(str(key))

        for whitelist in remote_call_data.get("wLists", []) or []:
            if not isinstance(whitelist, dict):
                continue

            name = str(whitelist.get("INTERFACE_NAME", "")).strip()
            config_type = str(whitelist.get("TYPE", "")).strip().lower()
            if not name:
                continue

            if config_type == "http":
                if name.startswith("mq:"):
                    mq_whitelist.append(name[3:])
                elif name.startswith("rabbitmq:"):
                    mq_whitelist.append(name[9:])
                elif name.startswith("search:"):
                    search_whitelist.append(name[7:])
                else:
                    url_whitelist.append(name)
            elif config_type in {"dubbo", "feign", "rpc", "grpc"}:
                rpc_whitelist.append(name)
            elif config_type == "mq":
                mq_whitelist.append(name)
            elif config_type == "search":
                search_whitelist.append(name)
            elif config_type == "block":
                block_list.append(name)

        return (
            sorted(set(url_whitelist)),
            sorted(set(rpc_whitelist)),
            sorted(set(mq_whitelist)),
            sorted(set(cache_key_whitelist)),
            sorted(set(block_list)),
            sorted(set(search_whitelist)),
        )

    def _notify_config_change(
        self,
        key: str,
        old_value: Any,
        new_value: Any
    ) -> None:
        """
        通知配置变更

        Args:
            key: 配置键
            old_value: 旧值
            new_value: 新值
        """
        logger.info(f"配置变更：{key}")

        for callback in self._config_change_callbacks:
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                logger.error(f"配置变更回调异常：{key}, error={e}")

    def _fetch_loop(self) -> None:
        """配置拉取循环"""
        logger.info("配置拉取线程启动")

        # 初始延迟
        if self._stop_event.wait(self.initial_delay):
            logger.info("配置拉取线程退出")
            return

        while self._running:
            try:
                self.fetch_now()
            except Exception as e:
                logger.error(f"配置拉取循环异常：{e}")

            if self._stop_event.wait(self.interval):
                break

        logger.info("配置拉取线程退出")


class ConfigFetcherBuilder:
    """
    配置拉取器构建器

    链式调用构建 ConfigFetcher
    """

    def __init__(self, external_api: ExternalAPI):
        """
        初始化构建器

        Args:
            external_api: ExternalAPI 实例
        """
        self.external_api = external_api
        self.interval = ConfigFetcher.DEFAULT_INTERVAL
        self.initial_delay = ConfigFetcher.DEFAULT_INITIAL_DELAY

    def interval(self, interval: int) -> "ConfigFetcherBuilder":
        """设置拉取间隔"""
        self.interval = interval
        return self

    def initial_delay(self, initial_delay: int) -> "ConfigFetcherBuilder":
        """设置初始延迟"""
        self.initial_delay = initial_delay
        return self

    def build(self) -> ConfigFetcher:
        """构建配置拉取器"""
        return ConfigFetcher(
            external_api=self.external_api,
            interval=self.interval,
            initial_delay=self.initial_delay,
        )
