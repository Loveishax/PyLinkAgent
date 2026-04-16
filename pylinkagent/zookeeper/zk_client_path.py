"""
PyLinkAgent ZooKeeper 客户端路径注册

参考 Java LinkAgent 的 CuratorZkPathChildrenCache 和 ZookeeperRegister 实现
用于在 ZooKeeper 中注册客户端路径，监听控制台下发的配置和命令
"""

import json
import threading
import os
import time
from typing import Optional, List, Callable, Dict, Any
from dataclasses import dataclass
import logging

from .zk_client import ZkClient, ConnectionState, ZkNodeStat
from .config import ZkConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class ClientNodeData:
    """
    客户端节点数据结构

    对应 Java Agent 注册到 ZK 的客户端信息
    """
    # 基础信息
    address: str = ""
    host: str = ""
    name: str = ""
    pid: str = ""
    agent_id: str = ""

    # 版本信息
    agent_language: str = "PYTHON"
    agent_version: str = "1.0.0"
    simulator_version: str = "1.0.0"

    # 租户信息
    tenant_app_key: str = ""
    env_code: str = "test"
    user_id: str = ""

    # 注册信息
    register_time: str = ""
    last_heartbeat: str = ""

    # 能力标识
    capabilities: List[str] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "address": self.address,
            "host": self.host,
            "name": self.name,
            "pid": self.pid,
            "agentId": self.agent_id,
            "agentLanguage": self.agent_language,
            "agentVersion": self.agent_version,
            "simulatorVersion": self.simulator_version,
            "tenantAppKey": self.tenant_app_key,
            "envCode": self.env_code,
            "userId": self.user_id,
            "registerTime": self.register_time,
            "lastHeartbeat": self.last_heartbeat,
            "capabilities": self.capabilities,
        }

    def to_json(self) -> bytes:
        """转换为 JSON 字节"""
        return json.dumps(self.to_dict(), ensure_ascii=False).encode('utf-8')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClientNodeData":
        """从字典创建"""
        return cls(
            address=data.get("address", ""),
            host=data.get("host", ""),
            name=data.get("name", ""),
            pid=data.get("pid", ""),
            agent_id=data.get("agentId", ""),
            agent_language=data.get("agentLanguage", "PYTHON"),
            agent_version=data.get("agentVersion", "1.0.0"),
            simulator_version=data.get("simulatorVersion", "1.0.0"),
            tenant_app_key=data.get("tenantAppKey", ""),
            env_code=data.get("envCode", "test"),
            user_id=data.get("userId", ""),
            register_time=data.get("registerTime", ""),
            last_heartbeat=data.get("lastHeartbeat", ""),
            capabilities=data.get("capabilities", []),
        )


