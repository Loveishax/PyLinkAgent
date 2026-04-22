"""
CommandPoller - PyLinkAgent 命令轮询

参考 Java LinkAgent 的 CommandPacket 机制，定期从控制台拉取并执行命令。

核心功能:
- 定时命令轮询 (默认 30 秒)
- 命令解析与分发
- 命令执行结果上报
- 支持框架命令和模块命令
"""

import logging
import time
import os
import threading
from typing import Optional, List, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor, Future

from .external_api import ExternalAPI, CommandPacket


logger = logging.getLogger(__name__)


class CommandExecutor:
    """
    命令执行器 - 负责执行具体命令

    对应 Java 的 CommandExecutor
    """

    def __init__(self):
        self._handlers: Dict[int, Callable[[CommandPacket], bool]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """注册默认处理器"""
        # 框架命令处理器
        self.register_handler(CommandPacket.COMMAND_TYPE_FRAMEWORK, self._handle_framework_command)
        # 模块命令处理器
        self.register_handler(CommandPacket.COMMAND_TYPE_MODULE, self._handle_module_command)

    def register_handler(
        self,
        command_type: int,
        handler: Callable[[CommandPacket], bool]
    ) -> None:
        """
        注册命令处理器

        Args:
            command_type: 命令类型
            handler: 处理函数
        """
        self._handlers[command_type] = handler
        logger.debug(f"注册命令处理器：command_type={command_type}")

    def execute(self, command: CommandPacket) -> bool:
        """
        执行命令

        Args:
            command: 命令包

        Returns:
            bool: 执行成功返回 True
        """
        command_type = command.command_type

        if command_type not in self._handlers:
            logger.warning(f"未找到命令处理器：command_type={command_type}")
            return False

        try:
            handler = self._handlers[command_type]
            return handler(command)
        except Exception as e:
            logger.error(f"执行命令失败：command_id={command.id}, error={e}")
            return False

    def _handle_framework_command(self, command: CommandPacket) -> bool:
        """
        处理框架命令

        Args:
            command: 框架命令包

        Returns:
            bool: 执行成功返回 True
        """
        operate_type = command.operate_type

        logger.info(f"执行框架命令：operate_type={operate_type}")

        if operate_type == CommandPacket.OPERATE_TYPE_INSTALL:
            return self._handle_install(command)
        elif operate_type == CommandPacket.OPERATE_TYPE_UNINSTALL:
            return self._handle_uninstall(command)
        elif operate_type == CommandPacket.OPERATE_TYPE_UPGRADE:
            return self._handle_upgrade(command)
        else:
            logger.warning(f"未知操作类型：operate_type={operate_type}")
            return False

    def _handle_module_command(self, command: CommandPacket) -> bool:
        """
        处理模块命令

        Args:
            command: 模块命令包

        Returns:
            bool: 执行成功返回 True
        """
        operate_type = command.operate_type

        logger.info(f"执行模块命令：operate_type={operate_type}")

        if operate_type == CommandPacket.OPERATE_TYPE_INSTALL:
            return self._handle_module_install(command)
        elif operate_type == CommandPacket.OPERATE_TYPE_UNINSTALL:
            return self._handle_module_uninstall(command)
        elif operate_type == CommandPacket.OPERATE_TYPE_UPGRADE:
            return self._handle_module_upgrade(command)
        else:
            logger.warning(f"未知操作类型：operate_type={operate_type}")
            return False

    def _handle_install(self, command: CommandPacket) -> bool:
        """处理框架安装命令"""
        logger.info(f"执行框架安装：data_path={command.data_path}")
        return True

    def _handle_uninstall(self, command: CommandPacket) -> bool:
        """处理框架卸载命令"""
        logger.info(f"执行框架卸载")
        return True

    def _handle_upgrade(self, command: CommandPacket) -> bool:
        """处理框架升级命令"""
        logger.info(f"执行框架升级：data_path={command.data_path}")
        return True

    def _handle_module_install(self, command: CommandPacket) -> bool:
        """处理模块安装命令"""
        logger.info(f"执行模块安装：data_path={command.data_path}")
        return True

    def _handle_module_uninstall(self, command: CommandPacket) -> bool:
        """处理模块卸载命令"""
        logger.info(f"执行模块卸载")
        return True

    def _handle_module_upgrade(self, command: CommandPacket) -> bool:
        """处理模块升级命令"""
        logger.info(f"执行模块升级：data_path={command.data_path}")
        return True


class CommandPoller:
    """
    命令轮询器 - 定期从控制台拉取命令并执行

    参考 Java LinkAgent 的 getLatestCommandPacket 机制
    """

    DEFAULT_INTERVAL = 30  # 默认轮询间隔 (秒)

    def __init__(
        self,
        external_api: ExternalAPI,
        interval: int = DEFAULT_INTERVAL,
        auto_start: bool = False,
    ):
        """
        初始化命令轮询器

        Args:
            external_api: ExternalAPI 实例
            interval: 轮询间隔 (秒)，默认 30 秒
            auto_start: 是否自动启动
        """
        self.external_api = external_api
        self.interval = interval

        self._executor = CommandExecutor()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._task_executor: Optional[ThreadPoolExecutor] = None

        # 命令结果回调
        self._on_command_result: Optional[Callable[[int, bool, str], None]] = None

        if auto_start:
            self.start()

    def start(self) -> bool:
        """
        启动命令轮询

        Returns:
            bool: 启动成功返回 True
        """
        if self._running:
            logger.warning("命令轮询已在运行")
            return True

        if not self.external_api.is_initialized():
            logger.warning("ExternalAPI 未初始化，无法启动命令轮询")
            return False

        self._running = True
        self._task_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="command-poller"
        )
        self._thread = self._task_executor.submit(self._poll_loop)

        logger.info(f"命令轮询已启动：interval={self.interval}s")
        return True

    def stop(self) -> None:
        """停止命令轮询"""
        self._running = False

        if self._task_executor:
            self._task_executor.shutdown(wait=False)
            self._task_executor = None

        logger.info("命令轮询已停止")

    def is_running(self) -> bool:
        """检查命令轮询是否运行中"""
        return self._running

    def poll_now(self) -> List[CommandPacket]:
        """
        立即轮询一次命令

        Returns:
            List[CommandPacket]: 获取到的命令列表
        """
        if not self.external_api.is_initialized():
            logger.warning("ExternalAPI 未初始化")
            return []

        try:
            # 获取最新命令
            command = self.external_api.get_latest_command()

            # 检查是否是无操作命令
            if command.id == -1:
                logger.debug("轮询结果：无新命令")
                return []

            logger.info(f"轮询到命令：id={command.id}, type={command.command_type}")
            return [command]

        except Exception as e:
            logger.error(f"轮询命令失败：{e}")
            return []

    def set_on_command_result(self, callback: Callable[[int, bool, str], None]) -> None:
        """
        设置命令结果回调

        Args:
            callback: 回调函数 (command_id, is_success, error_msg)
        """
        self._on_command_result = callback

    def register_command_handler(
        self,
        command_type: int,
        handler: Callable[[CommandPacket], bool]
    ) -> None:
        """
        注册命令处理器

        Args:
            command_type: 命令类型
            handler: 处理函数
        """
        self._executor.register_handler(command_type, handler)
        logger.info(f"注册命令处理器：command_type={command_type}")

    def _poll_loop(self) -> None:
        """命令轮询循环"""
        logger.info("命令轮询线程启动")

        # 首次轮询延迟 15 秒，给系统启动留出时间
        time.sleep(15)

        while self._running:
            try:
                # 轮询命令
                commands = self.poll_now()

                # 执行命令
                for command in commands:
                    self._execute_command_async(command)

            except Exception as e:
                logger.error(f"命令轮询异常：{e}")

            # 等待下一次轮询
            for _ in range(self.interval * 10):
                if not self._running:
                    break
                time.sleep(0.1)

        logger.info("命令轮询线程退出")

    def _execute_command_async(self, command: CommandPacket) -> Future:
        """
        异步执行命令

        Args:
            command: 命令包

        Returns:
            Future: 执行结果 Future
        """
        if not self._task_executor:
            logger.warning("任务执行器未启动")
            return None

        future = self._task_executor.submit(self._execute_and_report, command)
        return future

    def _execute_and_report(self, command: CommandPacket) -> bool:
        """
        执行命令并上报结果

        Args:
            command: 命令包

        Returns:
            bool: 执行结果
        """
        command_id = command.id
        success = False
        error_msg = ""

        try:
            # 检查命令是否过期
            if command.live_time != -1:
                elapsed = time.time() - (command.command_time / 1000)
                if elapsed > command.live_time:
                    logger.warning(f"命令已过期：id={command_id}")
                    error_msg = "命令已过期"
                    self._report_result(command_id, False, error_msg)
                    return False

            # 执行命令
            success = self._executor.execute(command)

            if not success:
                error_msg = "命令执行失败"

        except Exception as e:
            success = False
            error_msg = f"执行异常：{e}"
            logger.error(f"执行命令异常：command_id={command_id}, error={error_msg}")

        # 上报结果
        self._report_result(command_id, success, error_msg)
        return success

    def _report_result(self, command_id: int, is_success: bool, error_msg: str) -> None:
        """
        上报命令执行结果

        Args:
            command_id: 命令 ID
            is_success: 是否成功
            error_msg: 错误信息
        """
        try:
            # 调用外部 API 上报
            self.external_api.report_command_result(command_id, is_success, error_msg)

            # 调用回调
            if self._on_command_result:
                self._on_command_result(command_id, is_success, error_msg)

        except Exception as e:
            logger.error(f"上报命令结果失败：command_id={command_id}, error={e}")


class CommandPollerBuilder:
    """
    命令轮询器构建器

    链式调用构建 CommandPoller
    """

    def __init__(self, external_api: ExternalAPI):
        """
        初始化构建器

        Args:
            external_api: ExternalAPI 实例
        """
        self.external_api = external_api
        self.interval = CommandPoller.DEFAULT_INTERVAL
        self.auto_start = False

    def interval(self, interval: int) -> "CommandPollerBuilder":
        """设置轮询间隔"""
        self.interval = interval
        return self

    def auto_start(self, auto_start: bool = True) -> "CommandPollerBuilder":
        """设置是否自动启动"""
        self.auto_start = auto_start
        return self

    def build(self) -> CommandPoller:
        """构建命令轮询器"""
        return CommandPoller(
            external_api=self.external_api,
            interval=self.interval,
            auto_start=self.auto_start,
        )


# 添加常量到 CommandPacket
CommandPacket.COMMAND_TYPE_FRAMEWORK = 1
CommandPacket.COMMAND_TYPE_MODULE = 2
CommandPacket.OPERATE_TYPE_INSTALL = 1
CommandPacket.OPERATE_TYPE_UNINSTALL = 2
CommandPacket.OPERATE_TYPE_UPGRADE = 3
