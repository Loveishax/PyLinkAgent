"""
WhitelistManager - 白名单管理

参考 Java LinkAgent 的 WhitelistManager 实现，提供 URL/RPC/MQ 等白名单管理。
"""

import logging
import re
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import threading


logger = logging.getLogger(__name__)


class MatchType(Enum):
    """匹配类型"""
    EXACT = "EXACT"  # 精确匹配
    PREFIX = "PREFIX"  # 前缀匹配
    REGEX = "REGEX"  # 正则匹配
    CONTAINS = "CONTAINS"  # 包含匹配


@dataclass
class WhitelistEntry:
    """白名单条目"""
    pattern: str
    match_type: MatchType
    description: str = ""
    enabled: bool = True

    # 预编译的正则
    _compiled_regex: Optional[re.Pattern] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.match_type == MatchType.REGEX:
            try:
                self._compiled_regex = re.compile(self.pattern)
            except re.error as e:
                logger.error(f"WhitelistManager: 无效的正则表达式 {self.pattern}, error={e}")
                raise ValueError(f"Invalid regex pattern: {self.pattern}")

    def matches(self, target: str) -> bool:
        """
        检查目标是否匹配

        Args:
            target: 目标字符串

        Returns:
            bool: 是否匹配
        """
        if not self.enabled:
            return False

        if self.match_type == MatchType.EXACT:
            return target == self.pattern
        elif self.match_type == MatchType.PREFIX:
            return target.startswith(self.pattern)
        elif self.match_type == MatchType.CONTAINS:
            return self.pattern in target
        elif self.match_type == MatchType.REGEX:
            if self._compiled_regex:
                return bool(self._compiled_regex.match(target))
            return False

        return False


