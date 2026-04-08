"""
ConfigFetcher - PyLinkAgent 配置拉取

参考 Java LinkAgent 的 ConfigFetcherModule 机制，定期从控制台拉取配置。

核心功能:
- 定时配置拉取 (默认 60 秒)
- 配置变更检测
- 配置变更事件通知
- 支持影子库等配置同步
"""

import logging
import time
import threading
import json
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from .external_api import ExternalAPI


logger = logging.getLogger(__name__)


@dataclass
class ConfigData:
    """配置数据"""
    # 影子库配置
    shadow_database_configs: Dict[str, Any] = field(default_factory=dict)

    # 全局开关配置
    global_switch: Dict[str, Any] = field(default_factory=dict)

    # Redis 影子服务器配置
    redis_shadow_configs: Dict[str, Any] = field(default_factory=dict)

    # ES 影子服务器配置
    es_shadow_configs: Dict[str, Any] = field(default_factory=dict)

    # MQ 白名单配置
    mq_white_list: List[str] = field(default_factory=list)

    # RPC 白名单配置
    rpc_white_list: List[str] = field(default_factory=list)

    # URL 白名单配置
    url_white_list: List[str] = field(default_factory=list)

    # Mock 配置
    mock_configs: Dict[str, Any] = field(default_factory=dict)

    # 影子 Job 配置
    shadow_job_configs: Dict[str, Any] = field(default_factory=dict)

    # 原始配置数据
    raw_config: Dict[str, Any] = field(default_factory=dict)


