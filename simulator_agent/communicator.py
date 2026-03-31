"""
Communicator - 与控制平台通信模块

负责：
- HTTP/gRPC 通信
- 请求签名与认证
- 重试与超时处理
- 命令轮询
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import logging
import time

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from pylinkagent.config import Config


logger = logging.getLogger(__name__)


@dataclass
class Command:
    """
    命令对象

    从控制平台下发的命令
    """
    id: str
    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # 优先级，数字越大优先级越高

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Command":
        """从字典创建命令"""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            params=data.get("params", {}),
            timestamp=data.get("timestamp", time.time()),
            priority=data.get("priority", 0),
        )


class Communicator:
    """
    通信器

    提供与控制平台的双向通信能力
    """

    def __init__(self, config: Config):
        """
        初始化通信器

        Args:
            config: 配置对象
        """
        self.config = config
        self.platform_url = config.platform_url
        self.api_key = config.platform_api_key
        self.timeout = config.platform_timeout
        self.retry_times = 3

        self._client: Optional[Any] = None
        self._connected = False

    def connect(self) -> bool:
        """
        建立连接

        Returns:
            bool: 连接成功返回 True
        """
        try:
            if HTTPX_AVAILABLE:
                self._client = httpx.Client(
                    base_url=self.platform_url,
                    timeout=self.timeout,
                    headers=self._get_headers(),
                )
            else:
                # 降级使用 requests
                self._client = self._create_requests_client()

            # 测试连接
            response = self._request("GET", "/api/health")
            self._connected = response.get("success", False)

            return self._connected

        except Exception as e:
            logger.error(f"连接失败：{e}")
            return False

    def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            if hasattr(self._client, "close"):
                self._client.close()
            self._client = None
        self._connected = False
        logger.info("已断开与控制平台的连接")

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    def register(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        注册到平台

        Args:
            data: 注册数据

        Returns:
            注册结果
        """
        return self._request("POST", "/api/agent/register", data)

    def send_heartbeat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送心跳

        Args:
            data: 心跳数据

        Returns:
            响应结果
        """
        return self._request("POST", "/api/agent/heartbeat", data)

    def poll_commands(self) -> List[Command]:
        """
        轮询命令

        Returns:
            命令列表
        """
        result = self._request("GET", "/api/agent/commands")
        commands_data = result.get("commands", [])
        return [Command.from_dict(c) for c in commands_data]

    def report_command_result(self, command_id: str, result: Any) -> Dict[str, Any]:
        """
        上报命令执行结果

        Args:
            command_id: 命令 ID
            result: 执行结果

        Returns:
            响应结果
        """
        return self._request(
            "POST",
            f"/api/agent/commands/{command_id}/result",
            {"result": result}
        )

    def report_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        上报采集数据

        Args:
            data: 采集数据

        Returns:
            响应结果
        """
        return self._request("POST", "/api/agent/data", data)

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        retry: int = 0
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            path: 请求路径
            data: 请求体数据
            retry: 当前重试次数

        Returns:
            响应数据
        """
        url = f"{path}"

        try:
            if HTTPX_AVAILABLE:
                return self._httpx_request(method, url, data)
            else:
                return self._requests_request(method, url, data)

        except Exception as e:
            logger.error(f"请求失败：{method} {url}, error={e}")

            # 重试逻辑
            if retry < self.retry_times:
                logger.info(f"重试请求 ({retry + 1}/{self.retry_times})")
                time.sleep(1.0 * (retry + 1))  # 指数退避
                return self._request(method, path, data, retry + 1)

            return {"success": False, "error": str(e)}

    def _httpx_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用 httpx 发送请求"""
        if data:
            response = self._client.request(method, url, json=data)
        else:
            response = self._client.request(method, url)

        response.raise_for_status()
        return response.json()

    def _requests_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用 requests 发送请求（降级方案）"""
        import requests

        full_url = f"{self.platform_url}{url}"
        headers = self._get_headers()

        if data:
            response = requests.request(method, full_url, json=data, headers=headers, timeout=self.timeout)
        else:
            response = requests.request(method, full_url, headers=headers, timeout=self.timeout)

        response.raise_for_status()
        return response.json()

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "PyLinkAgent/1.0.0",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _create_requests_client(self) -> Any:
        """创建 requests 客户端（降级方案）"""
        class RequestsClient:
            def __init__(self, base_url: str, timeout: float, headers: Dict[str, str]):
                self.base_url = base_url
                self.timeout = timeout
                self.headers = headers

            def request(self, method: str, url: str, **kwargs):
                import requests
                full_url = f"{self.base_url}{url}"
                headers = {**self.headers, **kwargs.pop('headers', {})}
                return requests.request(method, full_url, headers=headers, timeout=self.timeout, **kwargs)

            def close(self):
                pass

        return RequestsClient(self.platform_url, self.timeout, self._get_headers())
