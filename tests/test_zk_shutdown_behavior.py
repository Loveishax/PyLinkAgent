import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.zk_integration import ZKIntegration
from pylinkagent.zookeeper.config import ZkConfig


def test_zk_config_reads_timeout_envs(monkeypatch):
    monkeypatch.setenv("SIMULATOR_ZK_CONNECTION_TIMEOUT_MS", "15000")
    monkeypatch.setenv("SIMULATOR_ZK_SESSION_TIMEOUT_MS", "12000")

    config = ZkConfig.from_env_and_file()

    assert config.connection_timeout_ms == 15000
    assert config.session_timeout_ms == 12000


def test_zk_config_ignores_invalid_timeout_envs(monkeypatch):
    monkeypatch.setenv("SIMULATOR_ZK_CONNECTION_TIMEOUT_MS", "invalid")
    monkeypatch.setenv("SIMULATOR_ZK_SESSION_TIMEOUT_MS", "still-invalid")

    config = ZkConfig.from_env_and_file()

    assert config.connection_timeout_ms == 60000
    assert config.session_timeout_ms == 60000


def test_zk_shutdown_removes_cached_client(monkeypatch):
    config = ZkConfig(zk_servers="127.0.0.1:2181", app_name="demo-app", agent_id="agent-1")
    integration = ZKIntegration(config)
    integration._client = object()
    integration._heartbeat_manager = object()
    integration._is_initialized = True
    integration._is_running = True

    calls = []

    def fake_remove_client(arg):
        calls.append(arg.zk_servers)

    class DummyHeartbeatManager:
        def stop(self):
            calls.append("heartbeat-stopped")

    integration._heartbeat_manager = DummyHeartbeatManager()

    monkeypatch.setattr(
        "pylinkagent.controller.zk_integration.ZkClientFactory.remove_client",
        fake_remove_client,
    )

    integration.shutdown()

    assert calls == ["heartbeat-stopped", "127.0.0.1:2181"]
    assert integration._client is None
    assert integration._heartbeat_manager is None
    assert integration.is_initialized() is False
    assert integration.is_running() is False
