"""
PyLinkAgent ZooKeeper 配置管理

参考 Java LinkAgent 的 CoreConfig 实现
"""

import os
import socket
import getpass
import platform
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class ZkConfig:
    """ZooKeeper 配置"""
    # ZK 服务器地址列表 (默认值来自用户要求)
    zk_servers: str = "7.198.155.26:2181,7.198.153.71:2181,7.198.152.234:2181"

    # ZK 路径配置
    status_base_path: str = "/config/log/pradar/client"  # Java agent 默认在线节点路径
    client_base_path: str = "/config/log/pradar/client"  # Pradar 模块路径
    server_base_path: str = "/config/log/pradar/server"  # 日志服务器发现路径

    # 超时配置 (毫秒)
    connection_timeout_ms: int = 60000
    session_timeout_ms: int = 60000

    # 重试配置
    max_retries: int = 3
    retry_interval_ms: int = 1000

    # 应用信息
    app_name: str = "default"
    agent_id: Optional[str] = None
    env_code: str = "test"
    tenant_id: str = "1"
    user_id: str = ""
    tenant_app_key: str = ""

    # 探针版本信息
    agent_version: str = "1.0.0"
    simulator_version: str = "1.0.0"

    # 其他配置
    tro_web_url: str = "http://localhost:9999"
    log_path: str = ""

    # 文件配置 (从配置文件读取)
    agent_file_configs: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env_and_file(cls, config_file: Optional[str] = None) -> "ZkConfig":
        """
        从环境变量和配置文件加载配置

        优先级：环境变量 > 配置文件 > 默认值
        """
        config = cls()

        # 1. 从配置文件加载 (如果存在)
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    for key, value in file_config.items():
                        if hasattr(config, key):
                            setattr(config, key, value)
                            config.agent_file_configs[key] = str(value)
                logger.info(f"已从配置文件加载配置：{config_file}")
            except Exception as e:
                logger.warning(f"读取配置文件失败：{e}")

        # 2. 从环境变量覆盖
        env_mappings = {
            'SIMULATOR_ZK_SERVERS': 'zk_servers',
            'SIMULATOR_APP_NAME': 'app_name',
            'SIMULATOR_AGENT_ID': 'agent_id',
            'SIMULATOR_ENV_CODE': 'env_code',
            'SIMULATOR_TENANT_ID': 'tenant_id',
            'SIMULATOR_USER_ID': 'user_id',
            'SIMULATOR_TENANT_APP_KEY': 'tenant_app_key',
            'SIMULATOR_AGENT_VERSION': 'agent_version',
            'SIMULATOR_VERSION': 'simulator_version',
            'TRO_WEB_URL': 'tro_web_url',
            'SIMULATOR_LOG_PATH': 'log_path',
            'PRADAR_PROJECT_NAME': 'app_name',  # 兼容旧版本
            'PRADAR_ENV_CODE': 'env_code',
            'PRADAR_USER_ID': 'user_id',
            'APP_NAME': 'app_name',
            'MANAGEMENT_URL': 'tro_web_url',
        }

        for env_name, config_attr in env_mappings.items():
            value = os.environ.get(env_name)
            if value:
                setattr(config, config_attr, value)
                logger.debug(f"从环境变量 {env_name} 加载：{config_attr}={value}")

        # 3. 从系统属性覆盖 (兼容 Java 风格)
        system_props = {
            'simulator.zk.servers': 'zk_servers',
            'simulator.app.name': 'app_name',
            'simulator.agentId': 'agent_id',
            'simulator.env.code': 'env_code',
            'simulator.agent.version': 'agent_version',
            'simulator.version': 'simulator_version',
            'tro.web.url': 'tro_web_url',
            'pradar.project.name': 'app_name',
            'pradar.env.code': 'env_code',
            'pradar.user.id': 'user_id',
        }

        for prop_name, config_attr in system_props.items():
            value = os.environ.get(prop_name.upper().replace('.', '_'))
            if value:
                setattr(config, config_attr, value)
                logger.debug(f"从系统属性 {prop_name} 加载：{config_attr}={value}")

        # 4. 自动设置 agent_id (如果未配置)
        if not config.agent_id:
            config.agent_id = cls._generate_default_agent_id()
            logger.info(f"自动生成 agent_id: {config.agent_id}")

        # 5. 自动设置日志路径 (如果未配置)
        if not config.log_path:
            config.log_path = os.path.join(
                os.path.expanduser("~"),
                "pylinkagent_logs",
                config.app_name
            )

        logger.info(f"ZK 配置加载完成：zk_servers={config.zk_servers}, app_name={config.app_name}")
        return config

    @staticmethod
    def _generate_default_agent_id() -> str:
        """
        生成默认 agent_id

        格式：{IP}-{PID}
        参考 Java: AddressUtils.getLocalAddress() + "-" + PidUtils.getPid()
        """
        # 获取本机 IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception:
            ip_address = "127.0.0.1"

        # 获取进程 ID
        pid = os.getpid()

        return f"{ip_address}-{pid}"

    def get_full_agent_id(self, include_user_info: bool = True) -> str:
        """
        获取完整的 agent_id (包含租户信息)

        格式：{agent_id}&{env_code}:{user_id}:{tenant_app_key}
        参考 Java: ZookeeperRegister.getAgentId()
        """
        agent_id = self.agent_id or self._generate_default_agent_id()

        if not include_user_info or not self.env_code:
            return agent_id

        # 新版探针兼容老版本的控制台
        user_id = self.user_id or ""
        tenant_app_key = self.tenant_app_key or ""

        full_id = f"{agent_id}&{self.env_code}:{user_id}:{tenant_app_key}"
        logger.debug(f"生成完整 agent_id: {full_id}")
        return full_id

    def get_status_path(self) -> str:
        """
        获取 Agent 状态路径

        格式：/config/log/pradar/status/{app_name}/{agent_id}
        """
        return f"{self.status_base_path}/{self.app_name}/{self.get_full_agent_id()}"

    def get_client_path(self) -> str:
        """
        获取 Pradar 模块路径

        格式：/config/log/pradar/client/{app_name}/{agent_id}
        """
        return f"{self.client_base_path}/{self.app_name}/{self.get_full_agent_id()}"

    def to_heartbeat_data(self,
                          agent_status: str = "running",
                          error_code: str = "",
                          error_msg: str = "",
                          jvm_args: str = "",
                          jdk_version: str = "",
                          simulator_service: str = "",
                          simulator_port: int = 0,
                          md5: str = "",
                          jars: list = None,
                          simulator_file_configs: Dict = None,
                          agent_file_configs: Dict = None) -> bytes:
        """
        生成心跳节点数据

        参考 Java: ZookeeperRegister.getHeartbeatDatas()

        Returns:
            bytes: UTF-8 编码的 JSON 数据
        """
        data = {
            # 基础信息
            "address": socket.gethostbyname(socket.gethostname()) if socket.gethostname() else "127.0.0.1",
            "host": socket.gethostname(),
            "name": os.path.basename(os.getcwd()),
            "pid": str(os.getpid()),
            "agentId": self.get_full_agent_id(),

            # 版本信息
            "agentLanguage": "PYTHON",
            "agentVersion": self.agent_version,
            "simulatorVersion": self.simulator_version,

            # 状态信息
            "agentStatus": agent_status,
            "errorCode": error_code,
            "errorMsg": error_msg,

            # JVM/Python 信息 (兼容 Java)
            "jvmArgs": jvm_args or " ".join(os.environ.get('PYTHONOPTIMIZE', '').split()),
            "jdkVersion": jdk_version or f"Python {platform.python_version()}",
            "jvmArgsCheck": "PASS",  # Python 不做 JVM 参数检查

            # 租户信息
            "tenantAppKey": self.tenant_app_key,
            "envCode": self.env_code,
            "userId": self.user_id,

            # Simulator 信息
            "service": simulator_service,
            "port": str(simulator_port) if simulator_port else "",

            # 其他信息
            "md5": md5,
            "jars": jars or [],
        }

        # 文件配置
        if simulator_file_configs:
            data["simulatorFileConfigs"] = simulator_file_configs
        if agent_file_configs:
            data["agentFileConfigs"] = agent_file_configs
        elif self.agent_file_configs:
            data["agentFileConfigs"] = self.agent_file_configs

        return json.dumps(data, ensure_ascii=False).encode('utf-8')

    def __str__(self) -> str:
        return (f"ZkConfig(zk_servers={self.zk_servers}, app_name={self.app_name}, "
                f"agent_id={self.agent_id}, env_code={self.env_code})")


# 全局配置实例 (单例模式)
_global_config: Optional[ZkConfig] = None


def get_config(config_file: Optional[str] = None) -> ZkConfig:
    """
    获取全局配置实例

    Args:
        config_file: 配置文件路径

    Returns:
        ZkConfig 实例
    """
    global _global_config
    if _global_config is None:
        _global_config = ZkConfig.from_env_and_file(config_file)
    return _global_config


def reset_config():
    """重置全局配置 (用于测试)"""
    global _global_config
    _global_config = None
