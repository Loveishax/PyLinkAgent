"""
HeartbeatReporter - PyLinkAgent 心跳上报

参考 Java LinkAgent 的 HeartRequest 机制，定期向控制台上报 Agent 状态。

核心功能:
- 定时心跳上报 (默认 30 秒)
- Agent 状态收集
- 错误信息记录
- 命令结果聚合上报
"""

import logging
import time
import socket
import os
import threading
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from .external_api import ExternalAPI, HeartRequest, CommandPacket


logger = logging.getLogger(__name__)


@dataclass
class AgentStatus:
    """
    Agent 状态数据

    对应 Java 的 HeartRequest 中的状态字段
    """
    agent_status: str = "running"
    agent_error_info: str = ""
    simulator_status: str = "running"
    simulator_error_info: str = ""
    uninstall_status: int = 0
    dormant_status: int = 0
    agent_version: str = "1.0.0"
    simulator_version: str = "1.0.0"
    dependency_info: str = ""
    task_exceed: bool = False


class HeartbeatReporter:
    """
    心跳上报器 - 定期向控制台发送心跳

    参考 Java LinkAgent 的心跳机制实现
    """

    DEFAULT_INTERVAL = 30  # 默认心跳间隔 (秒)
    DEFAULT_TIMEOUT = 10   # 默认超时时间 (秒)

    def __init__(
        self,
        external_api: ExternalAPI,
        interval: int = DEFAULT_INTERVAL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        初始化心跳上报器

        Args:
            external_api: ExternalAPI 实例
            interval: 心跳间隔 (秒)，默认 30 秒
            timeout: HTTP 超时时间 (秒)
        """
        self.external_api = external_api
        self.interval = interval
        self.timeout = timeout

        self._status = AgentStatus()
        self._command_results: List[Dict[str, Any]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._executor: Optional[ThreadPoolExecutor] = None

    def start(self) -> bool:
        """
        启动心跳上报

        Returns:
            bool: 启动成功返回 True
        """
        if self._running:
            logger.warning("心跳上报已在运行")
            return True

        if not self.external_api.is_initialized():
            logger.warning("ExternalAPI 未初始化，无法启动心跳上报")
            return False

        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="heartbeat")
        self._thread = self._executor.submit(self._heartbeat_loop).result()

        logger.info(f"心跳上报已启动：interval={self.interval}s")
        return True

    def stop(self) -> None:
        """停止心跳上报"""
        self._running = False

        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

        logger.info("心跳上报已停止")

    def is_running(self) -> bool:
        """检查心跳上报是否运行中"""
        return self._running

    def update_status(self, **kwargs) -> None:
        """
        更新 Agent 状态

        Args:
            **kwargs: 状态字段键值对
        """
        for key, value in kwargs.items():
            if hasattr(self._status, key):
                setattr(self._status, key, value)

        logger.debug(f"Agent 状态更新：{kwargs}")

    def set_agent_error(self, error_info: str) -> None:
        """设置 Agent 错误信息"""
        self._status.agent_status = "error"
        self._status.agent_error_info = error_info
        logger.warning(f"Agent 错误：{error_info}")

    def set_simulator_error(self, error_info: str) -> None:
        """设置 Simulator 错误信息"""
        self._status.simulator_status = "error"
        self._status.simulator_error_info = error_info
        logger.warning(f"Simulator 错误：{error_info}")

    def add_command_result(
        self,
        command_id: int,
        is_success: bool,
        error_msg: str = ""
    ) -> None:
        """
        添加命令执行结果到待上报列表

        Args:
            command_id: 命令 ID
            is_success: 是否成功
            error_msg: 错误信息
        """
        result = {
            "commandId": command_id,
            "success": is_success,
            "errorMsg": error_msg,
        }
        self._command_results.append(result)
        logger.debug(f"添加命令结果：commandId={command_id}, success={is_success}")

    def send_heartbeat_now(self) -> List[CommandPacket]:
        """
        立即发送一次心跳

        Returns:
            List[CommandPacket]: 控制台返回的命令列表
        """
        if not self.external_api.is_initialized():
            logger.warning("ExternalAPI 未初始化")
            return []

        try:
            # 构建心跳请求
            heart_request = self._build_heart_request()

            # 发送心跳
            commands = self.external_api.send_heartbeat(heart_request)

            # 清空已上报的命令结果
            self._command_results.clear()

            logger.debug(f"心跳发送成功：返回 {len(commands)} 个命令")
            return commands

        except Exception as e:
            logger.error(f"发送心跳失败：{e}")
            return []

    def _build_heart_request(self) -> HeartRequest:
        """构建心跳请求"""
        # 获取本机 IP
        ip_address = self._get_local_ip()

        # 获取进程 ID
        progress_id = str(os.getpid())

        # 构建依赖信息
        dependency_info = self._build_dependency_info()

        return HeartRequest(
            project_name=self.external_api.app_name,
            agent_id=self.external_api.agent_id,
            ip_address=ip_address,
            progress_id=progress_id,
            agent_status=self._status.agent_status,
            agent_error_info=self._status.agent_error_info,
            simulator_status=self._status.simulator_status,
            simulator_error_info=self._status.simulator_error_info,
            uninstall_status=self._status.uninstall_status,
            dormant_status=self._status.dormant_status,
            agent_version=self._status.agent_version,
            simulator_version=self._status.simulator_version,
            dependency_info=dependency_info,
            task_exceed=self._status.task_exceed,
            command_result=self._command_results.copy(),
        )

    def _get_local_ip(self) -> str:
        """获取本机 IP 地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _build_dependency_info(self) -> str:
        """构建依赖信息字符串"""
        # 从状态中获取依赖信息
        if self._status.dependency_info:
            return self._status.dependency_info

        # 默认返回版本信息
        return f"pylinkagent={self._status.agent_version}"

    def _heartbeat_loop(self) -> None:
        """心跳循环"""
        logger.info("心跳循环线程启动")

        # 首次心跳延迟 10 秒，给系统启动留出时间
        time.sleep(10)

        while self._running:
            try:
                commands = self.send_heartbeat_now()

                # 如果有命令，处理命令
                if commands:
                    logger.info(f"心跳返回 {len(commands)} 个待执行命令")
                    # 命令处理由 CommandPoller 负责，这里只记录
                    for cmd in commands:
                        logger.info(f"待执行命令：id={cmd.id}, type={cmd.command_type}")

            except Exception as e:
                logger.error(f"心跳循环异常：{e}")

            # 等待下一次心跳
            for _ in range(self.interval * 10):
                if not self._running:
                    break
                time.sleep(0.1)

        logger.info("心跳循环线程退出")


class HeartbeatReporterBuilder:
    """
    心跳上报器构建器

    链式调用构建 HeartbeatReporter
    """

    def __init__(self, external_api: ExternalAPI):
        """
        初始化构建器

        Args:
            external_api: ExternalAPI 实例
        """
        self.external_api = external_api
        self.interval = HeartbeatReporter.DEFAULT_INTERVAL
        self.timeout = HeartbeatReporter.DEFAULT_TIMEOUT

    def interval(self, interval: int) -> "HeartbeatReporterBuilder":
        """设置心跳间隔"""
        self.interval = interval
        return self

    def timeout(self, timeout: int) -> "HeartbeatReporterBuilder":
        """设置超时时间"""
        self.timeout = timeout
        return self

    def build(self) -> HeartbeatReporter:
        """构建心跳上报器"""
        return HeartbeatReporter(
            external_api=self.external_api,
            interval=self.interval,
            timeout=self.timeout,
        )
