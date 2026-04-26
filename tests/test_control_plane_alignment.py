import json
import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.application_register import ApplicationRegistrator
from pylinkagent.controller.external_api import ExternalAPI
from pylinkagent.controller.heartbeat import HeartbeatReporter
from pylinkagent.zookeeper.config import ZkConfig


def test_application_registration_payload_contains_runtime_metadata(monkeypatch):
    monkeypatch.setenv("SIMULATOR_ENV_CODE", "fat")
    monkeypatch.setenv("SIMULATOR_TENANT_ID", "11")
    monkeypatch.setenv("SIMULATOR_USER_ID", "42")

    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="demo-app",
        agent_id="10.0.0.1-1000",
    )
    registrator = ApplicationRegistrator(api)

    app_info = registrator._generate_app_info().to_dict()

    assert app_info["applicationName"] == "demo-app"
    assert app_info["agentId"] == "10.0.0.1-1000"
    assert app_info["nodeKey"] == "demo-app:10.0.0.1-1000"
    assert app_info["envCode"] == "fat"
    assert app_info["tenantId"] == "11"
    assert app_info["userId"] == "42"
    assert app_info["language"] == "PYTHON"
    assert app_info["frameworkName"] == "PyLinkAgent"
    assert "agentId=10.0.0.1-1000" in app_info["applicationDesc"]


def test_http_heartbeat_uses_plain_agent_id_and_uppercase_error_status():
    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="demo-app",
        agent_id="10.0.0.1-1000",
    )
    api._initialized = True
    api.agent_version = "2.1.0"
    api.simulator_version = "2.1.0"

    reporter = HeartbeatReporter(api, interval=1)
    reporter.set_agent_error("bootstrap failed")
    reporter.set_simulator_error("simulator failed")

    request = reporter._build_heart_request()

    assert request.agent_id == "10.0.0.1-1000"
    assert request.agent_status == "ERROR"
    assert request.agent_error_info == ["bootstrap failed"]
    assert request.simulator_status == "ERROR"
    assert request.simulator_error_info == "simulator failed"
    assert request.agent_version == "2.1.0"


def test_zk_payload_uses_full_agent_id_and_python_runtime_fields():
    config = ZkConfig(
        app_name="demo-app",
        agent_id="10.0.0.1-1000",
        env_code="fat",
        user_id="42",
        tenant_app_key="tenant-key",
        agent_version="2.1.0",
        simulator_version="2.1.0",
    )

    payload = json.loads(config.to_heartbeat_data().decode("utf-8"))

    assert payload["name"] == "demo-app"
    assert payload["agentId"] == "10.0.0.1-1000&fat:42:tenant-key"
    assert payload["agentLanguage"] == "PYTHON"
    assert payload["agentVersion"] == "2.1.0"
    assert payload["simulatorVersion"] == "2.1.0"
    assert payload["jdkVersion"].startswith("Python ")
    assert payload["jdk"] == payload["jdkVersion"]
    assert payload["jvmArgsCheck"] == "PASS"
