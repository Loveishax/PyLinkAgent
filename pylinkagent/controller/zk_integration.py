"""
ZooKeeper 集成模块

将 ZooKeeper 心跳功能集成到 PyLinkAgent 主流程中
实现双心跳机制 (HTTP + ZK) 以匹配 Java LinkAgent 行为
"""

import threading
import logging
from typing import Optional, Callable
import os

from ..zookeeper import (
    ZkConfig,
    ZkClient,
    ZkHeartbeatManager,
    AgentStatus,
    get_config,
    create_client,
    get_heartbeat_manager,
    reset_heartbeat_manager,
)

logger = logging.getLogger(__name__)


class ZKIntegration:
    """
    ZooKeeper 集成管理器

    负责管理 ZK 连接和心跳的生命周期
    """

    def __init__(self, config: Optional[ZkConfig] = None):
        """
        初始化 ZK 集成

        Args:
            config: ZK 配置，为 None 时使用默认配置
        """
        self.config = config or get_config()
        self._client: Optional[ZkClient] = None
        self._heartbeat_manager: Optional[ZkHeartbeatManager] = None
        self._is_initialized = False
        self._is_running = False
        self._lock = threading.Lock()

        # 状态变更回调
        self._status_callbacks: list = []

    def initialize(self, client: Optional[ZkClient] = None) -> bool:
        """
        初始化 ZK 集成

        Args:
            client: 可选的 ZK 客户端，为 None 时自动创建

        Returns:
            bool: 初始化成功返回 True
        """
        with self._lock:
            if self._is_initialized:
                logger.warning("ZK 集成已初始化")
                return True

            try:
                logger.info(f"开始初始化 ZK 集成：{self.config.zk_servers}")

                # 创建或获取 ZK 客户端
                if client is None:
                    self._client = create_client(self.config)
                else:
                    self._client = client

                # 连接 ZK
                if not self._client.connect():
                    logger.error("ZK 连接失败")
                    return False

                # 初始化心跳管理器
                self._heartbeat_manager = get_heartbeat_manager(self.config)
                if not self._heartbeat_manager.initialize(self._client):
                    logger.error("心跳管理器初始化失败")
                    return False

                self._is_initialized = True
                logger.info(f"ZK 集成初始化成功：{self.config.zk_servers}")
                return True

            except Exception as e:
                logger.error(f"ZK 集成初始化失败：{e}")
                return False

    def start(self) -> bool:
        """
        启动 ZK 心跳

        Returns:
            bool: 启动成功返回 True
        """
        with self._lock:
            if not self._is_initialized:
                logger.error("ZK 集成未初始化")
                return False

            if self._is_running:
                logger.warning("ZK 心跳已启动")
                return True

            try:
                # 启动心跳管理器
                if self._heartbeat_manager and self._heartbeat_manager.start():
                    self._is_running = True
                    logger.info("ZK 心跳启动成功")
                    return True
                else:
                    logger.error("ZK 心跳启动失败")
                    return False

            except Exception as e:
                logger.error(f"ZK 心跳启动失败：{e}")
                return False

    def stop(self) -> None:
        """停止 ZK 心跳"""
        with self._lock:
            if not self._is_running:
                return

            try:
                self._is_running = False

                # 停止心跳管理器
                if self._heartbeat_manager:
                    self._heartbeat_manager.stop()

                logger.info("ZK 心跳已停止")

            except Exception as e:
                logger.error(f"ZK 心跳停止失败：{e}")

    def shutdown(self) -> None:
        """完全关闭 ZK 集成"""
        self.stop()

        with self._lock:
            try:
                # 断开客户端连接
                if self._client:
                    self._client.disconnect()

                # 重置全局管理器
                reset_heartbeat_manager()

                self._is_initialized = False
                logger.info("ZK 集成已关闭")

            except Exception as e:
                logger.error(f"ZK 集成关闭失败：{e}")

    def update_status(self, status: AgentStatus, error_msg: str = "") -> None:
        """
        更新 Agent 状态

        Args:
            status: Agent 状态
            error_msg: 错误信息
        """
        if not self._is_running or not self._heartbeat_manager:
            logger.warning("ZK 心跳未运行，无法更新状态")
            return

        self._heartbeat_manager.update_status(status, error_msg)
        logger.info(f"ZK Agent 状态已更新：{status.value}")

    def set_simulator_info(self, service: str, port: int, md5: str = "",
                          jars: list = None) -> None:
        """
        设置 Simulator 信息并刷新心跳

        Args:
            service: 服务地址
            port: 端口
            md5: 模块 MD5
            jars: JAR 列表
        """
        if not self._heartbeat_manager:
            logger.warning("心跳管理器未初始化")
            return

        self._heartbeat_manager.set_simulator_info(service, port, md5, jars)
        self._heartbeat_manager.refresh()
        logger.info(f"Simulator 信息已设置：service={service}, port={port}")

    def add_status_callback(self, callback: Callable[[str], None]) -> None:
        """添加状态变更回调"""
        if self._heartbeat_manager:
            self._heartbeat_manager.add_status_listener(callback)

    def is_running(self) -> bool:
        """检查 ZK 心跳是否运行"""
        return self._is_running

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._is_initialized


# ==================== 全局集成实例 ====================

_global_integration: Optional[ZKIntegration] = None
_integration_lock = threading.Lock()


def get_integration(config: Optional[ZkConfig] = None) -> Optional[ZKIntegration]:
    """
    获取全局 ZK 集成实例

    Args:
        config: ZK 配置

    Returns:
        ZKIntegration 实例
    """
    global _global_integration

    with _integration_lock:
        if _global_integration is None:
            _global_integration = ZKIntegration(config)
        return _global_integration


def reset_integration():
    """重置全局集成实例 (用于测试)"""
    global _global_integration
    with _integration_lock:
        if _global_integration:
            _global_integration.shutdown()
            _global_integration = None


def initialize_zk() -> bool:
    """
    初始化并启动 ZK 集成

    从环境变量读取配置，如果 ZK 不可用则优雅降级

    Returns:
        bool: 初始化成功返回 True
    """
    # 检查是否启用 ZK
    register_name = os.getenv("REGISTER_NAME", "zookeeper")
    zk_enabled = os.getenv("ZK_ENABLED", "true").lower() == "true"

    if register_name.lower() != "zookeeper" or not zk_enabled:
        logger.info(f"ZK 集成已禁用：REGISTER_NAME={register_name}, ZK_ENABLED={zk_enabled}")
        return False

    try:
        integration = get_integration()
        if integration.initialize():
            if integration.start():
                logger.info("ZK 集成启动成功")
                return True
            else:
                logger.warning("ZK 集成启动失败")
                return False
        else:
            logger.warning("ZK 集成初始化失败")
            return False

    except Exception as e:
        logger.warning(f"ZK 集成失败，降级到 HTTP-only 模式：{e}")
        return False


def shutdown_zk() -> None:
    """关闭 ZK 集成"""
    try:
        integration = get_integration()
        if integration:
            integration.shutdown()
            reset_integration()
            logger.info("ZK 集成已关闭")
    except Exception as e:
        logger.error(f"关闭 ZK 集成失败：{e}")
