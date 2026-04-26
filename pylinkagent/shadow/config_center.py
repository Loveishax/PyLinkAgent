"""
影子配置中心 - 管理所有影子库/服务器配置

支持 ds_type:
  0 = 独立影子库 (shadow_url/shadow_username/shadow_password)
  1 = 同库影子表 (business_shadow_tables 映射)
  2 = 影子库 + 影子表 (两者都有)
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class ShadowDatabaseConfig:
    """影子数据库配置"""
    datasource_name: str = ""
    url: str = ""  # jdbc:mysql://host:port/db
    username: str = ""
    password: str = ""
    shadow_url: str = ""
    shadow_username: str = ""
    shadow_password: str = ""
    shadow_account_prefix: str = "PT_"
    shadow_account_suffix: str = ""
    business_shadow_tables: Dict[str, str] = field(default_factory=dict)
    ds_type: int = 0  # 0=分离库, 1=同库表, 2=库+表
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShadowDatabaseConfig":
        """
        从 API 返回的字典创建配置

        对应 Java ShadowDatabaseConfigParser.parse()
        真实 API 响应格式:
        {
          "dsType": 0,
          "url": "jdbc:mysql://host:port/db",
          "shadowTableConfig": "users,orders",  # dsType=1 时
          "shadowDbConfig": {
            "datasourceMediator": {
              "dataSourceBusiness": "dataSourceBusiness",
              "dataSourcePerformanceTest": "dataSourcePerformanceTest"
            },
            "dataSources": [
              { "id": "dataSourceBusiness",
                "url": "jdbc:mysql://...", "username": "...", "password": "..." },
              { "id": "dataSourcePerformanceTest",
                "url": "jdbc:mysql://...", "username": "...", "password": "..." }
            ]
          }
        }
        """
        ds_type = int(data.get("dsType", 0))
        url = data.get("url", "")
        config = cls(ds_type=ds_type, url=url, enabled=True)

        # dsType=1: 影子表模式 — 解析 shadowTableConfig
        if ds_type == 1:
            table_config = data.get("shadowTableConfig", "")
            if table_config:
                prefix = config.shadow_account_prefix
                for table_name in table_config.split(","):
                    table_name = table_name.strip()
                    if table_name:
                        config.business_shadow_tables[table_name] = f"{prefix}{table_name}"
            return config

        # dsType=0/2: 影子库模式 — 解析 shadowDbConfig
        shadow_db_config = data.get("shadowDbConfig")
        if not shadow_db_config:
            logger.debug(f"影子库配置缺少 shadowDbConfig: url={url}")
            return config

        # 获取 dataSource ID 引用
        mediator = shadow_db_config.get("datasourceMediator", {})
        business_id = mediator.get("dataSourceBusiness", "dataSourceBusiness")
        shadow_id = mediator.get("dataSourcePerformanceTest", "dataSourcePerformanceTest")

        # 从 dataSources 数组中按 ID 匹配
        data_sources = shadow_db_config.get("dataSources", [])
        business_ds: Dict[str, Any] = {}
        shadow_ds: Dict[str, Any] = {}
        for ds in data_sources:
            ds_id = ds.get("id", "")
            if ds_id == business_id:
                business_ds = ds
            elif ds_id == shadow_id:
                shadow_ds = ds

        # 业务库信息
        if business_ds:
            config.url = business_ds.get("url", url)
            config.username = business_ds.get("username", "")
            config.password = cls._resolve_spi_password(business_ds.get("password"))

        # 影子库信息
        if shadow_ds:
            config.shadow_url = shadow_ds.get("url", "")
            config.shadow_username = shadow_ds.get("username", "")
            config.shadow_password = cls._resolve_spi_password(shadow_ds.get("password"))

            # 影子表映射 (dsType=2 时 shadowTableConfig 可能也有值)
            if ds_type == 2:
                table_config = data.get("shadowTableConfig", "")
                if table_config:
                    prefix = config.shadow_account_prefix
                    for table_name in table_config.split(","):
                        table_name = table_name.strip()
                        if table_name:
                            config.business_shadow_tables[table_name] = f"{prefix}{table_name}"

        return config

    @staticmethod
    def _resolve_spi_password(password: Optional[str]) -> Optional[str]:
        """
        解析密码，处理 $<provider##secret> SPI 格式

        对应 Java ShadowDataSourceSPIManager.extractConfigValue()
        当前暂不解密，原样返回
        """
        if not password:
            return password
        # SPI 格式: $<vault##my-secret-key>
        if password.startswith("$<") and password.endswith(">"):
            logger.debug(f"检测到 SPI 密码格式，当前不解密: {password[:8]}...")
        return password

    @staticmethod
    def jdbc_to_pymysql(jdbc_url: str) -> str:
        """jdbc:mysql://host:port/db -> mysql+pymysql://host:port/db"""
        if jdbc_url.startswith("jdbc:mysql://"):
            return "mysql+pymysql://" + jdbc_url[len("jdbc:mysql://"):]
        if jdbc_url.startswith("jdbc:postgresql://"):
            return "postgresql+psycopg2://" + jdbc_url[len("jdbc:postgresql://"):]
        return jdbc_url

    def pymysql_url(self) -> str:
        """返回 pymysql 格式的 URL"""
        return self.jdbc_to_pymysql(self.url)

    def shadow_pymysql_url(self) -> str:
        """返回影子库 pymysql 格式的 URL"""
        return self.jdbc_to_pymysql(self.shadow_url)


