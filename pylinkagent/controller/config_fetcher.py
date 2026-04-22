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
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from .external_api import ExternalAPI
from pylinkagent.shadow.config_center import ShadowDatabaseConfig
from pylinkagent.shadow.config_center import ShadowConfigCenter


logger = logging.getLogger(__name__)


@dataclass
class ConfigData:
    """配置数据"""
    # 影子库配置 (key: datasourceName, value: ShadowDatabaseConfig)
    shadow_database_configs: Dict[str, ShadowDatabaseConfig] = field(default_factory=dict)

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

            # 1. 拉取影子库配置
            shadow_db_data = self.external_api.fetch_shadow_database_config()
            if shadow_db_data:
                for item in shadow_db_data:
                    config = ShadowDatabaseConfig.from_dict(item)
                    if config.url:
                        key = ShadowConfigCenter._normalize_url(config.url)
                        new_config.shadow_database_configs[key] = config
                        logger.debug(f"解析影子库配置: {config.url}")

            # 2. 保存原始配置
            new_config.raw_config = {
                "shadow_database_configs": shadow_db_data or [],
            }

            # 3. 检测配置变更
            self._check_config_games(new_config)

            # 4. 更新当前配置
            self._current_config = new_config

            if new_config.shadow_database_configs:
                logger.info(f"配置拉取成功：{len(new_config.shadow_database_configs)} 个影子库配置")
            else:
                logger.info("配置拉取成功：无影子库配置")
            return new_config

        except Exception as e:
            logger.error(f"拉取配置失败：{e}")
            return None

    def _check_config_games(self, new_config: ConfigData) -> None:
        """
        检测配置变更并触发回调

        Args:
            new_config: 新配置
        """
        # 检查影子库配置变更
        old_keys = set(self._current_config.shadow_database_configs.keys())
        new_keys = set(new_config.shadow_database_configs.keys())

        if old_keys != new_keys:
            self._notify_config_change(
                "shadowDatabaseConfigs",
                self._current_config.shadow_database_configs,
                new_config.shadow_database_configs
            )
            return

        # 检查具体配置内容变更
        for key in old_keys:
            old_cfg = self._current_config.shadow_database_configs[key]
            new_cfg = new_config.shadow_database_configs[key]
            if old_cfg != new_cfg:
                self._notify_config_change(
                    "shadowDatabaseConfigs",
                    self._current_config.shadow_database_configs,
                    new_config.shadow_database_configs
                )
                return

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