class ZkClientPathNode:
    """
    ZooKeeper 客户端路径节点

    参考 Java: CuratorZkNodeCache
    在客户端路径下创建持久节点，存储客户端配置信息
    """

    def __init__(self, client: ZkClient, path: str, data: bytes = b''):
        """
        初始化客户端路径节点

        Args:
            client: ZK 客户端
            path: 节点路径
            data: 初始数据
        """
        self.client = client
        self.path = path
        self.data = data
        self._is_running = False
        self._is_connected = False
        self._lock = threading.Lock()

    def start(self) -> bool:
        """
        启动客户端路径节点

        Returns:
            bool: 启动成功返回 True
        """
        with self._lock:
            if self._is_running:
                logger.warning(f"客户端路径节点已在运行：{self.path}")
                return True

            try:
                # 添加状态监听器
                self.client.add_state_listener(self._on_connection_state_change)

                # 确保父路径存在
                parent_path = os.path.dirname(self.path)
                if not self.client.ensure_path_exists(parent_path):
                    logger.error(f"创建父路径失败：{parent_path}")
                    return False

                # 创建持久节点（非临时节点）
                if not self.client.exists(self.path):
                    self.client.create(self.path, self.data, ephemeral=False, make_parent_dirs=False)
                    logger.info(f"客户端路径节点创建成功：{self.path}")
                else:
                    # 节点存在，更新数据
                    self.client.set(self.path, self.data)
                    logger.info(f"客户端路径节点数据已更新：{self.path}")

                self._is_running = True
                self._is_connected = True

                # 添加节点监听
                self._add_node_watch()

                return True

            except Exception as e:
                logger.error(f"客户端路径节点启动失败：{self.path}, error: {e}")
                return False

    def stop(self) -> None:
        """停止客户端路径节点"""
        with self._lock:
            if not self._is_running:
                return

            try:
                self._is_running = False

                # 移除状态监听器
                self.client.remove_state_listener(self._on_connection_state_change)

                # 删除节点
                self.client.delete(self.path)
                logger.info(f"客户端路径节点已删除：{self.path}")

            except Exception as e:
                logger.error(f"客户端路径节点停止失败：{self.path}, error: {e}")

    def set_data(self, data: bytes) -> bool:
        """
        设置节点数据

        Args:
            data: 数据

        Returns:
            bool: 设置成功返回 True
        """
        with self._lock:
            if not self._is_running:
                logger.warning(f"客户端路径节点未运行，无法设置数据：{self.path}")
                return False

            try:
                self.data = data
                self.client.set(self.path, data)
                logger.debug(f"客户端路径数据已更新：{self.path}")
                return True
            except Exception as e:
                logger.error(f"设置客户端路径数据失败：{self.path}, error: {e}")
                return False

    def get_data(self) -> bytes:
        """获取节点数据"""
        return self.data

    def is_running(self) -> bool:
        """检查节点是否运行"""
        return self._is_running

    def _reset(self) -> None:
        """重置节点"""
        with self._lock:
            if not self._is_running:
                return

            try:
                # 检查节点是否存在
                if self.client.exists(self.path):
                    # 节点存在，更新数据
                    self.client.set(self.path, self.data)
                    logger.debug(f"客户端路径节点数据已重置：{self.path}")
                else:
                    # 节点不存在，重新创建
                    self.client.create(self.path, self.data, ephemeral=False)
                    logger.info(f"客户端路径节点重新创建：{self.path}")

                self._add_node_watch()

            except Exception as e:
                logger.error(f"重置客户端路径节点失败：{self.path}, error: {e}")

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
                    self._reset()
                    logger.info(f"客户端路径节点从 RECONNECTED 事件恢复：{self.path}")
                except Exception as e:
                    logger.error(f"重连后重置失败：{self.path}, error: {e}")
        elif state in [ConnectionState.SUSPENDED, ConnectionState.LOST]:
            self._is_connected = False
            logger.warning(f"ZK 连接中断，客户端路径节点标记为未连接：{self.path}")

    def _add_node_watch(self) -> None:
        """添加节点监听"""
        def on_data_change(data: bytes, stat: dict):
            if data is not None:
                self.data = data

        self.client.watch_data(self.path, on_data_change)


class ZkPathChildrenCache:
    """
    ZooKeeper 路径子节点缓存

    参考 Java: CuratorZkPathChildrenCache
    监视子节点的增删，用于发现新的配置或命令
    """

    def __init__(self, client: ZkClient, path: str):
        """
        初始化子节点缓存

        Args:
            client: ZK 客户端
            path: 路径
        """
        self.client = client
        self.path = path
        self._children: List[str] = []
        self._last_children: List[str] = []
        self._is_running = False
        self._is_connected = False
        self._lock = threading.Lock()
        self._update_listener: Optional[Callable[[], None]] = None
        self._update_executor: Optional[threading.Thread] = None

    def start(self, require_rebuild: bool = True) -> bool:
        """
        启动子节点缓存

        Args:
            require_rebuild: 是否需要立即刷新

        Returns:
            bool: 启动成功返回 True
        """
        with self._lock:
            if self._is_running:
                logger.warning(f"子节点缓存已在运行：{self.path}")
                return True

            try:
                # 添加状态监听器
                self.client.add_state_listener(self._on_connection_state_change)

                # 确保路径存在
                if not self.client.ensure_path_exists(self.path):
                    logger.error(f"创建路径失败：{self.path}")
                    return False

                self._is_running = True
                self._is_connected = True

                if require_rebuild:
                    self._refresh()

                # 添加监听
                self._add_watch()

                logger.info(f"子节点缓存启动成功：{self.path}")
                return True

            except Exception as e:
                logger.error(f"子节点缓存启动失败：{self.path}, error: {e}")
                return False

    def stop(self) -> None:
        """停止子节点缓存"""
        with self._lock:
            if not self._is_running:
                return

            try:
                self._is_running = False
                self.client.remove_state_listener(self._on_connection_state_change)
                logger.info(f"子节点缓存已停止：{self.path}")

            except Exception as e:
                logger.error(f"子节点缓存停止失败：{self.path}, error: {e}")

    def get_children(self) -> List[str]:
        """获取子节点列表"""
        with self._lock:
            return self._children.copy() if self._children else []

    def get_added_children(self) -> List[str]:
        """获取新增的子节点"""
        with self._lock:
            return list(set(self._children) - set(self._last_children))

    def get_deleted_children(self) -> List[str]:
        """获取删除的子节点"""
        with self._lock:
            return list(set(self._last_children) - set(self._children))

    def set_update_listener(self, listener: Callable[[], None]) -> None:
        """设置更新监听器"""
        self._update_listener = listener

    def refresh(self) -> bool:
        """刷新子节点列表"""
        return self._refresh()

    def _refresh(self) -> bool:
        """内部刷新方法"""
        with self._lock:
            try:
                children = self.client.list_children(self.path)
                self._last_children = self._children
                self._children = children if children else []

                # 通知监听器
                if self._update_listener and self._children != self._last_children:
                    try:
                        self._update_listener()
                    except Exception as e:
                        logger.error(f"更新监听器执行失败：{e}")

                return True

            except Exception as e:
                logger.error(f"刷新子节点失败：{self.path}, error: {e}")
                return False

    def _add_watch(self) -> None:
        """添加监听"""
        def on_children_change(children: List[str]):
            if self._is_running and self._is_connected:
                self._refresh()

        self.client.watch_children(self.path, on_children_change)

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
                    self._refresh()
                    logger.info(f"子节点缓存从 RECONNECTED 事件恢复：{self.path}")
                except Exception as e:
                    logger.error(f"重连后刷新失败：{self.path}, error: {e}")
        elif state in [ConnectionState.SUSPENDED, ConnectionState.LOST]:
            self._is_connected = False
            logger.warning(f"ZK 连接中断，子节点缓存标记为未连接：{self.path}")