@dataclass
class ShadowRedisConfig:
    """影子 Redis 服务器配置"""
    original_host: str = ""
    original_port: int = 6379
    shadow_host: str = ""
    shadow_port: int = 6379
    shadow_password: str = ""
    shadow_db_index: int = 0
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShadowRedisConfig":
        return cls(
            original_host=data.get("originalHost", data.get("host", "")),
            original_port=int(data.get("originalPort", data.get("port", 6379))),
            shadow_host=data.get("shadowHost", ""),
            shadow_port=int(data.get("shadowPort", 6379)),
            shadow_password=data.get("shadowPassword", ""),
            shadow_db_index=int(data.get("shadowDbIndex", data.get("shadowDb", 0))),
        )


@dataclass
class ShadowEsConfig:
    """影子 Elasticsearch 服务器配置"""
    original_hosts: List[str] = field(default_factory=list)
    shadow_hosts: List[str] = field(default_factory=list)
    shadow_api_key: str = ""
    shadow_username: str = ""
    shadow_password: str = ""
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShadowEsConfig":
        return cls(
            original_hosts=data.get("originalHosts", data.get("hosts", [])),
            shadow_hosts=data.get("shadowHosts", []),
            shadow_api_key=data.get("shadowApiKey", ""),
            shadow_username=data.get("shadowUsername", ""),
            shadow_password=data.get("shadowPassword", ""),
        )


@dataclass
class ShadowKafkaConfig:
    """影子 Kafka 配置"""
    original_bootstrap_servers: str = ""
    shadow_bootstrap_servers: str = ""
    topic_mapping: Dict[str, str] = field(default_factory=dict)
    consumer_group_suffix: str = "_shadow"
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShadowKafkaConfig":
        return cls(
            original_bootstrap_servers=data.get("originalBootstrapServers", ""),
            shadow_bootstrap_servers=data.get("shadowBootstrapServers", ""),
            topic_mapping=data.get("topicMapping", {}),
            consumer_group_suffix=data.get("consumerGroupSuffix", "_shadow"),
        )