class ConfigFetcher:
    """
    配置拉取器 - 定期从控制台拉取配置

    参考 Java LinkAgent 的 ConfigFetcherModule 实现
    Java 中默认 60 秒拉取一次配置
    """

    DEFAULT_INTERVAL = 60  # 默认拉取间隔 (秒)
    DEFAULT_INITIAL_DELAY = 10  # 默认初始延迟 (秒)

    # 配置项键名
    KEY_SHADOW_DATABASE = "shadowDatabaseConfigs"
    KEY_GLOBAL_SWITCH = "globalSwitch"
    KEY_REDIS_SHADOW = "redisShadowServerConfigs"
    KEY_ES_SHADOW = "esShadowServerConfigs"
    KEY_MQ_WHITE_LIST = "mqWhiteList"
    KEY_RPC_WHITE_LIST = "rpcWhiteList"
    KEY_URL_WHITE_LIST = "urlWhiteList"
    KEY_MOCK_CONFIG = "mockConfigs"
    KEY_SHADOW_JOB = "shadowJobConfigs"

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

        self._running = True
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="config-fetcher"
        )
        self._thread = self._executor.submit(self._fetch_loop).result()

        logger.info(f"配置拉取已启动：interval={self.interval}s, initial_delay={self.initial_delay}s")
        return True

    def stop(self) -> None:
        """停止配置拉取"""
        self._running = False

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

    def get_shadow_database_config(self, datasource_name: str) -> Optional[Dict[str, Any]]:
        """
        获取影子库配置

        Args:
            datasource_name: 数据源名称

        Returns:
            影子库配置，不存在返回 None
        """
        return self._current_config.shadow_database_configs.get(datasource_name)

    def get_all_shadow_database_configs(self) -> Dict[str, Any]:
        """
        获取所有影子库配置

        Returns:
            影子库配置字典
        """
        return self._current_config.shadow_database_configs

    def is_global_switch_enabled(self, switch_name: str) -> bool:
        """
        检查全局开关是否启用

        Args:
            switch_name: 开关名称

        Returns:
            bool: 是否启用
        """
        return self._current_config.global_switch.get(switch_name, False)

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
            # 构建配置拉取 URL
            config_url = "/api/agent/config/fetch"

            params = {
                "appName": self.external_api.app_name,
                "agentId": self.external_api.agent_id,
            }

            url = f"{config_url}?appName={params['appName']}&agentId={params['agentId']}"

            # 发送请求
            response = self.external_api._request("GET", url)

            if not response or not response.get("success", False):
                logger.debug("配置拉取返回空或失败")
                return None

            # 解析配置数据
            config_data = response.get("data", {})
            new_config = self._parse_config(config_data)

            # 检测配置变更
            self._check_config_changes(new_config)

            # 更新当前配置
            self._current_config = new_config

            logger.info(f"配置拉取成功")
            return new_config

        except Exception as e:
            logger.error(f"拉取配置失败：{e}")
            return None

    def _parse_config(self, config_data: Dict[str, Any]) -> ConfigData:
        """
        解析配置数据

        Args:
            config_data: 原始配置数据

        Returns:
            ConfigData: 解析后的配置
        """
        config = ConfigData()
        config.raw_config = config_data

        # 解析影子库配置
        if self.KEY_SHADOW_DATABASE in config_data:
            config.shadow_database_configs = config_data[self.KEY_SHADOW_DATABASE]
            logger.debug(f"解析影子库配置：{len(config.shadow_database_configs)} 个数据源")

        # 解析全局开关
        if self.KEY_GLOBAL_SWITCH in config_data:
            config.global_switch = config_data[self.KEY_GLOBAL_SWITCH]
            logger.debug(f"解析全局开关：{len(config.global_switch)} 个开关")

        # 解析 Redis 影子配置
        if self.KEY_REDIS_SHADOW in config_data:
            config.redis_shadow_configs = config_data[self.KEY_REDIS_SHADOW]
            logger.debug(f"解析 Redis 影子配置：{len(config.redis_shadow_configs)} 个配置")

        # 解析 ES 影子配置
        if self.KEY_ES_SHADOW in config_data:
            config.es_shadow_configs = config_data[self.KEY_ES_SHADOW]
            logger.debug(f"解析 ES 影子配置：{len(config.es_shadow_configs)} 个配置")

        # 解析 MQ 白名单
        if self.KEY_MQ_WHITE_LIST in config_data:
            config.mq_white_list = config_data[self.KEY_MQ_WHITE_LIST]
            logger.debug(f"解析 MQ 白名单：{len(config.mq_white_list)} 条")

        # 解析 RPC 白名单
        if self.KEY_RPC_WHITE_LIST in config_data:
            config.rpc_white_list = config_data[self.KEY_RPC_WHITE_LIST]
            logger.debug(f"解析 RPC 白名单：{len(config.rpc_white_list)} 条")

        # 解析 URL 白名单
        if self.KEY_URL_WHITE_LIST in config_data:
            config.url_white_list = config_data[self.KEY_URL_WHITE_LIST]
            logger.debug(f"解析 URL 白名单：{len(config.url_white_list)} 条")

        # 解析 Mock 配置
        if self.KEY_MOCK_CONFIG in config_data:
            config.mock_configs = config_data[self.KEY_MOCK_CONFIG]
            logger.debug(f"解析 Mock 配置：{len(config.mock_configs)} 个配置")

        # 解析影子 Job 配置
        if self.KEY_SHADOW_JOB in config_data:
            config.shadow_job_configs = config_data[self.KEY_SHADOW_JOB]
            logger.debug(f"解析影子 Job 配置：{len(config.shadow_job_configs)} 个配置")

        return config

    def _check_config_changes(self, new_config: ConfigData) -> None:
        """
        检测配置变更并触发回调

        Args:
            new_config: 新配置
        """
        # 检查影子库配置变更
        if new_config.shadow_database_configs != self._current_config.shadow_database_configs:
            self._notify_config_change(
                self.KEY_SHADOW_DATABASE,
                self._current_config.shadow_database_configs,
                new_config.shadow_database_configs
            )

        # 检查全局开关变更
        if new_config.global_switch != self._current_config.global_switch:
            self._notify_config_change(
                self.KEY_GLOBAL_SWITCH,
                self._current_config.global_switch,
                new_config.global_switch
            )

        # 检查 Redis 影子配置变更
        if new_config.redis_shadow_configs != self._current_config.redis_shadow_configs:
            self._notify_config_change(
                self.KEY_REDIS_SHADOW,
                self._current_config.redis_shadow_configs,
                new_config.redis_shadow_configs
            )

        # 检查 ES 影子配置变更
        if new_config.es_shadow_configs != self._current_config.es_shadow_configs:
            self._notify_config_change(
                self.KEY_ES_SHADOW,
                self._current_config.es_shadow_configs,
                new_config.es_shadow_configs
            )

        # 检查 MQ 白名单变更
        if new_config.mq_white_list != self._current_config.mq_white_list:
            self._notify_config_change(
                self.KEY_MQ_WHITE_LIST,
                self._current_config.mq_white_list,
                new_config.mq_white_list
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
        time.sleep(self.initial_delay)

        while self._running:
            try:
                self.fetch_now()
            except Exception as e:
                logger.error(f"配置拉取循环异常：{e}")

            # 等待下一次拉取
            for _ in range(self.interval * 10):
                if not self._running:
                    break
                time.sleep(0.1)

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
