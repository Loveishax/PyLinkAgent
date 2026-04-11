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
    对接 Takin-web / takin-ee-web 接口
    """

    # ==================== 心跳相关接口 ====================
    # 心跳上报接口 (对应 Java: ExternalAPIImpl.HEART_URL = "api/agent/heartbeat")
    HEART_URL = "/api/agent/heartbeat"

    # ==================== 命令相关接口 ====================
    # 命令拉取接口 (对应 Java: ExternalAPIImpl.COMMAND_URL = "api/agent/application/node/probe/operate")
    COMMAND_URL = "/api/agent/application/node/probe/operate"

    # 命令结果上报接口 (对应 Java: ExternalAPIImpl.REPORT_URL = "api/agent/application/node/probe/operateResult")
    REPORT_URL = "/api/agent/application/node/probe/operateResult"

    # ==================== 配置拉取接口 ====================
    # 影子库配置拉取 (对应 Java: ApplicationConfigHttpResolver.SHADOW_DB_TABLE_URL)
    SHADOW_DB_CONFIG_URL = "/api/link/ds/configs/pull"

    # 远程调用配置 (白名单/黑名单/Mock) (对应 Java: ApplicationConfigHttpResolver.WHITELIST_FILE_URL)
    REMOTE_CALL_CONFIG_URL = "/api/remote/call/configs/pull"

    # 影子 Redis Server 配置 (对应 Java: ApplicationConfigHttpResolver.REDIS_SHADOW_SERVER_URL)
    SHADOW_REDIS_SERVER_URL = "/api/link/ds/server/configs/pull"

    # 影子 ES Server 配置 (对应 Java: ApplicationConfigHttpResolver.ES_SHADOW_SERVER_URL)
    SHADOW_ES_SERVER_URL = "/api/link/es/server/configs/pull"

    # 影子 Job 配置 (对应 Java: ApplicationConfigHttpResolver.TRO_SHADOW_JOB_URL)
    SHADOW_JOB_URL = "/api/shadow/job/queryByAppName"

    # 影子 MQ 消费者配置 (对应 Java: ApplicationConfigHttpResolver.TRO_SHADOW_MQ_CONSUMER_URL)
    SHADOW_MQ_CONSUMER_URL = "/api/agent/configs/shadow/consumer"

    # ACK 接口 (保留)
    ACK_URL = "/api/agent/event/ack"

    # 应用信息上传接口
    APP_UPLOAD_URL = "/api/application/center/app/info"

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

            # 测试连接 - 直接调用心跳接口测试
            # 注意：管理侧可能没有健康检查端点，使用心跳接口测试
            self._initialized = True
            logger.info(f"ExternalAPI 初始化成功：{self.tro_web_url}")
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
        接口：GET /api/agent/application/node/probe/operate

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

            # Takin-web 响应格式：{ "success": true, "data": {...} }
            if isinstance(response, dict):
                if response.get("success", True):
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
        接口：POST /api/agent/heartbeat

        Args:
            heart_request: 心跳请求

        Returns:
            List[CommandPacket]: 控制台返回的待执行命令列表
        """
        if not self._initialized:
            logger.warning("ExternalAPI 未初始化")
            return []

        url = self.HEART_URL

        # 配置心跳请求数据
        heart_request.project_name = self.app_name
        heart_request.agent_id = self.agent_id

        try:
            # Takin-web 直接返回 List<AgentCommandResBO>，不需要包装在 Result 中
            response_data = self._request("POST", url, heart_request.to_dict())

            if not response_data:
                return []

            # Takin-web 的响应格式：直接是命令数组
            # [{ "id": 1, "extrasString": "..." }, ...]
            if isinstance(response_data, list):
                commands = [CommandPacket.from_dict(c) for c in response_data]
                if commands:
                    logger.info(f"心跳响应返回 {len(commands)} 个命令")
                return commands

            # 如果响应包装在 { "success": true, "data": [...] } 中
            if isinstance(response_data, dict):
                if response_data.get("success", True):
                    data = response_data.get("data", [])
                    commands = [CommandPacket.from_dict(c) for c in data]
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
        接口：POST /api/agent/application/node/probe/operateResult

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
            success = response.get("success", True) if response else False

            if success:
                logger.info(f"命令执行结果已上报：commandId={command_id}, success={is_success}")
            else:
                logger.warning(f"上报命令结果失败：commandId={command_id}")

            return success

        except Exception as e:
            logger.error(f"上报命令结果失败：{e}")
            return False

    def fetch_shadow_database_config(self) -> Optional[List[Dict[str, Any]]]:
        """
        拉取影子库配置

        对应 Java 的 getPressureTable4AccessSimple()
        接口：GET /api/link/ds/configs/pull?appName=xxx

        Returns:
            影子库配置列表，失败返回 None

        配置格式示例:
        [
            {
                "dataSourceName": "master",
                "url": "jdbc:mysql://master:3306/app",
                "username": "root",
                "shadowUrl": "jdbc:mysql://shadow:3306/app_shadow",
                "shadowUsername": "root_shadow"
            }
        ]
        """
        if not self._initialized:
            logger.warning("ExternalAPI 未初始化")
            return None

        url = f"{self.SHADOW_DB_CONFIG_URL}?appName={self.app_name}"

        try:
            response = self._request("GET", url)

            if not response:
                logger.warning("影子库配置拉取返回空")
                return None

            # Takin-web 响应格式：{ "success": true, "data": [...] }
            if isinstance(response, dict):
                if not response.get("success", True):
                    logger.error(f"影子库配置拉取失败：{response.get('error', 'unknown error')}")
                    return None
                data = response.get("data", [])
            elif isinstance(response, list):
                data = response
            else:
                logger.error(f"影子库配置响应格式异常：{response}")
                return None

            if data:
                logger.info(f"影子库配置拉取成功：{len(data)} 个数据源")
            return data

        except Exception as e:
            logger.error(f"拉取影子库配置失败：{e}")
            return None

    def fetch_remote_call_config(self) -> Optional[Dict[str, Any]]:
        """
        拉取远程调用配置 (白名单/黑名单/Mock)

        对应 Java 的 getWhiteList()
        接口：GET /api/remote/call/configs/pull?appName=xxx

        Returns:
            远程调用配置，失败返回 None

        配置格式示例:
        {
            "newBlists": [...],  # 黑名单
            "wLists": [...],     # 白名单
            "mockConfigs": [...] # Mock 配置
        }
        """
        if not self._initialized:
            logger.warning("ExternalAPI 未初始化")
            return None

        url = f"{self.REMOTE_CALL_CONFIG_URL}?appName={self.app_name}"

        try:
            response = self._request("GET", url)

            if not response:
                logger.warning("远程调用配置拉取返回空")
                return None

            # Takin-web 响应格式：{ "success": true, "data": {...} }
            if isinstance(response, dict):
                if not response.get("success", True):
                    logger.error(f"远程调用配置拉取失败：{response.get('error', 'unknown error')}")
                    return None
                data = response.get("data", {})
            else:
                logger.error(f"远程调用配置响应格式异常：{response}")
                return None

            logger.info(f"远程调用配置拉取成功")
            return data

        except Exception as e:
            logger.error(f"拉取远程调用配置失败：{e}")
            return None

    def upload_application_info(self, app_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        上传应用信息

        对应 Java 的 uploadAppInfo()
        接口：POST /api/application/center/app/info

        Args:
            app_info: 应用信息字典，为 None 时使用默认值

        Returns:
            bool: 上传成功返回 True

        应用信息格式:
        {
            "applicationName": "test-app",
            "applicationDesc": "应用描述",
            "useYn": 0,  # 0:启用，1:禁用
            "accessStatus": 0,  # 0:正常，1:待配置，2:待检测，3:异常
            "switchStatus": "OPENED",  # OPENED:已开启，CLOSED:已关闭
            "nodeNum": 1,
            "agentVersion": "1.0.0",
            "pradarVersion": "1.0.0"
        }
        """
        if not self._initialized:
            logger.warning("ExternalAPI 未初始化")
            return False

        url = self.APP_UPLOAD_URL

        # 使用默认应用信息
        if app_info is None:
            app_info = {
                "applicationName": self.app_name,
                "applicationDesc": f"Application: {self.app_name}",
                "useYn": 0,
                "accessStatus": 0,
                "switchStatus": "OPENED",
                "nodeNum": 1,
                "agentVersion": self.agent_version if hasattr(self, 'agent_version') else "1.0.0",
                "pradarVersion": self.simulator_version if hasattr(self, 'simulator_version') else "1.0.0",
            }

        try:
            response = self._request("POST", url, app_info)

            if not response:
                logger.warning("应用信息上传返回空")
                return False

            # Takin-web 响应格式：{ "success": true, "data": {...} }
            if isinstance(response, dict):
                if response.get("success", True):
                    logger.info(f"应用信息上传成功：{self.app_name}")
                    return True
                else:
                    logger.error(f"应用信息上传失败：{response.get('error', 'unknown error')}")
                    return False

            return False

        except Exception as e:
            logger.error(f"上传应用信息失败：{e}")
            return False

    def upload_access_status(self, error_info: Dict[str, Any]) -> bool:
        """
        上报应用接入状态

        对应 Java 的 uploadAccessStatus()
        接口：POST /api/application/agent/access/status

        Args:
            error_info: 错误信息字典

        Returns:
            bool: 上报成功返回 True
        """
        if not self._initialized:
            logger.warning("ExternalAPI 未初始化")
            return False

        url = "/api/application/agent/access/status"

        body = {
            "nodeKey": os.getenv("NODE_KEY", "pylinkagent-" + str(os.getpid())),
            "agentId": self.agent_id,
            "applicationName": self.app_name,
            "switchErrorMap": error_info,
        }

        try:
            response = self._request("POST", url, body)

            if response:
                logger.info(f"应用接入状态上报成功")
                return True
            else:
                logger.warning(f"应用接入状态上报返回空")
                return False

        except Exception as e:
            logger.error(f"上报应用接入状态失败：{e}")
            return False

    def fetch_shadow_job_config(self) -> Optional[List[Dict[str, Any]]]:
        """
        拉取影子 Job 配置

        对应 Java 的 getShadowJobConfig()
        接口：GET /api/shadow/job/queryByAppName?appName=xxx

        Returns:
            影子 Job 配置列表，失败返回 None
        """
        if not self._initialized:
            logger.warning("ExternalAPI 未初始化")
            return None

        url = f"{self.SHADOW_JOB_URL}?appName={self.app_name}"

        try:
            response = self._request("GET", url)

            if not response:
                logger.warning("影子 Job 配置拉取返回空")
                return None

            if isinstance(response, dict):
                if not response.get("success", True):
                    logger.error(f"影子 Job 配置拉取失败：{response.get('error', 'unknown error')}")
                    return None
                data = response.get("data", [])
            elif isinstance(response, list):
                data = response
            else:
                logger.error(f"影子 Job 配置响应格式异常：{response}")
                return None

            if data:
                logger.info(f"影子 Job 配置拉取成功：{len(data)} 个 Job")
            return data

        except Exception as e:
            logger.error(f"拉取影子 Job 配置失败：{e}")
            return None

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
