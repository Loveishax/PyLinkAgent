"""
PyLinkAgent ZooKeeper 日志服务器发现

参考 Java LinkAgent 的 ZkPathStore 和 CuratorZkPathChildrenCache 实现
用于在 ZooKeeper 中发现和监听日志服务器
"""

import json
import threading
import os
from typing import Optional, List, Callable, Dict, Any
from dataclasses import dataclass
import logging
import time

from .zk_client import ZkClient, ConnectionState
from .config import ZkConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class LogServerInfo:
    """
    日志服务器信息

    对应 Java Agent 中的日志服务器节点数据
    """
    # 服务器地址
    host: str = ""
    port: int = 0
    address: str = ""  # host:port

    # 服务器类型
    server_type: str = "http"  # http, grpc, tcp

    # 服务器状态
    status: str = "online"  # online, offline, unknown

    # 服务器信息
    name: str = ""
    version: str = ""
    region: str = ""

    # 注册时间
    register_time: str = ""
    last_heartbeat: str = ""

    # 额外属性
    properties: Dict[str, Any] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
        if not self.address and self.host and self.port:
            self.address = f"{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "host": self.host,
            "port": self.port,
            "address": self.address,
            "serverType": self.server_type,
            "status": self.status,
            "name": self.name,
            "version": self.version,
            "region": self.region,
            "registerTime": self.register_time,
            "lastHeartbeat": self.last_heartbeat,
            "properties": self.properties,
        }

    def to_json(self) -> bytes:
        """转换为 JSON 字节"""
        return json.dumps(self.to_dict(), ensure_ascii=False).encode('utf-8')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogServerInfo":
        """从字典创建"""
        properties = data.get("properties", {})
        if properties is None:
            properties = {}

        return cls(
            host=data.get("host", ""),
            port=data.get("port", 0),
            address=data.get("address", ""),
            server_type=data.get("serverType", "http"),
            status=data.get("status", "online"),
            name=data.get("name", ""),
            version=data.get("version", ""),
            region=data.get("region", ""),
            register_time=data.get("registerTime", ""),
            last_heartbeat=data.get("lastHeartbeat", ""),
            properties=properties,
        )


