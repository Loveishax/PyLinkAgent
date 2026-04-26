"""
Application registration helpers for Takin-web.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pylinkagent.zookeeper.config import get_host_name, get_local_address


logger = logging.getLogger(__name__)


@dataclass
class ApplicationInfo:
    """Application metadata payload sent to the control plane."""

    application_name: str = ""
    application_desc: str = ""
    use_yn: int = 0
    access_status: int = 0
    switch_status: str = "OPENED"
    node_num: int = 1
    agent_version: str = "1.0.0"
    pradar_version: str = "1.0.0"

    cluster_name: str = "default"
    ddl_script_path: str = ""
    clean_script_path: str = ""
    ready_script_path: str = ""
    base_script_path: str = ""
    cache_script_path: str = ""
    tenant_id: str = "1"
    env_code: str = "test"
    user_id: str = ""

    agent_id: str = ""
    node_key: str = ""
    machine_ip: str = ""
    host_name: str = ""
    pid: str = ""
    language: str = "PYTHON"
    framework_name: str = "PyLinkAgent"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to the control-plane payload."""
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
            "agentId": self.agent_id,
            "nodeKey": self.node_key,
            "machineIp": self.machine_ip,
            "hostName": self.host_name,
            "pid": self.pid,
            "language": self.language,
            "frameworkName": self.framework_name,
        }


class ApplicationRegistrator:
    """Upload application registration metadata."""

    def __init__(self, external_api):
        self.external_api = external_api
        self._is_registered = False
        self._application_id: Optional[str] = None

    def register(self, app_info: Optional[ApplicationInfo] = None) -> bool:
        """Register the application if it has not been registered yet."""
        if self._is_registered:
            logger.info("Application already registered, skip")
            return True

        try:
            app_info = app_info or self._generate_app_info()
            success = self.external_api.upload_application_info(app_info.to_dict())
            if success:
                self._is_registered = True
                logger.info("Application registration succeeded: %s", app_info.application_name)
                return True
            logger.error("Application registration failed")
            return False
        except Exception as exc:
            logger.error("Application registration raised an exception: %s", exc)
            return False

    def _generate_app_info(self) -> ApplicationInfo:
        """Build application metadata using runtime environment."""
        app_name = self.external_api.app_name
        cluster_name = os.getenv("CLUSTER_NAME", "default")
        tenant_id = os.getenv("SIMULATOR_TENANT_ID", os.getenv("TENANT_ID", "1"))
        env_code = os.getenv("SIMULATOR_ENV_CODE", os.getenv("ENV_CODE", "test"))
        user_id = os.getenv("SIMULATOR_USER_ID", os.getenv("USER_ID", ""))
        host_name = get_host_name()
        machine_ip = get_local_address()
        pid = str(os.getpid())
        node_key = os.getenv("NODE_KEY", f"{app_name}:{self.external_api.agent_id}")

        description = (
            f"PyLinkAgent app={app_name}, host={host_name}, ip={machine_ip}, "
            f"pid={pid}, agentId={self.external_api.agent_id}"
        )

        return ApplicationInfo(
            application_name=app_name,
            application_desc=description,
            use_yn=0,
            access_status=0,
            switch_status="OPENED",
            node_num=1,
            agent_version=getattr(self.external_api, "agent_version", "1.0.0"),
            pradar_version=getattr(self.external_api, "simulator_version", "1.0.0"),
            cluster_name=cluster_name,
            tenant_id=tenant_id,
            env_code=env_code,
            user_id=user_id,
            agent_id=self.external_api.agent_id,
            node_key=node_key,
            machine_ip=machine_ip,
            host_name=host_name,
            pid=pid,
        )

    def is_registered(self) -> bool:
        """Return whether application registration succeeded."""
        return self._is_registered

    def get_application_id(self) -> Optional[str]:
        """Return the current application ID if known."""
        return self._application_id

    def sync_application_info(self) -> bool:
        """Upload a refreshed registration payload."""
        if not self._is_registered:
            logger.warning("Application has not been registered yet")
            return False

        try:
            app_info = self._generate_app_info()
            app_info.node_num = self._get_current_node_num() + 1
            success = self.external_api.upload_application_info(app_info.to_dict())
            if success:
                logger.info("Application info sync succeeded: %s", app_info.application_name)
                return True
            logger.error("Application info sync failed")
            return False
        except Exception as exc:
            logger.error("Application info sync raised an exception: %s", exc)
            return False

    def _get_current_node_num(self) -> int:
        """Return the current node count. This stays optimistic for now."""
        return 1


class ApplicationStatusReporter:
    """Report application access and configuration status."""

    def __init__(self, external_api):
        self.external_api = external_api
        self._error_map: Dict[str, Any] = {}

    def report_access_status(
        self, status: int = 0, error_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Upload application access status."""
        if error_info:
            self._error_map.update(error_info)
        return self.external_api.upload_access_status(self._error_map)

    def report_config_error(self, config_type: str, error_msg: str) -> bool:
        """Upload a configuration error payload."""
        error_info = {
            "configType": config_type,
            "errorMsg": error_msg,
            "timestamp": int(time.time()),
        }
        return self.report_access_status(status=3, error_info=error_info)

    def report_config_success(self, config_type: str) -> bool:
        """Upload a configuration success payload."""
        error_info = {
            f"{config_type}.status": "success",
            f"{config_type}.timestamp": int(time.time()),
        }
        return self.report_access_status(status=0, error_info=error_info)

    def clear_errors(self) -> None:
        """Clear accumulated access status details."""
        self._error_map.clear()
