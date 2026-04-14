"""
PyLinkAgent ZooKeeper 客户端

参考 Java LinkAgent 的 NetflixCuratorZkClient 和 CuratorFramework 实现
使用 kazoo 库作为 Curator 的 Python 等价物
"""

import json
import threading
import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import logging

try:
    from kazoo.client import KazooClient, KazooState
    from kazoo.exceptions import KeeperException, NoNodeError
    from kazoo.handlers.threading import SequentialThreadingHandler
    from kazoo.recipe.watchers import ChildrenWatch, DataWatch
    KAZOO_AVAILABLE = True
except ImportError:
    KAZOO_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("kazoo 库未安装，ZooKeeper 功能将不可用。请运行：pip install kazoo")

from .config import ZkConfig

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接状态"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SUSPENDED = "suspended"
    LOST = "lost"
    RECONNECTED = "reconnected"


@dataclass
class ZkNodeStat:
    """节点统计信息"""
    version: int = 0
    ephemeral_owner: int = 0
    data_len: int = 0
    ctime: int = 0
    mtime: int = 0


class ZkClient:
    """
    ZooKeeper 客户端封装

    参考 Java: NetflixCuratorZkClient
    """

    def __init__(self, config: ZkConfig):
        """
        初始化 ZK 客户端

        Args:
            config: ZK 配置
        """
        if not KAZOO_AVAILABLE:
            raise RuntimeError("kazoo 库未安装，请运行：pip install kazoo")

        self.config = config
        self._client: Optional[KazooClient] = None
        self._connected = False
        self._state = ConnectionState.DISCONNECTED
        self._lock = threading.Lock()
        self._state_listeners: List[Callable[[ConnectionState], None]] = []
        self._data_watches: Dict[str, DataWatch] = {}
        self._children_watches: Dict[str, ChildrenWatch] = {}

    def connect(self) -> bool:
        """
        连接到 ZooKeeper

        Returns:
            bool: 连接成功返回 True
        """
        if self._connected:
            logger.debug("ZK 已连接")
            return True

        with self._lock:
            if self._connected:
                return True

            try:
                # 创建 KazooClient
                self._client = KazooClient(
                    hosts=self.config.zk_servers,
                    connection_timeout=self.config.connection_timeout_ms / 1000.0,
                    timeout=self.config.session_timeout_ms / 1000.0,
                    handler=SequentialThreadingHandler(),
                    read_only=False,
                )

                # 添加状态监听器
                self._client.add_listener(self._connection_listener)

                # 启动连接
                self._client.start()

                # 等待连接
                if not self._client.connected.wait(timeout=self.config.connection_timeout_ms / 1000.0):
                    logger.error("ZK 连接超时")
                    return False

                self._connected = True
                self._state = ConnectionState.CONNECTED
                logger.info(f"ZK 连接成功：{self.config.zk_servers}")
                return True

            except Exception as e:
                logger.error(f"ZK 连接失败：{e}")
                self._connected = False
                self._state = ConnectionState.DISCONNECTED
                return False

    def disconnect(self) -> None:
        """断开连接"""
        with self._lock:
            if self._client:
                try:
                    self._client.remove_listener(self._connection_listener)
                    self._client.stop()
                    self._client.close()
                except Exception as e:
                    logger.warning(f"断开 ZK 连接时出错：{e}")
                finally:
                    self._client = None
                    self._connected = False
                    self._state = ConnectionState.DISCONNECTED
                    logger.info("ZK 已断开连接")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self._client and self._client.connected.is_set()

    def get_state(self) -> ConnectionState:
        """获取当前连接状态"""
        return self._state

    def _connection_listener(self, state: KazooState) -> None:
        """连接状态监听器"""
        if state == KazooState.SUSPENDED:
            self._state = ConnectionState.SUSPENDED
            logger.warning("ZK 连接已暂停")
        elif state == KazooState.LOST:
            self._state = ConnectionState.LOST
            logger.warning("ZK 连接已丢失")
        elif state == KazooState.CONNECTED or state == KazooState.CONNECTED_READONLY:
            if self._state == ConnectionState.SUSPENDED or self._state == ConnectionState.LOST:
                self._state = ConnectionState.RECONNECTED
                logger.info("ZK 已重连")
            else:
                self._state = ConnectionState.CONNECTED
                self._connected = True
                logger.info("ZK 已连接")

        # 通知状态监听器
        for listener in self._state_listeners:
            try:
                listener(self._state)
            except Exception as e:
                logger.error(f"状态监听器出错：{e}")

    def add_state_listener(self, listener: Callable[[ConnectionState], None]) -> None:
        """添加状态监听器"""
        self._state_listeners.append(listener)

    def remove_state_listener(self, listener: Callable[[ConnectionState], None]) -> None:
        """移除状态监听器"""
        if listener in self._state_listeners:
            self._state_listeners.remove(listener)

    # ==================== 节点操作 ====================

    def exists(self, path: str) -> bool:
        """检查节点是否存在"""
        if not self.is_connected():
            return False
        try:
            return self._client.exists(path) is not None
        except Exception:
            return False

    def create(self, path: str, data: bytes = b'', ephemeral: bool = False,
               make_parent_dirs: bool = True) -> bool:
        """
        创建节点

        Args:
            path: 节点路径
            data: 节点数据
            ephemeral: 是否临时节点
            make_parent_dirs: 是否自动创建父目录

        Returns:
            bool: 创建成功返回 True
        """
        if not self.is_connected():
            logger.warning(f"ZK 未连接，无法创建节点：{path}")
            return False

        try:
            create_func = self._client.Ephemeral if ephemeral else self._client.create
            self._client.create(path, data, ephemeral=ephemeral, makepath=make_parent_dirs)
            logger.info(f"ZK 节点创建成功：{path}")
            return True
        except KeeperException.NodeExistsError:
            logger.debug(f"节点已存在：{path}")
            return True  # 节点已存在也算成功
        except Exception as e:
            logger.error(f"创建 ZK 节点失败：{path}, error: {e}")
            return False

    def delete(self, path: str, recursive: bool = False) -> bool:
        """
        删除节点

        Args:
            path: 节点路径
            recursive: 是否递归删除子节点

        Returns:
            bool: 删除成功返回 True
        """
        if not self.is_connected():
            return False

        try:
            self._client.delete(path, recursive=recursive)
            logger.info(f"ZK 节点删除成功：{path}")
            return True
        except NoNodeError:
            logger.debug(f"节点不存在：{path}")
            return True
        except Exception as e:
            logger.error(f"删除 ZK 节点失败：{path}, error: {e}")
            return False

    def get(self, path: str) -> Optional[bytes]:
        """获取节点数据"""
        if not self.is_connected():
            return None

        try:
            data, stat = self._client.get(path)
            return data
        except NoNodeError:
            logger.debug(f"节点不存在：{path}")
            return None
        except Exception as e:
            logger.error(f"获取 ZK 节点数据失败：{path}, error: {e}")
            return None

    def get_json(self, path: str) -> Optional[Dict[str, Any]]:
        """获取节点数据并解析为 JSON"""
        data = self.get(path)
        if data:
            try:
                return json.loads(data.decode('utf-8'))
            except Exception as e:
                logger.error(f"解析 JSON 失败：{e}")
                return None
        return None

    def set(self, path: str, data: bytes) -> bool:
        """
        设置节点数据

        Args:
            path: 节点路径
            data: 数据

        Returns:
            bool: 设置成功返回 True
        """
        if not self.is_connected():
            return False

        try:
            self._client.set(path, data)
            logger.debug(f"ZK 节点数据更新成功：{path}")
            return True
        except NoNodeError:
            logger.warning(f"节点不存在，尝试创建：{path}")
            return self.create(path, data, ephemeral=False)
        except Exception as e:
            logger.error(f"设置 ZK 节点数据失败：{path}, error: {e}")
            return False

    def set_json(self, path: str, data: Dict[str, Any]) -> bool:
        """设置节点数据为 JSON"""
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        return self.set(path, json_data)

    def get_stat(self, path: str) -> Optional[ZkNodeStat]:
        """获取节点统计信息"""
        if not self.is_connected():
            return None

        try:
            stat = self._client.exists(path)
            if stat:
                return ZkNodeStat(
                    version=stat.version,
                    ephemeral_owner=stat.ephemeral_owner,
                    data_len=stat.data_len,
                    ctime=stat.ctime,
                    mtime=stat.mtime,
                )
            return None
        except Exception as e:
            logger.error(f"获取节点统计信息失败：{path}, error: {e}")
            return None

    def list_children(self, path: str) -> Optional[List[str]]:
        """获取子节点列表"""
        if not self.is_connected():
            return None

        try:
            return self._client.get_children(path)
        except NoNodeError:
            return None
        except Exception as e:
            logger.error(f"获取子节点列表失败：{path}, error: {e}")
            return None

    def ensure_path_exists(self, path: str) -> bool:
        """
        确保路径存在，不存在则创建

        Args:
            path: 路径

        Returns:
            bool: 成功返回 True
        """
        if not self.is_connected():
            return False

        try:
            if not self.exists(path):
                self.create(path, make_parent_dirs=True)
            return True
        except Exception as e:
            logger.error(f"确保路径存在失败：{path}, error: {e}")
            return False

    # ==================== Watch 监听 ====================

    def watch_data(self, path: str, callback: Callable[[bytes, dict], None]) -> bool:
        """
        监听节点数据变化

        Args:
            path: 节点路径
            callback: 回调函数 (data, stat_dict)

        Returns:
            bool: 成功返回 True
        """
        if not self.is_connected():
            return False

        try:
            @DataWatch(path)
            def watcher(data: bytes, stat: dict):
                try:
                    callback(data, stat)
                except Exception as e:
                    logger.error(f"DataWatch 回调出错：{e}")

            self._data_watches[path] = watcher
            logger.debug(f"已添加 DataWatch: {path}")
            return True
        except Exception as e:
            logger.error(f"添加 DataWatch 失败：{path}, error: {e}")
            return False

    def watch_children(self, path: str, callback: Callable[[List[str]], None]) -> bool:
        """
        监听子节点变化

        Args:
            path: 节点路径
            callback: 回调函数 (children_list)

        Returns:
            bool: 成功返回 True
        """
        if not self.is_connected():
            return False

        try:
            @ChildrenWatch(path)
            def watcher(children: List[str]):
                try:
                    callback(children)
                except Exception as e:
                    logger.error(f"ChildrenWatch 回调出错：{e}")

            self._children_watches[path] = watcher
            logger.debug(f"已添加 ChildrenWatch: {path}")
            return True
        except Exception as e:
            logger.error(f"添加 ChildrenWatch 失败：{path}, error: {e}")
            return False

    def remove_watch(self, path: str) -> None:
        """移除监听器"""
        if path in self._data_watches:
            # DataWatch 无法直接移除，需要重新实现
            del self._data_watches[path]
        if path in self._children_watches:
            del self._children_watches[path]
        logger.debug(f"已移除 Watch: {path}")


# ==================== 工厂类 ====================

class ZkClientFactory:
    """ZK 客户端工厂"""

    _clients: Dict[str, ZkClient] = {}
    _lock = threading.Lock()

    @classmethod
    def get_client(cls, config: ZkConfig) -> ZkClient:
        """
        获取或创建 ZK 客户端

        Args:
            config: ZK 配置

        Returns:
            ZkClient 实例
        """
        key = config.zk_servers

        with cls._lock:
            if key not in cls._clients:
                cls._clients[key] = ZkClient(config)
            return cls._clients[key]

    @classmethod
    def remove_client(cls, config: ZkConfig) -> None:
        """移除客户端"""
        key = config.zk_servers
        with cls._lock:
            if key in cls._clients:
                client = cls._clients.pop(key)
                try:
                    client.disconnect()
                except Exception:
                    pass


# ==================== 快捷方法 ====================

def create_client(config: Optional[ZkConfig] = None) -> ZkClient:
    """
    创建 ZK 客户端

    Args:
        config: ZK 配置

    Returns:
        ZkClient 实例
    """
    from .config import get_config
    if config is None:
        config = get_config()
    return ZkClientFactory.get_client(config)