class WhitelistManager:
    """
    白名单管理器

    对应 Java 的 WhitelistManager
    """

    # URL 白名单
    _url_whitelist: List[WhitelistEntry] = []
    _url_whitelist_lock = threading.Lock()

    # RPC 白名单
    _rpc_whitelist: List[WhitelistEntry] = []
    _rpc_whitelist_lock = threading.Lock()

    # MQ 白名单
    _mq_whitelist: List[WhitelistEntry] = []
    _mq_whitelist_lock = threading.Lock()

    # Cache Key 白名单
    _cache_key_whitelist: List[WhitelistEntry] = []
    _cache_key_whitelist_lock = threading.Lock()

    # 是否启用白名单
    _whitelist_enabled: bool = True

    # 默认 URL 白名单（放过不需要追踪的 URL）
    _default_url_whitelist: List[str] = [
        # 健康检查
        "/health",
        "/healthcheck",
        "/ping",
        "/actuator/health",

        # 静态资源
        "/static/",
        "/assets/",
        "/favicon.ico",
        "/robots.txt",

        # 监控端点
        "/metrics",
        "/prometheus",
        "/jmx",

        # 文档
        "/doc/",
        "/swagger/",
        "/api-docs/",
    ]

    # 默认 RPC 白名单
    _default_rpc_whitelist: List[str] = [
        "echo",
        "ping",
        "health",
    ]

    @classmethod
    def init(cls) -> None:
        """初始化白名单（加载默认配置）"""
        cls.clear_all()

        # 添加默认 URL 白名单
        for pattern in cls._default_url_whitelist:
            cls.add_url_whitelist(pattern, MatchType.PREFIX if pattern.endswith("/") else MatchType.EXACT)

        # 添加默认 RPC 白名单
        for pattern in cls._default_rpc_whitelist:
            cls.add_rpc_whitelist(pattern, MatchType.EXACT)

        logger.info("WhitelistManager: 白名单初始化完成")

    # ==================== URL 白名单 ====================

    @classmethod
    def add_url_whitelist(
        cls,
        pattern: str,
        match_type: MatchType = MatchType.EXACT,
        description: str = ""
    ) -> None:
        """
        添加 URL 白名单

        Args:
            pattern: 匹配模式
            match_type: 匹配类型
            description: 描述
        """
        try:
            entry = WhitelistEntry(pattern, match_type, description)
            with cls._url_whitelist_lock:
                cls._url_whitelist.append(entry)
            logger.debug(f"WhitelistManager: 添加 URL 白名单 {pattern} ({match_type.value})")
        except ValueError as e:
            logger.error(f"WhitelistManager: 添加 URL 白名单失败 {e}")

    @classmethod
    def remove_url_whitelist(cls, pattern: str) -> bool:
        """
        移除 URL 白名单

        Args:
            pattern: 匹配模式

        Returns:
            bool: 是否成功移除
        """
        with cls._url_whitelist_lock:
            for i, entry in enumerate(cls._url_whitelist):
                if entry.pattern == pattern:
                    cls._url_whitelist.pop(i)
                    logger.debug(f"WhitelistManager: 移除 URL 白名单 {pattern}")
                    return True
        return False

    @classmethod
    def is_url_in_whitelist(cls, url: str) -> bool:
        """
        检查 URL 是否在白名单中

        Args:
            url: URL 路径

        Returns:
            bool: 是否在白名单中
        """
        if not cls._whitelist_enabled:
            return False

        with cls._url_whitelist_lock:
            for entry in cls._url_whitelist:
                if entry.matches(url):
                    return True
        return False

    @classmethod
    def get_url_whitelist(cls) -> List[Dict]:
        """获取 URL 白名单列表"""
        with cls._url_whitelist_lock:
            return [
                {
                    "pattern": entry.pattern,
                    "match_type": entry.match_type.value,
                    "description": entry.description,
                    "enabled": entry.enabled
                }
                for entry in cls._url_whitelist
            ]

    # ==================== RPC 白名单 ====================

    @classmethod
    def add_rpc_whitelist(
        cls,
        pattern: str,
        match_type: MatchType = MatchType.EXACT,
        description: str = ""
    ) -> None:
        """
        添加 RPC 白名单

        Args:
            pattern: 匹配模式
            match_type: 匹配类型
            description: 描述
        """
        try:
            entry = WhitelistEntry(pattern, match_type, description)
            with cls._rpc_whitelist_lock:
                cls._rpc_whitelist.append(entry)
            logger.debug(f"WhitelistManager: 添加 RPC 白名单 {pattern} ({match_type.value})")
        except ValueError as e:
            logger.error(f"WhitelistManager: 添加 RPC 白名单失败 {e}")

    @classmethod
    def remove_rpc_whitelist(cls, pattern: str) -> bool:
        """移除 RPC 白名单"""
        with cls._rpc_whitelist_lock:
            for i, entry in enumerate(cls._rpc_whitelist):
                if entry.pattern == pattern:
                    cls._rpc_whitelist.pop(i)
                    return True
        return False

    @classmethod
    def is_rpc_in_whitelist(cls, service_name: str, method_name: str = "") -> bool:
        """
        检查 RPC 是否在白名单中

        Args:
            service_name: 服务名称
            method_name: 方法名称（可选）

        Returns:
            bool: 是否在白名单中
        """
        if not cls._whitelist_enabled:
            return False

        with cls._rpc_whitelist_lock:
            for entry in cls._rpc_whitelist:
                # 匹配服务名称
                if entry.matches(service_name):
                    return True
                # 匹配完整的服务名。方法名
                if method_name:
                    full_name = f"{service_name}.{method_name}"
                    if entry.matches(full_name):
                        return True
        return False

    @classmethod
    def get_rpc_whitelist(cls) -> List[Dict]:
        """获取 RPC 白名单列表"""
        with cls._rpc_whitelist_lock:
            return [
                {
                    "pattern": entry.pattern,
                    "match_type": entry.match_type.value,
                    "description": entry.description,
                    "enabled": entry.enabled
                }
                for entry in cls._rpc_whitelist
            ]

    # ==================== MQ 白名单 ====================

    @classmethod
    def add_mq_whitelist(
        cls,
        pattern: str,
        match_type: MatchType = MatchType.EXACT,
        description: str = ""
    ) -> None:
        """添加 MQ 白名单"""
        try:
            entry = WhitelistEntry(pattern, match_type, description)
            with cls._mq_whitelist_lock:
                cls._mq_whitelist.append(entry)
            logger.debug(f"WhitelistManager: 添加 MQ 白名单 {pattern} ({match_type.value})")
        except ValueError as e:
            logger.error(f"WhitelistManager: 添加 MQ 白名单失败 {e}")

    @classmethod
    def remove_mq_whitelist(cls, pattern: str) -> bool:
        """移除 MQ 白名单"""
        with cls._mq_whitelist_lock:
            for i, entry in enumerate(cls._mq_whitelist):
                if entry.pattern == pattern:
                    cls._mq_whitelist.pop(i)
                    return True
        return False

    @classmethod
    def is_mq_in_whitelist(cls, topic: str, queue_name: str = "") -> bool:
        """
        检查 MQ 是否在白名单中

        Args:
            topic: Topic 名称
            queue_name: 队列名称（可选）

        Returns:
            bool: 是否在白名单中
        """
        if not cls._whitelist_enabled:
            return False

        with cls._mq_whitelist_lock:
            for entry in cls._mq_whitelist:
                if entry.matches(topic):
                    return True
                if queue_name and entry.matches(queue_name):
                    return True
        return False

    @classmethod
    def get_mq_whitelist(cls) -> List[Dict]:
        """获取 MQ 白名单列表"""
        with cls._mq_whitelist_lock:
            return [
                {
                    "pattern": entry.pattern,
                    "match_type": entry.match_type.value,
                    "description": entry.description,
                    "enabled": entry.enabled
                }
                for entry in cls._mq_whitelist
            ]

    # ==================== Cache Key 白名单 ====================

    @classmethod
    def add_cache_key_whitelist(
        cls,
        pattern: str,
        match_type: MatchType = MatchType.EXACT,
        description: str = ""
    ) -> None:
        """添加 Cache Key 白名单"""
        try:
            entry = WhitelistEntry(pattern, match_type, description)
            with cls._cache_key_whitelist_lock:
                cls._cache_key_whitelist.append(entry)
            logger.debug(f"WhitelistManager: 添加 Cache Key 白名单 {pattern} ({match_type.value})")
        except ValueError as e:
            logger.error(f"WhitelistManager: 添加 Cache Key 白名单失败 {e}")

    @classmethod
    def remove_cache_key_whitelist(cls, pattern: str) -> bool:
        """移除 Cache Key 白名单"""
        with cls._cache_key_whitelist_lock:
            for i, entry in enumerate(cls._cache_key_whitelist):
                if entry.pattern == pattern:
                    cls._cache_key_whitelist.pop(i)
                    return True
        return False

    @classmethod
    def is_cache_key_in_whitelist(cls, cache_key: str) -> bool:
        """检查 Cache Key 是否在白名单中"""
        if not cls._whitelist_enabled:
            return False

        with cls._cache_key_whitelist_lock:
            for entry in cls._cache_key_whitelist:
                if entry.matches(cache_key):
                    return True
        return False

    @classmethod
    def get_cache_key_whitelist(cls) -> List[Dict]:
        """获取 Cache Key 白名单列表"""
        with cls._cache_key_whitelist_lock:
            return [
                {
                    "pattern": entry.pattern,
                    "match_type": entry.match_type.value,
                    "description": entry.description,
                    "enabled": entry.enabled
                }
                for entry in cls._cache_key_whitelist
            ]

    # ==================== 全局控制 ====================

    @classmethod
    def enable_whitelist(cls) -> None:
        """启用白名单"""
        cls._whitelist_enabled = True
        logger.info("WhitelistManager: 白名单已启用")

    @classmethod
    def disable_whitelist(cls) -> None:
        """禁用白名单"""
        cls._whitelist_enabled = False
        logger.info("WhitelistManager: 白名单已禁用")

    @classmethod
    def is_whitelist_enabled(cls) -> bool:
        """检查白名单是否启用"""
        return cls._whitelist_enabled

    @classmethod
    def clear_all(cls) -> None:
        """清空所有白名单"""
        with cls._url_whitelist_lock:
            cls._url_whitelist.clear()
        with cls._rpc_whitelist_lock:
            cls._rpc_whitelist.clear()
        with cls._mq_whitelist_lock:
            cls._mq_whitelist.clear()
        with cls._cache_key_whitelist_lock:
            cls._cache_key_whitelist.clear()
        logger.info("WhitelistManager: 所有白名单已清空")

    @classmethod
    def get_stats(cls) -> Dict[str, int]:
        """获取白名单统计信息"""
        return {
            "url_count": len(cls._url_whitelist),
            "rpc_count": len(cls._rpc_whitelist),
            "mq_count": len(cls._mq_whitelist),
            "cache_key_count": len(cls._cache_key_whitelist),
            "enabled": cls._whitelist_enabled
        }


# 全局 WhitelistManager 实例
_whitelist_manager: Optional[WhitelistManager] = None


def get_whitelist_manager() -> WhitelistManager:
    """获取 WhitelistManager 单例"""
    global _whitelist_manager
    if _whitelist_manager is None:
        _whitelist_manager = WhitelistManager()
    return _whitelist_manager
