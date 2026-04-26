"""
PyLinkAgent ZooKeeper configuration.

The Python agent keeps the same core identifiers as the Java agent:
- HTTP heartbeat uses the plain `agentId`
- ZooKeeper nodes use the full `agentId&env:user:tenantAppKey`
"""

import json
import logging
import os
import platform
import socket
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


def get_local_address() -> str:
    """Return the best-effort local routable IP address."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        sock.close()
        return address
    except Exception:
        return "127.0.0.1"


def get_host_name() -> str:
    """Return the local host name."""
    try:
        return socket.gethostname() or "localhost"
    except Exception:
        return "localhost"


@dataclass
class ZkConfig:
    """ZooKeeper configuration."""

    zk_servers: str = "7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181"

    status_base_path: str = "/config/log/pradar/client"
    client_base_path: str = "/config/log/pradar/client"
    server_base_path: str = "/config/log/pradar/server"

    connection_timeout_ms: int = 60000
    session_timeout_ms: int = 60000
    max_retries: int = 3
    retry_interval_ms: int = 1000

    app_name: str = "default"
    agent_id: Optional[str] = None
    env_code: str = "test"
    tenant_id: str = "1"
    user_id: str = ""
    tenant_app_key: str = ""

    agent_version: str = "1.0.0"
    simulator_version: str = "1.0.0"

    tro_web_url: str = "http://localhost:9999"
    log_path: str = ""

    agent_file_configs: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env_and_file(cls, config_file: Optional[str] = None) -> "ZkConfig":
        """Load configuration from file and environment."""
        config = cls()

        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as file_obj:
                    file_config = json.load(file_obj)
                for key, value in file_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                        config.agent_file_configs[key] = str(value)
                logger.info("Loaded ZK config file: %s", config_file)
            except Exception as exc:
                logger.warning("Failed to read ZK config file %s: %s", config_file, exc)

        env_mappings = {
            "SIMULATOR_ZK_SERVERS": "zk_servers",
            "SIMULATOR_APP_NAME": "app_name",
            "SIMULATOR_AGENT_ID": "agent_id",
            "SIMULATOR_ENV_CODE": "env_code",
            "SIMULATOR_TENANT_ID": "tenant_id",
            "SIMULATOR_USER_ID": "user_id",
            "SIMULATOR_TENANT_APP_KEY": "tenant_app_key",
            "SIMULATOR_AGENT_VERSION": "agent_version",
            "SIMULATOR_VERSION": "simulator_version",
            "SIMULATOR_LOG_PATH": "log_path",
            "TRO_WEB_URL": "tro_web_url",
            "PRADAR_PROJECT_NAME": "app_name",
            "PRADAR_ENV_CODE": "env_code",
            "PRADAR_USER_ID": "user_id",
            "APP_NAME": "app_name",
            "MANAGEMENT_URL": "tro_web_url",
        }
        for env_name, attr_name in env_mappings.items():
            value = os.environ.get(env_name)
            if value:
                setattr(config, attr_name, value)

        system_prop_mappings = {
            "SIMULATOR_ZK_SERVERS": "zk_servers",
            "SIMULATOR_APP_NAME": "app_name",
            "SIMULATOR_AGENTID": "agent_id",
            "SIMULATOR_ENV_CODE": "env_code",
            "SIMULATOR_AGENT_VERSION": "agent_version",
            "SIMULATOR_VERSION": "simulator_version",
            "TRO_WEB_URL": "tro_web_url",
            "PRADAR_PROJECT_NAME": "app_name",
            "PRADAR_ENV_CODE": "env_code",
            "PRADAR_USER_ID": "user_id",
        }
        for env_name, attr_name in system_prop_mappings.items():
            value = os.environ.get(env_name)
            if value:
                setattr(config, attr_name, value)

        if not config.agent_id:
            config.agent_id = cls._generate_default_agent_id()
            logger.info("Generated default agent_id: %s", config.agent_id)

        if not config.log_path:
            config.log_path = os.path.join(
                os.path.expanduser("~"),
                "pylinkagent_logs",
                config.app_name,
            )

        logger.info(
            "ZK config ready: zk_servers=%s, app_name=%s, agent_id=%s",
            config.zk_servers,
            config.app_name,
            config.agent_id,
        )
        return config

    @staticmethod
    def _generate_default_agent_id() -> str:
        """Generate the Java-style plain agent ID: `<ip>-<pid>`."""
        return f"{get_local_address()}-{os.getpid()}"

    def get_full_agent_id(self, include_user_info: bool = True) -> str:
        """Return the full ZK agent ID with env/user/tenant suffix."""
        plain_agent_id = self.agent_id or self._generate_default_agent_id()
        if not include_user_info or not self.env_code:
            return plain_agent_id
        return f"{plain_agent_id}&{self.env_code}:{self.user_id or ''}:{self.tenant_app_key or ''}"

    def get_status_path(self) -> str:
        """Return the online node path."""
        return f"{self.status_base_path}/{self.app_name}/{self.get_full_agent_id()}"

    def get_client_path(self) -> str:
        """Return the client path node."""
        return f"{self.client_base_path}/{self.app_name}/{self.get_full_agent_id()}"

    def get_node_key(self) -> str:
        """Return the node key used by access status reporting."""
        return f"{self.app_name}:{self.agent_id or self._generate_default_agent_id()}"

    def to_heartbeat_data(
        self,
        agent_status: str = "RUNNING",
        error_code: str = "",
        error_msg: str = "",
        jvm_args: str = "",
        jdk_version: str = "",
        simulator_service: str = "",
        simulator_port: int = 0,
        md5: str = "",
        jars: Optional[list] = None,
        simulator_file_configs: Optional[Dict[str, Any]] = None,
        agent_file_configs: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Build the ZK node payload."""
        python_runtime = jdk_version or f"Python {platform.python_version()}"
        data = {
            "address": get_local_address(),
            "host": get_host_name(),
            "name": self.app_name,
            "pid": str(os.getpid()),
            "agentId": self.get_full_agent_id(),
            "agentLanguage": "PYTHON",
            "agentVersion": self.agent_version,
            "simulatorVersion": self.simulator_version,
            "agentStatus": agent_status,
            "errorCode": error_code,
            "errorMsg": error_msg,
            "jvmArgs": jvm_args or " ".join(os.environ.get("PYTHONOPTIMIZE", "").split()),
            "jdkVersion": python_runtime,
            "jdk": python_runtime,
            "jvmArgsCheck": "PASS",
            "tenantAppKey": self.tenant_app_key,
            "envCode": self.env_code,
            "userId": self.user_id,
            "service": simulator_service,
            "port": str(simulator_port) if simulator_port else "",
            "md5": md5,
            "jars": jars or [],
        }
        if simulator_file_configs:
            data["simulatorFileConfigs"] = simulator_file_configs
        if agent_file_configs:
            data["agentFileConfigs"] = agent_file_configs
        elif self.agent_file_configs:
            data["agentFileConfigs"] = self.agent_file_configs
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    def __str__(self) -> str:
        return (
            f"ZkConfig(zk_servers={self.zk_servers}, app_name={self.app_name}, "
            f"agent_id={self.agent_id}, env_code={self.env_code})"
        )


_global_config: Optional[ZkConfig] = None


def get_config(config_file: Optional[str] = None) -> ZkConfig:
    """Return the global ZK config singleton."""
    global _global_config
    if _global_config is None:
        _global_config = ZkConfig.from_env_and_file(config_file)
    return _global_config


def reset_config() -> None:
    """Reset the global ZK config singleton."""
    global _global_config
    _global_config = None