class ZkClientPathRegister:
    """
    ZooKeeper 客户端路径注册器

    参考 Java: ZookeeperRegister
    负责在 ZooKeeper 中注册客户端路径，并监听配置变化
    """

    def __init__(self, config: Optional[ZkConfig] = None,
                 client: Optional[ZkClient] = None):
        """
        初始化客户端路径注册器

        Args:
            config: ZK 配置
            client: ZK 客户端
        """
        self.config = config or get_config()
        self.client = client

        self._client_path_node: Optional[ZkClientPathNode] = None
        self._config_cache: Optional[ZkPathChildrenCache] = None
        self._command_cache: Optional[ZkPathChildrenCache] = None
        self._is_started = False
        self._lock = threading.Lock()

        # 客户端数据
        self._client_data = ClientNodeData()

        # 监听器
        self._config_listeners: List[Callable[[List[str]], None]] = []
        self._command_listeners: List[Callable[[List[str]], None]] = []

    def initialize(self, client: Optional[ZkClient] = None) -> bool:
        """
        初始化客户端路径注册器

        Args:
            client: ZK 客户端

        Returns:
            bool: 初始化成功返回 True
        """
        with self._lock:
            if self.client and self.client.is_connected():
                logger.warning("客户端路径注册器已初始化")
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

                # 初始化客户端数据
                self._init_client_data()

                # 获取客户端路径
                client_path = self.config.get_client_path()

                # 创建客户端路径节点
                self._client_path_node = ZkClientPathNode(
                    self.client,
                    client_path,
                    self._get_client_data()
                )

                # 创建配置缓存
                config_path = f"{client_path}/configs"
                self._config_cache = ZkPathChildrenCache(self.client, config_path)
                self._config_cache.set_update_listener(self._on_config_change)

                # 创建命令缓存
                command_path = f"{client_path}/commands"
                self._command_cache = ZkPathChildrenCache(self.client, command_path)
                self._command_cache.set_update_listener(self._on_command_change)

                logger.info(f"客户端路径注册器初始化成功：{client_path}")
                return True

            except Exception as e:
                logger.error(f"客户端路径注册器初始化失败：{e}")
                return False

    def start(self) -> bool:
        """
        启动客户端路径注册器

        Returns:
            bool: 启动成功返回 True
        """
        with self._lock:
            if self._is_started:
                logger.warning("客户端路径注册器已启动")
                return True

            if not self.client or not self._client_path_node:
                logger.error("客户端路径注册器未初始化")
                return False

            try:
                # 启动客户端路径节点
                if not self._client_path_node.start():
                    logger.error("客户端路径节点启动失败")
                    return False

                # 启动配置缓存
                if not self._config_cache.start():
                    logger.warning("配置缓存启动失败")

                # 启动命令缓存
                if not self._command_cache.start():
                    logger.warning("命令缓存启动失败")

                self._is_started = True
                logger.info("客户端路径注册器启动成功")
                return True

            except Exception as e:
                logger.error(f"客户端路径注册器启动失败：{e}")
                return False

    def stop(self) -> None:
        """停止客户端路径注册器"""
        with self._lock:
            if not self._is_started:
                return

            try:
                self._is_started = False

                # 停止命令缓存
                if self._command_cache:
                    self._command_cache.stop()

                # 停止配置缓存
                if self._config_cache:
                    self._config_cache.stop()

                # 停止客户端路径节点
                if self._client_path_node:
                    self._client_path_node.stop()

                logger.info("客户端路径注册器已停止")

            except Exception as e:
                logger.error(f"客户端路径注册器停止失败：{e}")

    def add_config_listener(self, listener: Callable[[List[str]], None]) -> None:
        """
        添加配置监听器

        Args:
            listener: 监听器函数，参数为配置列表
        """
        self._config_listeners.append(listener)
        logger.debug(f"已添加配置监听器")

    def remove_config_listener(self, listener: Callable[[List[str]], None]) -> None:
        """移除配置监听器"""
        if listener in self._config_listeners:
            self._config_listeners.remove(listener)

    def add_command_listener(self, listener: Callable[[List[str]], None]) -> None:
        """
        添加命令监听器

        Args:
            listener: 监听器函数，参数为命令列表
        """
        self._command_listeners.append(listener)
        logger.debug(f"已添加命令监听器")

    def remove_command_listener(self, listener: Callable[[List[str]], None]) -> None:
        """移除命令监听器"""
        if listener in self._command_listeners:
            self._command_listeners.remove(listener)

    def get_config_children(self) -> List[str]:
        """获取配置子节点列表"""
        if self._config_cache:
            return self._config_cache.get_children()
        return []

    def get_command_children(self) -> List[str]:
        """获取命令子节点列表"""
        if self._command_cache:
            return self._command_cache.get_children()
        return []

    def _init_client_data(self) -> None:
        """初始化客户端数据"""
        import socket
        import datetime

        # 获取本机 IP
        try:
            self._client_data.address = socket.gethostbyname(socket.gethostname())
        except Exception:
            self._client_data.address = "127.0.0.1"

        self._client_data.host = socket.gethostname()
        self._client_data.name = os.path.basename(os.getcwd())
        self._client_data.pid = str(os.getpid())
        self._client_data.agent_id = self.config.get_full_agent_id()
        self._client_data.agent_language = "PYTHON"
        self._client_data.agent_version = self.config.agent_version
        self._client_data.simulator_version = self.config.simulator_version
        self._client_data.tenant_app_key = self.config.tenant_app_key
        self._client_data.env_code = self.config.env_code
        self._client_data.user_id = self.config.user_id
        self._client_data.register_time = datetime.datetime.now().isoformat()
        self._client_data.last_heartbeat = datetime.datetime.now().isoformat()
        self._client_data.capabilities = ["config_fetch", "command_poll"]

    def _get_client_data(self) -> bytes:
        """获取客户端数据"""
        import datetime
        self._client_data.last_heartbeat = datetime.datetime.now().isoformat()
        return self._client_data.to_json()

    def _on_config_change(self) -> None:
        """配置变化回调"""
        children = self.get_config_children()
        logger.info(f"配置发生变化：{len(children)} 个配置")

        for listener in self._config_listeners:
            try:
                listener(children)
            except Exception as e:
                logger.error(f"配置监听器执行失败：{e}")

    def _on_command_change(self) -> None:
        """命令变化回调"""
        children = self.get_command_children()
        logger.info(f"命令发生变化：{len(children)} 个命令")

        for listener in self._command_listeners:
            try:
                listener(children)
            except Exception as e:
                logger.error(f"命令监听器执行失败：{e}")


# ==================== 全局管理器 ====================

_global_register: Optional[ZkClientPathRegister] = None
_register_lock = threading.Lock()


def get_client_path_register(config: Optional[ZkConfig] = None) -> Optional[ZkClientPathRegister]:
    """
    获取全局客户端路径注册器实例

    Args:
        config: ZK 配置

    Returns:
        ZkClientPathRegister 实例
    """
    global _global_register

    with _register_lock:
        if _global_register is None:
            _global_register = ZkClientPathRegister(config)
        return _global_register


def reset_client_path_register():
    """重置客户端路径注册器 (用于测试)"""
    global _global_register
    with _register_lock:
        if _global_register:
            _global_register.stop()
            _global_register = None