class ShadowConfigCenter:
    """
    影子配置中心 - 存储和管理所有影子配置

    线程安全, 支持热更新和配置变更通知。
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._db_configs: Dict[str, ShadowDatabaseConfig] = {}
        self._redis_configs: Dict[str, ShadowRedisConfig] = {}
        self._es_configs: Dict[str, ShadowEsConfig] = {}
        self._kafka_configs: Dict[str, ShadowKafkaConfig] = {}
        self._callbacks: List[Callable[[str, Any, Any], None]] = []

    # ==================== Database configs ====================

    def register_db_config(self, config: ShadowDatabaseConfig) -> None:
        """注册影子库配置"""
        with self._lock:
            key = self._normalize_url(config.url)
            old = self._db_configs.get(key)
            self._db_configs[key] = config
            logger.info(f"注册影子库配置: {config.datasource_name or key}")
            self._notify("db_config", old, config)

    def get_db_config(self, original_url: str) -> Optional[ShadowDatabaseConfig]:
        """根据原始 URL 查找影子库配置"""
        with self._lock:
            key = self._normalize_url(original_url)
            cfg = self._db_configs.get(key)
            if cfg and cfg.enabled:
                return cfg
            # 模糊匹配: 按 host:port/db 匹配
            for k, c in self._db_configs.items():
                if c.enabled and self._urls_similar(original_url, k):
                    return c
            return None

    def get_db_config_by_name(self, name: str) -> Optional[ShadowDatabaseConfig]:
        """根据数据源名称查找"""
        with self._lock:
            for cfg in self._db_configs.values():
                if cfg.datasource_name == name and cfg.enabled:
                    return cfg
            return None

    def get_all_db_configs(self) -> Dict[str, ShadowDatabaseConfig]:
        """获取所有影子库配置"""
        with self._lock:
            return dict(self._db_configs)

    def unregister_db_config(self, url: str) -> bool:
        """删除影子库配置"""
        with self._lock:
            key = self._normalize_url(url)
            if key in self._db_configs:
                del self._db_configs[key]
                return True
            return False

    # ==================== Redis configs ====================

    def register_redis_config(self, config: ShadowRedisConfig) -> None:
        """注册影子 Redis 配置"""
        with self._lock:
            key = f"{config.original_host}:{config.original_port}"
            self._redis_configs[key] = config
            logger.info(f"注册影子 Redis: {key}")

    def get_redis_config(self, host: str, port: int = 6379) -> Optional[ShadowRedisConfig]:
        """查找影子 Redis 配置"""
        with self._lock:
            key = f"{host}:{port}"
            cfg = self._redis_configs.get(key)
            return cfg if cfg and cfg.enabled else None

    def get_all_redis_configs(self) -> Dict[str, ShadowRedisConfig]:
        with self._lock:
            return dict(self._redis_configs)

    def load_redis_configs(self, configs: List[ShadowRedisConfig]) -> None:
        """批量加载影子 Redis 配置"""
        with self._lock:
            old = dict(self._redis_configs)
            new = {}
            for cfg in configs:
                key = f"{cfg.original_host}:{cfg.original_port}"
                new[key] = cfg
            self._redis_configs = new
            if old != new:
                logger.info(f"批量加载 {len(configs)} 个影子 Redis 配置")
                self._notify("redis_configs", old, new)

    # ==================== Elasticsearch configs ====================

    def register_es_config(self, key: str, config: ShadowEsConfig) -> None:
        """注册影子 ES 配置"""
        with self._lock:
            self._es_configs[key] = config
            logger.info(f"注册影子 ES: {key}")

    def get_es_config(self, key: str) -> Optional[ShadowEsConfig]:
        """查找影子 ES 配置"""
        with self._lock:
            cfg = self._es_configs.get(key)
            return cfg if cfg and cfg.enabled else None

    def get_all_es_configs(self) -> Dict[str, ShadowEsConfig]:
        with self._lock:
            return dict(self._es_configs)

    def load_es_configs(self, configs: Dict[str, ShadowEsConfig]) -> None:
        """批量加载影子 ES 配置"""
        with self._lock:
            old = dict(self._es_configs)
            self._es_configs = dict(configs)
            if old != self._es_configs:
                logger.info(f"批量加载 {len(configs)} 个影子 ES 配置")
                self._notify("es_configs", old, self._es_configs)

    # ==================== Kafka configs ====================

    def register_kafka_config(self, config: ShadowKafkaConfig) -> None:
        """注册影子 Kafka 配置"""
        with self._lock:
            key = config.original_bootstrap_servers
            self._kafka_configs[key] = config
            logger.info(f"注册影子 Kafka: {key}")

    def get_kafka_config(self, bootstrap_servers: str) -> Optional[ShadowKafkaConfig]:
        """查找影子 Kafka 配置"""
        with self._lock:
            cfg = self._kafka_configs.get(bootstrap_servers)
            return cfg if cfg and cfg.enabled else None

    def get_all_kafka_configs(self) -> Dict[str, ShadowKafkaConfig]:
        with self._lock:
            return dict(self._kafka_configs)

    def load_kafka_configs(self, configs: List[ShadowKafkaConfig]) -> None:
        """批量加载影子 Kafka 配置"""
        with self._lock:
            old = dict(self._kafka_configs)
            new = {}
            for cfg in configs:
                new[cfg.original_bootstrap_servers] = cfg
            self._kafka_configs = new
            if old != new:
                logger.info(f"批量加载 {len(configs)} 个影子 Kafka 配置")
                self._notify("kafka_configs", old, new)

    # ==================== Callbacks ====================

    def on_change(self, callback: Callable[[str, Any, Any], None]) -> None:
        """注册配置变更回调"""
        self._callbacks.append(callback)

    # ==================== Bulk load ====================

    def load_db_configs(self, configs: List[ShadowDatabaseConfig]) -> None:
        """批量加载影子库配置"""
        with self._lock:
            old = dict(self._db_configs)
            new = {}
            for cfg in configs:
                key = self._normalize_url(cfg.url)
                new[key] = cfg
            self._db_configs = new
            changed = old != new
            if changed:
                logger.info(f"批量加载 {len(configs)} 个影子库配置")
                self._notify("db_configs", old, new)

    # ==================== Internal ====================

    @staticmethod
    def _normalize_url(url: str) -> str:
        """规范化 URL 用于匹配"""
        url = url.strip().lower()
        if url.startswith("jdbc:"):
            url = url[5:]
        if url.startswith("mysql+pymysql://"):
            url = "mysql://" + url[len("mysql+pymysql://"):]
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql://" + url[len("postgresql+psycopg2://"):]
        return url

    @staticmethod
    def _urls_similar(url1: str, url2: str) -> bool:
        """检查两个 URL 是否相似 (忽略协议前缀)"""
        n1 = ShadowConfigCenter._normalize_url(url1)
        n2 = ShadowConfigCenter._normalize_url(url2)
        return n1 == n2

    def _notify(self, event_type: str, old: Any, new: Any) -> None:
        """通知配置变更"""
        for cb in self._callbacks:
            try:
                cb(event_type, old, new)
            except Exception as e:
                logger.error(f"配置变更回调异常: {e}")
