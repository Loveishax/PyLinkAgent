"""
PyLinkAgent ZooKeeper 心跳节点管理

参考 Java LinkAgent 的 CuratorZkHeartbeatNode 和 ZookeeperRegister 实现
"""

import json
import threading
import platform
import time
import socket
import os
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum
import logging

from .zk_client import ZkClient, ConnectionState, ZkNodeStat
from .config import ZkConfig, get_config

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent 状态枚举"""
    UNKNOWN = "UNKNOWN"  # 未知
    BEGIN = "BEGIN"  # 启动中
    STARTING = "STARTING"  # 升级待重启
    RUNNING = "RUNNING"  # 运行中
    ERROR = "ERROR"  # 异常
    SLEEP = "SLEEP"  # 休眠
    UNINSTALL = "UNINSTALL"  # 卸载
    INSTALL_FAILED = "INSTALL_FAILED"  # 安装失败


@dataclass
class HeartbeatData:
    """心跳数据结构"""
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

    # 状态信息
    agent_status: str = AgentStatus.RUNNING.value
    error_code: str = ""
    error_msg: str = ""

    # 环境信息
    jvm_args: str = ""
    jdk_version: str = ""
    jvm_args_check: str = "PASS"

    # 租户信息
    tenant_app_key: str = ""
    env_code: str = "test"
    user_id: str = ""

    # Simulator 信息
    service: str = ""
    port: str = ""

    # 其他信息
    md5: str = ""
    jars: List[str] = field(default_factory=list)
    simulator_file_configs: Dict[str, Any] = field(default_factory=dict)
    agent_file_configs: Dict[str, Any] = field(default_factory=dict)

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
            "agentStatus": self.agent_status,
            "errorCode": self.error_code,
            "errorMsg": self.error_msg,
            "jvmArgs": self.jvm_args,
            "jdkVersion": self.jdk_version,
            "jvmArgsCheck": self.jvm_args_check,
            "tenantAppKey": self.tenant_app_key,
            "envCode": self.env_code,
            "userId": self.user_id,
            "service": self.service,
            "port": self.port,
            "md5": self.md5,
            "jars": self.jars,
            "simulatorFileConfigs": self.simulator_file_configs,
            "agentFileConfigs": self.agent_file_configs,
        }

    def to_json(self) -> bytes:
        """转换为 JSON 字节"""
        return json.dumps(self.to_dict(), ensure_ascii=False).encode('utf-8')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HeartbeatData":
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
            agent_status=data.get("agentStatus", AgentStatus.RUNNING.value),
            error_code=data.get("errorCode", ""),
            error_msg=data.get("errorMsg", ""),
            jvm_args=data.get("jvmArgs", ""),
            jdk_version=data.get("jdkVersion", ""),
            jvm_args_check=data.get("jvmArgsCheck", "PASS"),
            tenant_app_key=data.get("tenantAppKey", ""),
            env_code=data.get("envCode", "test"),
            user_id=data.get("userId", ""),
            service=data.get("service", ""),
            port=data.get("port", ""),
            md5=data.get("md5", ""),
            jars=data.get("jars", []),
            simulator_file_configs=data.get("simulatorFileConfigs", {}),
            agent_file_configs=data.get("agentFileConfigs", {}),
        )


class ZkHeartbeatNode:
    """
    ZooKeeper 心跳节点

    参考 Java: CuratorZkHeartbeatNode
    """

    def __init__(self, client: ZkClient, path: str, data: bytes = b''):
        """
        初始化心跳节点

        Args:
            client: ZK 客户端
            path: 节点路径
            data: 初始数据
        """
        self.client = client
        self.path = path
        self.data = data
        self._is_running = False
        self._is_alive = False
        self._is_connected = False
        self._lock = threading.Lock()
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> bool:
        """
        启动心跳节点

        Returns:
            bool: 启动成功返回 True
        """
        with self._lock:
            if self._is_running:
                logger.warning(f"心跳节点已在运行：{self.path}")
                return True

            try:
                # 添加状态监听器
                self.client.add_state_listener(self._on_connection_state_change)

                # 检查节点是否存在，存在则删除
                if self.client.exists(self.path):
                    self.client.delete(self.path)
                    logger.debug(f"已删除旧节点：{self.path}")

                # 创建临时节点
                self.client.create(self.path, self.data, ephemeral=True)
                logger.info(f"心跳节点创建成功：{self.path}")

                # 重置状态
                self._is_running = True
                self._is_alive = True
                self._is_connected = True

                # 添加节点删除监听
                self._add_node_watch()

                logger.info(f"心跳节点启动成功：{self.path}")
                return True

            except Exception as e:
                logger.error(f"心跳节点启动失败：{self.path}, error: {e}")
                self._is_running = False
                self._is_alive = False
                return False

    def stop(self) -> None:
        """停止心跳节点"""
        with self._lock:
            if not self._is_running:
                return

            try:
                self._is_running = False
                self._is_alive = False

                # 移除状态监听器
                self.client.remove_state_listener(self._on_connection_state_change)

                # 删除节点
                self.client.delete(self.path)
                logger.info(f"心跳节点已删除：{self.path}")

            except Exception as e:
                logger.error(f"心跳节点停止失败：{self.path}, error: {e}")

    def set_data(self, data: bytes) -> bool:
        """
        设置节点数据

        Args:
            data: 数据

        Returns:
            bool: 设置成功返回 True
        """
        with self._lock:
            if not self._is_running or not self._is_alive:
                logger.warning(f"心跳节点未运行，无法设置数据：{self.path}")
                return False

            try:
                self.data = data
                self.client.set(self.path, data)
                logger.debug(f"心跳数据已更新：{self.path}")
                return True
            except Exception as e:
                logger.error(f"设置心跳数据失败：{self.path}, error: {e}")
                return False

    def get_data(self) -> bytes:
        """获取节点数据"""
        return self.data

    def is_alive(self) -> bool:
        """检查节点是否存活"""
        return self._is_alive

    def is_running(self) -> bool:
        """检查节点是否运行"""
        return self._is_running

    def _reset(self) -> None:
        """重置节点"""
        with self._lock:
            if not self._is_running or not self._is_connected:
                return

            try:
                # 检查节点是否存在
                if self.client.exists(self.path):
                    # 节点存在，更新数据
                    self.client.set(self.path, self.data)
                    logger.debug(f"心跳节点数据已更新：{self.path}")
                else:
                    # 节点不存在，重新创建
                    self.client.create(self.path, self.data, ephemeral=True)
                    logger.info(f"心跳节点重新创建：{self.path}")

                self._is_alive = True
                self._add_node_watch()

            except Exception as e:
                logger.error(f"重置心跳节点失败：{self.path}, error: {e}")
                self._is_alive = False

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
                    logger.info(f"心跳节点从 RECONNECTED 事件恢复：{self.path}")
                except Exception as e:
                    logger.error(f"重连后重置失败：{self.path}, error: {e}")
        elif state in [ConnectionState.SUSPENDED, ConnectionState.LOST]:
            self._is_connected = False
            self._is_alive = False
            logger.warning(f"ZK 连接中断，心跳节点标记为不存活：{self.path}")

    def _add_node_watch(self) -> None:
        """添加节点删除监听"""
        def on_node_deleted(children: List[str]):
            # 如果节点被删除（非正常停止），重新创建
            if self._is_running and self._is_connected:
                logger.warning(f"心跳节点被删除，尝试重新创建：{self.path}")
                self._reset()

        self.client.watch_children(os.path.dirname(self.path), lambda c: None)  # 监听父节点

        # 使用 DataWatch 监听节点本身
        def on_data_change(data: bytes, stat: dict):
            if data is None:
                # 节点被删除
                if self._is_running and self._is_connected:
                    logger.warning(f"心跳节点被删除，尝试重新创建：{self.path}")
                    self._reset()
            else:
                # 数据变化
                self.data = data

        self.client.watch_data(self.path, on_data_change)


class ZkHeartbeatManager:
    """
    ZooKeeper 心跳管理器

    参考 Java: ZookeeperRegister
    """

    def __init__(self, config: Optional[ZkConfig] = None,
                 client: Optional[ZkClient] = None):
        """
        初始化心跳管理器

        Args:
            config: ZK 配置
            client: ZK 客户端
        """
        self.config = config or get_config()
        self.client = client

        self._heartbeat_node: Optional[ZkHeartbeatNode] = None
        self._is_started = False
        self._lock = threading.Lock()

        # 心跳数据
        self._heartbeat_data = HeartbeatData()

        # 定时刷新线程
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 状态监听器
        self._status_listeners: List[Callable[[str], None]] = []

    def initialize(self, client: Optional[ZkClient] = None) -> bool:
        """
        初始化心跳管理器

        Args:
            client: ZK 客户端

        Returns:
            bool: 初始化成功返回 True
        """
        with self._lock:
            if self._is_started:
                logger.warning("心跳管理器已初始化")
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

                # 确保父路径存在
                status_path = self.config.get_status_path()
                parent_path = os.path.dirname(status_path)
                if not self.client.ensure_path_exists(parent_path):
                    logger.error(f"创建父路径失败：{parent_path}")
                    return False

                # 清理过期节点
                self._clean_expired_nodes(parent_path)

                # 创建心跳节点
                self._heartbeat_node = ZkHeartbeatNode(
                    self.client,
                    status_path,
                    self._get_heartbeat_data()
                )

                logger.info(f"心跳管理器初始化成功：{status_path}")
                return True

            except Exception as e:
                logger.error(f"心跳管理器初始化失败：{e}")
                return False

    def start(self) -> bool:
        """
        启动心跳管理器

        Returns:
            bool: 启动成功返回 True
        """
        with self._lock:
            if self._is_started:
                logger.warning("心跳管理器已启动")
                return True

            if not self._heartbeat_node:
                logger.error("心跳管理器未初始化")
                return False

            try:
                # 启动心跳节点
                if self._heartbeat_node.start():
                    self._is_started = True

                    # 启动定时刷新线程
                    self._start_refresh_thread()

                    logger.info("心跳管理器启动成功")
                    return True
                else:
                    return False

            except Exception as e:
                logger.error(f"心跳管理器启动失败：{e}")
                return False

    def stop(self) -> None:
        """停止心跳管理器"""
        with self._lock:
            if not self._is_started:
                return

            try:
                self._is_started = False

                # 停止刷新线程
                self._stop_event.set()
                if self._refresh_thread and self._refresh_thread.is_alive():
                    self._refresh_thread.join(timeout=5)

                # 停止心跳节点
                if self._heartbeat_node:
                    self._heartbeat_node.stop()

                logger.info("心跳管理器已停止")

            except Exception as e:
                logger.error(f"心跳管理器停止失败：{e}")

    def refresh(self) -> bool:
        """
        刷新心跳数据

        Returns:
            bool: 刷新成功返回 True
        """
        if not self._is_started or not self._heartbeat_node:
            return False

        try:
            data = self._get_heartbeat_data()
            return self._heartbeat_node.set_data(data)
        except Exception as e:
            logger.error(f"刷新心跳数据失败：{e}")
            return False

    def update_status(self, status: AgentStatus, error_msg: str = "") -> None:
        """
        更新 Agent 状态

        Args:
            status: Agent 状态
            error_msg: 错误信息
        """
        self._heartbeat_data.agent_status = status.value
        if error_msg:
            self._heartbeat_data.error_msg = error_msg

        # 立即刷新
        self.refresh()

        # 通知监听器
        for listener in self._status_listeners:
            try:
                listener(status.value)
            except Exception as e:
                logger.error(f"状态监听器通知失败：{e}")

    def add_status_listener(self, listener: Callable[[str], None]) -> None:
        """添加状态监听器"""
        self._status_listeners.append(listener)

    def remove_status_listener(self, listener: Callable[[str], None]) -> None:
        """移除状态监听器"""
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)

    def set_simulator_info(self, service: str, port: int, md5: str = "",
                           jars: List[str] = None) -> None:
        """
        设置 Simulator 信息

        Args:
            service: 服务地址
            port: 端口
            md5: 模块 MD5
            jars: JAR 列表
        """
        self._heartbeat_data.service = service
        self._heartbeat_data.port = str(port)
        if md5:
            self._heartbeat_data.md5 = md5
        if jars:
            self._heartbeat_data.jars = jars

    def _get_heartbeat_data(self) -> bytes:
        """获取心跳数据"""
        # 从配置填充数据
        self._heartbeat_data.address = socket.gethostbyname(
            socket.gethostname()) if socket.gethostname() else "127.0.0.1"
        self._heartbeat_data.host = socket.gethostname()
        self._heartbeat_data.name = os.path.basename(os.getcwd())
        self._heartbeat_data.pid = str(os.getpid())
        self._heartbeat_data.agent_id = self.config.get_full_agent_id()
        self._heartbeat_data.agent_language = "PYTHON"
        self._heartbeat_data.agent_version = self.config.agent_version
        self._heartbeat_data.simulator_version = self.config.simulator_version

        # 【修复1】Python 版本获取方式
        self._heartbeat_data.jdk_version = f"Python {platform.python_version()}"

        self._heartbeat_data.tenant_app_key = self.config.tenant_app_key
        self._heartbeat_data.env_code = self.config.env_code
        self._heartbeat_data.user_id = self.config.user_id
        self._heartbeat_data.agent_file_configs = self.config.agent_file_configs

        return self._heartbeat_data.to_json()

    def _clean_expired_nodes(self, path: str) -> None:
        """
        清理过期节点
        """
        try:
            children = self.client.list_children(path)
            if not children:
                return

            for child in children:
                child_path = f"{path}/{child}"
                stat = self.client.get_stat(child_path)
                if stat:
                    # 【修复2】Kazoo 的 ZnodeStat 属性是驼峰命名
                    if getattr(stat, 'ephemeralOwner', 0) == 0:  # 永久节点才清理
                        self.client.delete(child_path)
                        logger.info(f"清理过期节点：{child_path}")
        except Exception as e:
            logger.error(f"清理过期节点失败：{e}")

    def _start_refresh_thread(self) -> None:
        """启动定时刷新线程"""
        def refresh_loop():
            while not self._stop_event.is_set():
                try:
                    # 等待一段时间
                    self._stop_event.wait(timeout=30)  # 30 秒刷新一次
                    if not self._stop_event.is_set():
                        self.refresh()
                except Exception as e:
                    logger.error(f"刷新线程异常：{e}")

        self._refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        self._refresh_thread.start()


# ==================== 全局管理器 ====================

_global_manager: Optional[ZkHeartbeatManager] = None
_manager_lock = threading.Lock()


def get_heartbeat_manager(config: Optional[ZkConfig] = None) -> Optional[ZkHeartbeatManager]:
    """
    获取全局心跳管理器实例

    Args:
        config: ZK 配置

    Returns:
        ZkHeartbeatManager 实例
    """
    global _global_manager

    with _manager_lock:
        if _global_manager is None:
            _global_manager = ZkHeartbeatManager(config)
        return _global_manager


def reset_heartbeat_manager():
    """重置心跳管理器 (用于测试)"""
    global _global_manager
    with _manager_lock:
        if _global_manager:
            _global_manager.stop()
            _global_manager = None
