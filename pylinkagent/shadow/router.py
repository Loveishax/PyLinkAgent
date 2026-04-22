"""
影子路由器 - 路由决策引擎

根据 Pradar trace context 判断是否路由到影子,
并根据配置生成影子连接参数。
"""

import logging
import re
from typing import Optional, Tuple, Dict, Any

from ..pradar import Pradar, PradarSwitcher
from .config_center import (
    ShadowConfigCenter,
    ShadowDatabaseConfig,
    ShadowRedisConfig,
    ShadowEsConfig,
    ShadowKafkaConfig,
)
from .context import get_shadow_context

logger = logging.getLogger(__name__)


class ShadowRouter:
    """
    影子路由器 - 决策引擎

    两门判断:
    1. PradarSwitcher.is_cluster_test_enabled() - 全局开关
    2. Pradar.is_cluster_test() - 当前请求流量染色
    """

    def __init__(self, config_center: ShadowConfigCenter):
        self.config_center = config_center
        self._context = get_shadow_context()

    # ==================== 核心路由判断 ====================

    def should_route(self) -> bool:
        """
        判断是否应该路由到影子

        同时满足两个条件:
        1. 全局压测开关已打开
        2. 当前请求是压测流量
        """
        if not PradarSwitcher.is_cluster_test_enabled():
            return False
        if not Pradar.is_cluster_test():
            return False
        self._context.set_shadow_enabled(True)
        return True

    def is_shadow_enabled(self) -> bool:
        """当前线程是否处于影子路由模式"""
        return self._context.is_shadow_enabled()

    # ==================== MySQL 路由 ====================

    def route_mysql(
        self,
        original_url: str,
        original_username: str = "",
        original_password: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        路由 MySQL 连接

        Args:
            original_url: 原始数据库 URL (jdbc:mysql://host:port/db)
            original_username: 原始用户名
            original_password: 原始密码

        Returns:
            影子连接参数字典, 找不到配置返回 None
            格式: {host, port, user, password, database}
        """
        if not self.should_route():
            return None

        config = self.config_center.get_db_config(original_url)
        if not config:
            logger.debug(f"未找到影子库配置: {original_url}")
            return None

        if config.ds_type == 0:
            # 模式 0: 独立影子库
            return self._parse_mysql_url(config.shadow_url, config.shadow_username or original_username, config.shadow_password or original_password)
        elif config.ds_type == 1:
            # 模式 1: 同库影子表 - 不改变连接参数
            return {"mode": "same_db", "config": config}
        elif config.ds_type == 2:
            # 模式 2: 影子库 + 影子表
            return self._parse_mysql_url(config.shadow_url, config.shadow_username or original_username, config.shadow_password or original_password)

        return None

    def get_shadow_table_name(self, original_table: str, config: ShadowDatabaseConfig) -> str:
        """获取影子表名"""
        # 先在映射表中查找
        if original_table in config.business_shadow_tables:
            return config.business_shadow_tables[original_table]

        # 使用 PT_ 前缀自动生成
        prefix = config.shadow_account_prefix or "PT_"
        return f"{prefix}{original_table}"

    # ==================== Redis 路由 ====================

    def route_redis(
        self,
        host: str = "localhost",
        port: int = 6379,
    ) -> Optional[Dict[str, Any]]:
        """
        路由 Redis 连接

        Returns:
            影子 Redis 参数字典 {host, port, db, password}, 找不到返回 None
        """
        if not self.should_route():
            return None

        config = self.config_center.get_redis_config(host, port)
        if not config:
            return None

        return {
            "host": config.shadow_host or host,
            "port": config.shadow_port or port,
            "db": config.shadow_db_index,
            "password": config.shadow_password or None,
        }

    # ==================== Elasticsearch 路由 ====================

    def route_es(
        self,
        hosts: list = None,
    ) -> Optional[Dict[str, Any]]:
        """
        路由 Elasticsearch 连接

        Returns:
            影子 ES 参数字典, 找不到返回 None
        """
        if not self.should_route():
            return None

        # 尝试按 hosts 匹配
        for key, config in self.config_center.get_all_es_configs().items():
            if self._hosts_overlap(hosts or [], config.original_hosts):
                return {
                    "hosts": config.shadow_hosts,
                    "api_key": config.shadow_api_key or None,
                    "basic_auth": (config.shadow_username, config.shadow_password)
                        if config.shadow_username else None,
                }

        return None

    # ==================== Kafka 路由 ====================

    def route_kafka(
        self,
        bootstrap_servers: str = "",
        topic: str = "",
        group_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        路由 Kafka 连接

        Returns:
            影子 Kafka 参数字典, 找不到返回 None
        """
        if not self.should_route():
            return None

        config = self.config_center.get_kafka_config(bootstrap_servers)
        if not config:
            return None

        result = {
            "bootstrap_servers": config.shadow_bootstrap_servers or bootstrap_servers,
        }

        if topic and config.topic_mapping:
            result["topic"] = config.topic_mapping.get(topic, topic)

        if group_id and config.consumer_group_suffix:
            result["group_id"] = f"{group_id}{config.consumer_group_suffix}"

        return result

    # ==================== 内部工具方法 ====================

    @staticmethod
    def _parse_mysql_url(jdbc_url: str, username: str, password: str) -> Dict[str, Any]:
        """解析 JDBC URL 为 MySQL 连接参数"""
        # jdbc:mysql://host:port/database
        pattern = r'jdbc:mysql://([^:/]+):?(\d+)?/([^?]+)'
        match = re.match(pattern, jdbc_url)
        if match:
            return {
                "host": match.group(1),
                "port": int(match.group(2)) if match.group(2) else 3306,
                "database": match.group(3),
                "user": username,
                "password": password,
            }
        # 纯 host:port/db 格式
        pattern2 = r'([^:/]+):?(\d+)?/([^?]+)'
        match = re.match(pattern2, jdbc_url)
        if match:
            return {
                "host": match.group(1),
                "port": int(match.group(2)) if match.group(2) else 3306,
                "database": match.group(3),
                "user": username,
                "password": password,
            }
        return {}

    @staticmethod
    def _hosts_overlap(hosts1: list, hosts2: list) -> bool:
        """检查两组 hosts 是否有重叠"""
        set1 = set(h.rstrip("/") for h in hosts1)
        set2 = set(h.rstrip("/") for h in hosts2)
        return bool(set1 & set2)
