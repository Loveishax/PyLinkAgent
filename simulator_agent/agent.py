"""
SimulatorAgent - 控制面主类

负责协调所有控制面功能
"""

from typing import Optional, Dict, Any, List
import threading
import logging
import time

from pylinkagent.config import Config
from .communicator import Communicator, Command
from .upgrade_manager import UpgradeManager
from .config_manager import ConfigManager
from .health_check import HealthChecker


logger = logging.getLogger(__name__)


class SimulatorAgent:
    """
    控制面 Agent

    作为与控制平台通信的入口，负责：
    1. 建立并维护与控制平台的连接
    2. 接收并执行平台下发的命令
    3. 定期上报心跳和状态
    4. 管理模块升级
    """

    def __init__(self, config: Config, instrument_simulator: Any = None):
        """
        初始化 SimulatorAgent

        Args:
            config: 探针配置
            instrument_simulator: instrument-simulator 实例（用于模块管理）
        """
        self.config = config
        self._instrument_simulator = instrument_simulator

        # 核心组件
        self._communicator = Communicator(config)
        self._upgrade_manager = UpgradeManager(config)
        self._config_manager = ConfigManager(config)
        self._health_checker = HealthChecker(config)

        # 状态
        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._command_thread: Optional[threading.Thread] = None

        # 命令处理器注册表
        self._command_handlers: Dict[str, Any] = {}

        self._register_default_handlers()

        logger.info("SimulatorAgent 初始化完成")

    def start(self) -> bool:
        """
        启动控制面 Agent

        Returns:
            bool: 启动成功返回 True
        """
        if self._running:
            logger.warning("SimulatorAgent 已经在运行")
            return True

        try:
            # 1. 启动通信器
            if not self._communicator.connect():
                logger.error("无法连接到控制平台")
                return False

            # 2. 注册到平台
            if not self._register_to_platform():
                logger.error("注册到平台失败")
                return False

            # 3. 启动心跳线程
            self._start_heartbeat()

            # 4. 启动命令轮询线程
            self._start_command_poller()

            # 5. 启动健康检查
            self._health_checker.start()

            self._running = True
            logger.info("SimulatorAgent 启动成功")
            return True

        except Exception as e:
            logger.exception(f"SimulatorAgent 启动失败：{e}")
            return False

    def stop(self) -> bool:
        """
        停止控制面 Agent

        Returns:
            bool: 停止成功返回 True
        """
        if not self._running:
            return True

        try:
            self._running = False

            # 1. 停止健康检查
            self._health_checker.stop()

            # 2. 停止心跳
            self._stop_heartbeat()

            # 3. 停止命令轮询
            self._stop_command_poller()

            # 4. 断开连接
            self._communicator.disconnect()

            logger.info("SimulatorAgent 已停止")
            return True

        except Exception as e:
            logger.exception(f"SimulatorAgent 停止失败：{e}")
            return False

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running

    def register_command_handler(self, command_type: str, handler: Any) -> None:
        """
        注册命令处理器

        Args:
            command_type: 命令类型
            handler: 处理器函数，签名：handler(command: Command) -> Any
        """
        self._command_handlers[command_type] = handler
        logger.debug(f"注册命令处理器：{command_type}")

    def execute_command(self, command: Command) -> Any:
        """
        执行命令

        Args:
            command: 命令对象

        Returns:
            命令执行结果
        """
        handler = self._command_handlers.get(command.type)
        if handler is None:
            logger.warning(f"未知命令类型：{command.type}")
            return {"success": False, "error": f"Unknown command: {command.type}"}

        try:
            logger.info(f"执行命令：{command.type}, id={command.id}")
            result = handler(command)

            # 上报命令执行结果
            self._communicator.report_command_result(command.id, result)

            return result

        except Exception as e:
            logger.exception(f"执行命令失败：{e}")
            error_result = {"success": False, "error": str(e)}
            self._communicator.report_command_result(command.id, error_result)
            return error_result

    # ========= 内部方法 =========

    def _register_default_handlers(self) -> None:
        """注册默认命令处理器"""
        self._command_handlers = {
            "UPGRADE_MODULE": self._handle_upgrade_module,
            "UNLOAD_MODULE": self._handle_unload_module,
            "UPDATE_CONFIG": self._handle_update_config,
            "ENABLE_AGENT": self._handle_enable_agent,
            "DISABLE_AGENT": self._handle_disable_agent,
            "RESTART_AGENT": self._handle_restart_agent,
            "GET_STATUS": self._handle_get_status,
        }

    def _register_to_platform(self) -> bool:
        """
        注册到控制平台

        Returns:
            bool: 注册成功返回 True
        """
        try:
            register_data = {
                "agent_id": self.config.agent_id,
                "app_name": self.config.app_name,
                "version": self._get_version(),
                "hostname": self._get_hostname(),
                "pid": self._get_pid(),
                "enabled_modules": self.config.enabled_modules,
            }

            result = self._communicator.register(register_data)

            if result.get("success"):
                logger.info("成功注册到控制平台")
                return True
            else:
                logger.error(f"注册失败：{result.get('error')}")
                return False

        except Exception as e:
            logger.exception(f"注册异常：{e}")
            return False

    def _start_heartbeat(self) -> None:
        """启动心跳线程"""
        def heartbeat_loop():
            while self._running:
                try:
                    self._send_heartbeat()
                except Exception as e:
                    logger.error(f"发送心跳失败：{e}")

                # 每 30 秒发送一次心跳
                time.sleep(30)

        self._heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            daemon=True,
            name="pylinkagent-heartbeat"
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        """停止心跳线程"""
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5.0)
            self._heartbeat_thread = None

    def _send_heartbeat(self) -> None:
        """发送心跳"""
        heartbeat_data = {
            "agent_id": self.config.agent_id,
            "timestamp": time.time(),
            "status": "running" if self._running else "stopped",
            "metrics": self._collect_metrics(),
        }
        self._communicator.send_heartbeat(heartbeat_data)

    def _start_command_poller(self) -> None:
        """启动命令轮询线程"""
        def command_poll_loop():
            while self._running:
                try:
                    commands = self._communicator.poll_commands()
                    for cmd in commands:
                        self.execute_command(cmd)
                except Exception as e:
                    logger.error(f"轮询命令失败：{e}")

                # 每 5 秒轮询一次
                time.sleep(5)

        self._command_thread = threading.Thread(
            target=command_poll_loop,
            daemon=True,
            name="pylinkagent-command-poller"
        )
        self._command_thread.start()

    def _stop_command_poller(self) -> None:
        """停止命令轮询线程"""
        if self._command_thread:
            self._command_thread.join(timeout=5.0)
            self._command_thread = None

    # ========= 命令处理器 =========

    def _handle_upgrade_module(self, command: Command) -> Dict[str, Any]:
        """处理模块升级命令"""
        module_name = command.params.get("module_name")
        module_version = command.params.get("version")
        download_url = command.params.get("download_url")

        logger.info(f"升级模块：{module_name} -> {module_version}")

        return self._upgrade_manager.upgrade_module(
            module_name,
            module_version,
            download_url,
            self._instrument_simulator
        )

    def _handle_unload_module(self, command: Command) -> Dict[str, Any]:
        """处理模块卸载命令"""
        module_name = command.params.get("module_name")

        logger.info(f"卸载模块：{module_name}")

        if self._instrument_simulator:
            return self._instrument_simulator.unload_module(module_name)
        return {"success": False, "error": "instrument_simulator not available"}

    def _handle_update_config(self, command: Command) -> Dict[str, Any]:
        """处理配置更新命令"""
        new_config = command.params.get("config", {})

        logger.info(f"更新配置：{new_config}")

        return self._config_manager.update_config(new_config)

    def _handle_enable_agent(self, command: Command) -> Dict[str, Any]:
        """处理启用探针命令"""
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            agent.enable()
            return {"success": True}
        return {"success": False, "error": "Agent not initialized"}

    def _handle_disable_agent(self, command: Command) -> Dict[str, Any]:
        """处理禁用探针命令"""
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            agent.disable()
            return {"success": True}
        return {"success": False, "error": "Agent not initialized"}

    def _handle_restart_agent(self, command: Command) -> Dict[str, Any]:
        """处理重启探针命令"""
        logger.info("收到重启命令")
        # 重启逻辑：停止 -> 启动
        self.stop()
        time.sleep(1)
        self.start()
        return {"success": True}

    def _handle_get_status(self, command: Command) -> Dict[str, Any]:
        """处理状态查询命令"""
        return self._get_status()

    # ========= 状态收集 =========

    def _get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "agent_id": self.config.agent_id,
            "running": self._running,
            "version": self._get_version(),
            "enabled_modules": self.config.enabled_modules,
            "health": self._health_checker.get_health_status(),
            "metrics": self._collect_metrics(),
        }

    def _collect_metrics(self) -> Dict[str, Any]:
        """收集指标数据"""
        # 简化的指标收集
        return {
            "uptime": time.time(),
            "memory_usage": self._get_memory_usage(),
        }

    def _get_memory_usage(self) -> float:
        """获取内存使用量（MB）"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0

    def _get_version(self) -> str:
        """获取版本号"""
        from pylinkagent.version import __version__
        return __version__

    def _get_hostname(self) -> str:
        """获取主机名"""
        import socket
        return socket.gethostname()

    def _get_pid(self) -> int:
        """获取进程 ID"""
        import os
        return os.getpid()
