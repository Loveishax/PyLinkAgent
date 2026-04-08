"""
ExternalAPI - PyLinkAgent 外部 API

参考 Java LinkAgent 的 ExternalAPI 实现，提供与控制台 (TRO) 的完整对接能力。

核心功能:
- 心跳上报 (/api/agent/heartbeat)
- 命令拉取 (/api/agent/application/node/probe/operate)
- 结果上报 (/api/agent/application/node/probe/operateResult)
- 模块下载
- 在线升级
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import logging
import time
import os
import json

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import requests


logger = logging.getLogger(__name__)


@dataclass
class CommandPacket:
    """
    命令包 - 对应 Java 的 CommandPacket

    从控制台接收到的命令数据
    """
    id: int = -1
    command_type: int = 1  # 1: 框架命令，2: 模块命令
    operate_type: int = 1  # 1: 安装，2: 卸载，3: 升级
    data_path: str = ""
    command_time: int = 0
    live_time: int = -1  # -1: 无限
    use_local: bool = False
    extras: Dict[str, Any] = field(default_factory=dict)
    extras_string: str = ""

    @classmethod
    def no_action_packet(cls) -> "CommandPacket":
        """创建无操作命令包"""
        return cls(id=-1, command_type=1, operate_type=1)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommandPacket":
        """从字典创建命令包"""
        return cls(
            id=data.get("id", -1),
            command_type=data.get("commandType", 1),
            operate_type=data.get("operateType", 1),
            data_path=data.get("dataPath", ""),
            command_time=data.get("commandTime", 0),
            live_time=data.get("liveTime", -1),
            use_local=data.get("useLocal", False),
            extras=data.get("extras", {}),
            extras_string=data.get("extrasString", ""),
        )


@dataclass
class HeartRequest:
    """
    心跳请求 - 对应 Java 的 HeartRequest

    发送到控制台的心跳数据
    """
    project_name: str = ""
    agent_id: str = ""
    ip_address: str = ""
    progress_id: str = ""
    cur_upgrade_batch: str = "-1"
    agent_status: str = "running"
    agent_error_info: str = ""
    simulator_status: str = "running"
    simulator_error_info: str = ""
    uninstall_status: int = 0
    dormant_status: int = 0
    agent_version: str = "1.0.0"
    simulator_version: str = "1.0.0"
    dependency_info: str = ""
    flag: str = "shulieEnterprise"
    task_exceed: bool = False
    command_result: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "projectName": self.project_name,
            "agentId": self.agent_id,
            "ipAddress": self.ip_address,
            "progressId": self.progress_id,
            "curUpgradeBatch": self.cur_upgrade_batch,
            "agentStatus": self.agent_status,
            "agentErrorInfo": self.agent_error_info,
            "simulatorStatus": self.simulator_status,
            "simulatorErrorInfo": self.simulator_error_info,
            "uninstallStatus": self.uninstall_status,
            "dormantStatus": self.dormant_status,
            "agentVersion": self.agent_version,
            "simulatorVersion": self.simulator_version,
            "dependencyInfo": self.dependency_info,
            "flag": self.flag,
            "taskExceed": self.task_exceed,
            "commandResult": self.command_result,
        }


class ExternalAPI:
    """
    外部 API - 与控制台通信的核心接口

    参考 Java LinkAgent 的 ExternalAPIImpl 实现
    """

    # API 端点
    COMMAND_URL = "/api/agent/application/node/probe/operate"
    HEART_URL = "/api/agent/heartbeat"
    REPORT_URL = "/api/agent/application/node/probe/operateResult"

    def __init__(
        self,
        tro_web_url: str,
        app_name: str,
        agent_id: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        初始化 ExternalAPI

        Args:
            tro_web_url: 控制台 Web 地址 (对应 tro.web.url)
            app_name: 应用名称
            agent_id: Agent ID
            api_key: API 密钥
            timeout: HTTP 超时时间 (秒)
        """
        self.tro_web_url = tro_web_url.rstrip("/")
        self.app_name = app_name
        self.agent_id = agent_id
        self.api_key = api_key or ""
        self.timeout = timeout

        self._client: Optional[Any] = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        初始化 API 客户端

        Returns:
            bool: 初始化成功返回 True
        """
        try:
            if HTTPX_AVAILABLE:
                self._client = httpx.Client(
                    base_url=self.tro_web_url,
                    timeout=self.timeout,
                    headers=self._get_headers(),
                )
            else:
                logger.info("httpx 不可用，使用 requests 作为降级方案")

            # 测试连接
            response = self._request("GET", "/api/health")
            self._initialized = response.get("success", False)

            if self._initialized:
                logger.info(f"ExternalAPI 初始化成功：{self.tro_web_url}")
            else:
                logger.warning(f"ExternalAPI 初始化：控制台连接测试失败")

            return self._initialized

        except Exception as e:
            logger.error(f"ExternalAPI 初始化失败：{e}")
            return False

    def shutdown(self) -> None:
        """关闭 API 客户端"""
        if self._client:
            if hasattr(self._client, "close"):
                self._client.close()
            self._client = None
        self._initialized = False
        logger.info("ExternalAPI 已关闭")

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def get_latest_command(self) -> CommandPacket:
        """
        获取最新命令

        对应 Java 的 getLatestCommandPacket()

        Returns:
            CommandPacket: 命令包，无命令时返回 NO_ACTION_PACKET
        """
        if not self._initialized:
            logger.warning("ExternalAPI 未初始化")
            return CommandPacket.no_action_packet()

        # Kafka 注册模式下不和控制台直接交互
        register_name = os.getenv("REGISTER_NAME", "zookeeper")
        if register_name.lower() == "kafka":
            logger.debug("Kafka 注册模式，跳过命令拉取")
            return CommandPacket.no_action_packet()

        url = f"{self.COMMAND_URL}?appName={self.app_name}&agentId={self.agent_id}"

        try:
            response = self._request("GET", url)

            if not response:
                return CommandPacket.no_action_packet()

            # 解析响应
            if response.get("success", False):
                data = response.get("data", {})
                if data:
                    cmd = CommandPacket.from_dict(data)
                    logger.info(f"获取到命令：id={cmd.id}, type={cmd.command_type}")
                    return cmd

            return CommandPacket.no_action_packet()

        except Exception as e:
            logger.error(f"获取命令失败：{e}")
            return CommandPacket.no_action_packet()

    def send_heartbeat(self, heart_request: HeartRequest) -> List[CommandPacket]:
        """
        发送心跳

        对应 Java 的 sendHeart()

        Args:
            heart_request: 心跳请求

        Returns:
            List[CommandPacket]: 命令包列表（控制台返回的待执行命令）
        """
        if not self._initialized:
            logger.warning("ExternalAPI 未初始化")
            return []

        url = self.HEART_URL

        # 配置心跳请求数据
        heart_request.project_name = self.app_name
        heart_request.agent_id = self.agent_id

        try:
            response = self._request("POST", url, heart_request.to_dict())

            if not response:
                return []

            # 解析返回的命令列表
            if response.get("success", False):
                commands_data = response.get("data", [])
                commands = [CommandPacket.from_dict(c) for c in commands_data]
                if commands:
                    logger.info(f"心跳响应返回 {len(commands)} 个命令")
                return commands

            return []

        except Exception as e:
            logger.error(f"发送心跳失败：{e}")
            return []

    def report_command_result(
        self,
        command_id: int,
        is_success: bool,
        error_msg: str = ""
    ) -> bool:
        """
        上报命令执行结果

        对应 Java 的 reportCommandResult()

        Args:
            command_id: 命令 ID
            is_success: 是否成功
            error_msg: 错误信息

        Returns:
            bool: 上报成功返回 True
        """
        if not self._initialized:
            logger.warning("ExternalAPI 未初始化")
            return False

        url = self.REPORT_URL

        body = {
            "appName": self.app_name,
            "agentId": self.agent_id,
            "operateResult": "1" if is_success else "0",
        }

        if error_msg:
            body["errorMsg"] = error_msg

        try:
            response = self._request("POST", url, body)
            success = response.get("success", False) if response else False

            if success:
                logger.info(f"命令执行结果已上报：commandId={command_id}, success={is_success}")
            else:
                logger.warning(f"上报命令结果失败：commandId={command_id}")

            return success

        except Exception as e:
            logger.error(f"上报命令结果失败：{e}")
            return False

    def download_module(self, download_url: str, target_path: str) -> Optional[str]:
        """
        下载模块包

        对应 Java 的 downloadModule()

        Args:
            download_url: 下载地址
            target_path: 下载存放路径

        Returns:
            str: 下载的文件路径，失败返回 None
        """
        if not download_url:
            return None

        # 添加应用参数
        if "?" in download_url:
            download_url += f"&appName={self.app_name}&agentId={self.agent_id}"
        else:
            download_url += f"?appName={self.app_name}&agentId={self.agent_id}"

        try:
            os.makedirs(target_path, exist_ok=True)

            if HTTPX_AVAILABLE:
                response = httpx.get(download_url, timeout=self.timeout)
            else:
                response = requests.get(download_url, timeout=self.timeout)

            response.raise_for_status()

            # 从 URL 提取文件名
            filename = download_url.split("/")[-1].split("?")[0]
            filepath = os.path.join(target_path, filename)

            with open(filepath, "wb") as f:
                f.write(response.content)

            logger.info(f"模块下载成功：{filepath}")
            return filepath

        except Exception as e:
            logger.error(f"下载模块失败：{e}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "PyLinkAgent/1.0.0",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # 添加控制台必需的请求头
        extra_headers = os.getenv("HTTP_MUST_HEADERS", "")
        if extra_headers:
            try:
                extra = json.loads(extra_headers)
                headers.update(extra)
            except Exception:
                pass

        return headers

    def _request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        retry: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            url: 请求 URL
            data: 请求体数据
            retry: 当前重试次数

        Returns:
            响应数据
        """
        retry_times = 3

        try:
            if HTTPX_AVAILABLE and self._client:
                return self._httpx_request(method, url, data)
            else:
                return self._requests_request(method, url, data)

        except Exception as e:
            logger.error(f"请求失败：{method} {url}, error={e}")

            # 重试逻辑
            if retry < retry_times:
                logger.info(f"重试请求 ({retry + 1}/{retry_times})")
                time.sleep(1.0 * (retry + 1))  # 指数退避
                return self._request(method, url, data, retry + 1)

            return None

    def _httpx_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用 httpx 发送请求"""
        if url.startswith("http"):
            full_url = url
        else:
            full_url = f"{self.tro_web_url}{url}"

        if data:
            response = self._client.request(method, full_url, json=data)
        else:
            response = self._client.request(method, full_url)

        response.raise_for_status()
        return response.json()

    def _requests_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用 requests 发送请求（降级方案）"""
        if url.startswith("http"):
            full_url = url
        else:
            full_url = f"{self.tro_web_url}{url}"

        headers = self._get_headers()

        if data:
            response = requests.request(method, full_url, json=data, headers=headers, timeout=self.timeout)
        else:
            response = requests.request(method, full_url, headers=headers, timeout=self.timeout)

        response.raise_for_status()
        return response.json()
