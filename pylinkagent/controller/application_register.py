"""
应用自动注册模块

参考 Java LinkAgent 的 HttpApplicationUploader 实现
实现应用的自动注册和同步
"""

import os
import socket
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ApplicationInfo:
    """
    应用信息数据类

    对应 Java: ApplicationInfoDTO
    """
    application_name: str = ""
    application_desc: str = ""
    use_yn: int = 0  # 0:启用，1:禁用
    access_status: int = 0  # 0:正常，1:待配置，2:待检测，3:异常
    switch_status: str = "OPENED"  # OPENED/CLOSED
    node_num: int = 1
    agent_version: str = "1.0.0"
    pradar_version: str = "1.0.0"

    # 扩展字段
    cluster_name: str = "default"
    ddl_script_path: str = ""
    clean_script_path: str = ""
    ready_script_path: str = ""
    base_script_path: str = ""
    cache_script_path: str = ""
    tenant_id: str = "1"
    env_code: str = "test"
    user_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "applicationName": self.application_name,
            "applicationDesc": self.application_desc,
            "useYn": self.use_yn,
            "accessStatus": self.access_status,
            "switchStatus": self.switch_status,
            "nodeNum": self.node_num,
            "agentVersion": self.agent_version,
            "pradarVersion": self.pradar_version,
            "clusterName": self.cluster_name,
            "ddlScriptPath": self.ddl_script_path,
            "cleanScriptPath": self.clean_script_path,
            "readyScriptPath": self.ready_script_path,
            "baseScriptPath": self.base_script_path,
            "cacheScriptPath": self.cache_script_path,
            "tenantId": self.tenant_id,
            "envCode": self.env_code,
            "userId": self.user_id,
        }


class ApplicationRegistrator:
    """
    应用注册器

    参考 Java: HttpApplicationUploader
    """

    def __init__(self, external_api):
        """
        初始化应用注册器

        Args:
            external_api: ExternalAPI 实例
        """
        self.external_api = external_api
        self._is_registered = False
        self._application_id: Optional[str] = None

    def register(self, app_info: Optional[ApplicationInfo] = None) -> bool:
        """
        注册应用

        Args:
            app_info: 应用信息，为 None 时自动生成

        Returns:
            bool: 注册成功返回 True
        """
        if self._is_registered:
            logger.info("应用已注册，跳过")
            return True

        try:
            # 生成应用信息
            if app_info is None:
                app_info = self._generate_app_info()

            # 上传应用信息
            success = self.external_api.upload_application_info(app_info.to_dict())

            if success:
                self._is_registered = True
                logger.info(f"应用注册成功：{app_info.application_name}")
                return True
            else:
                logger.error("应用注册失败")
                return False

        except Exception as e:
            logger.error(f"应用注册异常：{e}")
            return False

    def _generate_app_info(self) -> ApplicationInfo:
        """
        生成应用信息

        Returns:
            ApplicationInfo: 应用信息对象
        """
        # 从环境变量读取配置
        app_name = self.external_api.app_name
        cluster_name = os.getenv('CLUSTER_NAME', 'default')
        tenant_id = os.getenv('SIMULATOR_TENANT_ID', os.getenv('TENANT_ID', '1'))
        env_code = os.getenv('SIMULATOR_ENV_CODE', os.getenv('ENV_CODE', 'test'))
        user_id = os.getenv('SIMULATOR_USER_ID', os.getenv('USER_ID', ''))

        # 生成应用描述
        hostname = socket.gethostname()
        try:
            ip_address = socket.gethostbyname(hostname)
        except Exception:
            ip_address = "127.0.0.1"

        return ApplicationInfo(
            application_name=app_name,
            application_desc=f"Application: {app_name} (Host: {hostname}, IP: {ip_address})",
            use_yn=0,  # 启用
            access_status=0,  # 正常
            switch_status="OPENED",  # 已开启
            node_num=1,
            agent_version=self.external_api.agent_version if hasattr(self.external_api, 'agent_version') else "1.0.0",
            pradar_version=self.external_api.simulator_version if hasattr(self.external_api, 'simulator_version') else "1.0.0",
            cluster_name=cluster_name,
            tenant_id=tenant_id,
            env_code=env_code,
            user_id=user_id,
        )

    def is_registered(self) -> bool:
        """检查是否已注册"""
        return self._is_registered

    def get_application_id(self) -> Optional[str]:
        """获取应用 ID"""
        return self._application_id

    def sync_application_info(self) -> bool:
        """
        同步应用信息（更新现有应用）

        Returns:
            bool: 同步成功返回 True
        """
        if not self._is_registered:
            logger.warning("应用未注册，无法同步")
            return False

        try:
            app_info = self._generate_app_info()
            # 增加 node_num
            app_info.node_num = self._get_current_node_num() + 1

            success = self.external_api.upload_application_info(app_info.to_dict())

            if success:
                logger.info(f"应用信息同步成功：{app_info.application_name}")
                return True
            else:
                logger.error("应用信息同步失败")
                return False

        except Exception as e:
            logger.error(f"应用信息同步异常：{e}")
            return False

    def _get_current_node_num(self) -> int:
        """获取当前节点数（简化实现，返回 1）"""
        # TODO: 从数据库或缓存读取实际节点数
        return 1


class ApplicationStatusReporter:
    """
    应用状态上报器

    参考 Java: 应用接入状态上报相关实现
    """

    def __init__(self, external_api):
        """
        初始化应用状态上报器

        Args:
            external_api: ExternalAPI 实例
        """
        self.external_api = external_api
        self._error_map: Dict[str, Any] = {}

    def report_access_status(self,
                             status: int = 0,
                             error_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        上报应用接入状态

        Args:
            status: 状态码 (0:正常，1:待配置，2:待检测，3:异常)
            error_info: 错误信息

        Returns:
            bool: 上报成功返回 True
        """
        if error_info:
            self._error_map.update(error_info)

        return self.external_api.upload_access_status(self._error_map)

    def report_config_error(self, config_type: str, error_msg: str) -> bool:
        """
        上报配置错误

        Args:
            config_type: 配置类型 (shadow_db, redis, es, etc.)
            error_msg: 错误信息

        Returns:
            bool: 上报成功返回 True
        """
        error_info = {
            "configType": config_type,
            "errorMsg": error_msg,
            "timestamp": int(os.path.getctime(__file__)) if os.path.exists(__file__) else 0,
        }
        return self.report_access_status(status=3, error_info=error_info)

    def report_config_success(self, config_type: str) -> bool:
        """
        上报配置成功

        Args:
            config_type: 配置类型

        Returns:
            bool: 上报成功返回 True
        """
        error_info = {
            f"{config_type}.status": "success",
            f"{config_type}.timestamp": int(os.path.getctime(__file__)) if os.path.exists(__file__) else 0,
        }
        return self.report_access_status(status=0, error_info=error_info)

    def clear_errors(self) -> None:
        """清除错误信息"""
        self._error_map.clear()