class ZkLogServerDiscovery:
    """
    ZooKeeper 日志服务器发现

    参考 Java: CuratorZkPathChildrenCache + ZkPathStore
    监听日志服务器目录，发现可用的日志服务器
    """

    # 默认日志服务器路径 (对应 Java: ZkPathStore.server_base_path)
    DEFAULT_SERVER_PATH = "/config/log/pradar/server"

    def __init__(self, config: Optional[ZkConfig] = None,
                 client: Optional[ZkClient] = None,
                 server_path: Optional[str] = None):
        """
        初始化日志服务器发现

        Args:
            config: ZK 配置
            client: ZK 客户端
            server_path: 日志服务器路径，默认 /config/log/pradar/server
        """
        self.config = config or get_config()
        self.client = client
        self.server_path = server_path or self.DEFAULT_SERVER_PATH

        self._is_running = False
        self._is_connected = False
        self._lock = threading.Lock()

        # 服务器缓存
        self._servers: Dict[str, LogServerInfo] = {}
        self._server_ids: List[str] = []

        # 监听器
        self._server_listeners: List[Callable[[List[str]], None]] = []

        # 子节点缓存路径
        self._children_cache_path = self.server_path

    def initialize(self, client: Optional[ZkClient] = None) -> bool:
        """
        初始化日志服务器发现

        Args:
            client: ZK 客户端

        Returns:
            bool: 初始化成功返回 True
        """
        with self._lock:
            if self.client and self.client.is_connected():
                logger.warning("日志服务器发现已初始化")
                return True

            try:
                # 创建或获取 ZK 客户端
                if client is None:
                    from .zk_client import create_client
                    self.client = create_client(self.config)
                else:
                    self.client = client

                # 连接 ZK
                if not self.client.connect():
                    logger.error("ZK 连接失败")
                    return False

                # 确保服务器路径存在
                if not self.client.ensure_path_exists(self.server_path):
                    logger.error(f"创建服务器路径失败：{self.server_path}")
                    return False

                logger.info(f"日志服务器发现初始化成功：{self.server_path}")
                return True

            except Exception as e:
                logger.error(f"日志服务器发现初始化失败：{e}")
                return False

    def start(self) -> bool:
        """
        启动日志服务器发现

        Returns:
            bool: 启动成功返回 True
        """
        with self._lock:
            if self._is_running:
                logger.warning("日志服务器发现已启动")
                return True

            if not self.client:
                logger.error("日志服务器发现未初始化")
                return False

            try:
                # 添加状态监听器
                self.client.add_state_listener(self._on_connection_state_change)

                # 添加子节点监听
                self._add_children_watch()

                # 初始加载服务器列表
                self._refresh_servers()

                self._is_running = True
                self._is_connected = True

                logger.info(f"日志服务器发现启动成功：{len(self._server_ids)} 个服务器")
                return True

            except Exception as e:
                logger.error(f"日志服务器发现启动失败：{e}")
                return False

    def stop(self) -> None:
        """停止日志服务器发现"""
        with self._lock:
            if not self._is_running:
                return

            try:
                self._is_running = False
                self.client.remove_state_listener(self._on_connection_state_change)
                logger.info("日志服务器发现已停止")

            except Exception as e:
                logger.error(f"日志服务器发现停止失败：{e}")

    def get_servers(self) -> List[LogServerInfo]:
        """获取所有服务器列表"""
        with self._lock:
            return [self._servers.get(sid) for sid in self._server_ids if self._servers.get(sid)]

    def get_server_ids(self) -> List[str]:
        """获取服务器 ID 列表"""
        with self._lock:
            return self._server_ids.copy()

    def get_server(self, server_id: str) -> Optional[LogServerInfo]:
        """获取指定服务器信息"""
        with self._lock:
            return self._servers.get(server_id)

    def get_online_servers(self) -> List[LogServerInfo]:
        """获取在线服务器列表"""
        with self._lock:
            return [
                self._servers.get(sid)
                for sid in self._server_ids
                if self._servers.get(sid) and self._servers.get(sid).status == "online"
            ]

    def add_server_listener(self, listener: Callable[[List[str]], None]) -> None:
        """
        添加服务器监听器

        Args:
            listener: 监听器函数，参数为服务器 ID 列表
        """
        self._server_listeners.append(listener)
        logger.debug(f"已添加服务器监听器")

    def remove_server_listener(self, listener: Callable[[List[str]], None]) -> None:
        """移除服务器监听器"""
        if listener in self._server_listeners:
            self._server_listeners.remove(listener)

    def _refresh_servers(self) -> bool:
        """刷新服务器列表"""
        with self._lock:
            try:
                children = self.client.list_children(self.server_path)
                old_server_ids = self._server_ids
                self._server_ids = children if children else []

                # 更新服务器信息
                for server_id in self._server_ids:
                    server_path = f"{self.server_path}/{server_id}"
                    data = self.client.get(server_path)
                    if data:
                        try:
                            server_data = json.loads(data.decode('utf-8'))
                            server_info = LogServerInfo.from_dict(server_data)
                            self._servers[server_id] = server_info
                        except Exception as e:
                            logger.error(f"解析服务器信息失败：{server_id}, error: {e}")

                # 通知监听器
                if self._server_ids != old_server_ids:
                    self._notify_listeners()

                logger.debug(f"服务器列表刷新成功：{len(self._server_ids)} 个服务器")
                return True

            except Exception as e:
                logger.error(f"刷新服务器列表失败：{e}")
                return False

    def _add_children_watch(self) -> None:
        """添加子节点监听"""
        def on_children_change(children: List[str]):
            if self._is_running and self._is_connected:
                logger.info(f"服务器列表发生变化：{len(children)} 个服务器")
                self._refresh_servers()

        self.client.watch_children(self.server_path, on_children_change)

    def _on_connection_state_change(self, state: ConnectionState) -> None:
        """
        连接状态变化回调

        Args:
            state: 连接状态
        """
        if state == ConnectionState.RECONNECTED:
            if not self._is_connected:
                self._is_connected = True
                try:
                    self._refresh_servers()
                    logger.info("日志服务器发现从 RECONNECTED 事件恢复")
                except Exception as e:
                    logger.error(f"重连后刷新失败：{e}")
        elif state in [ConnectionState.SUSPENDED, ConnectionState.LOST]:
            self._is_connected = False
            logger.warning("ZK 连接中断，日志服务器发现标记为未连接")

    def _notify_listeners(self) -> None:
        """通知监听器"""
        for listener in self._server_listeners:
            try:
                listener(self._server_ids)
            except Exception as e:
                logger.error(f"服务器监听器执行失败：{e}")


class LogServerSelector:
    """
    日志服务器选择器

    从发现的服务器中选择一个可用的服务器
    """

    def __init__(self, discovery: ZkLogServerDiscovery):
        """
        初始化服务器选择器

        Args:
            discovery: 日志服务器发现实例
        """
        self.discovery = discovery

    def select(self) -> Optional[LogServerInfo]:
        """
        选择一个可用的服务器

        Returns:
            LogServerInfo: 服务器信息，无可用服务器返回 None
        """
        online_servers = self.discovery.get_online_servers()
        if not online_servers:
            return None

        # 简单轮询选择
        # TODO: 支持权重、就近等策略
        return online_servers[0]

    def select_by_region(self, region: str) -> Optional[LogServerInfo]:
        """
        按区域选择服务器

        Args:
            region: 区域

        Returns:
            LogServerInfo: 服务器信息，无匹配服务器返回 None
        """
        online_servers = self.discovery.get_online_servers()
        for server in online_servers:
            if server.region == region:
                return server

        # 如果没有匹配的区域，返回第一个在线服务器
        return online_servers[0] if online_servers else None


# ==================== 全局管理器 ====================

_global_discovery: Optional[ZkLogServerDiscovery] = None
_discovery_lock = threading.Lock()


def get_log_server_discovery(config: Optional[ZkConfig] = None) -> Optional[ZkLogServerDiscovery]:
    """
    获取全局日志服务器发现实例

    Args:
        config: ZK 配置

    Returns:
        ZkLogServerDiscovery 实例
    """
    global _global_discovery

    with _discovery_lock:
        if _global_discovery is None:
            _global_discovery = ZkLogServerDiscovery(config)
        return _global_discovery


def reset_log_server_discovery():
    """重置日志服务器发现 (用于测试)"""
    global _global_discovery
    with _discovery_lock:
        if _global_discovery:
            _global_discovery.stop()
            _global_discovery = None
