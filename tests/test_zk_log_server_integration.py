from unittest.mock import Mock

from pylinkagent.controller.zk_integration import ZKIntegration
from pylinkagent.zookeeper.config import ZkConfig


def test_zk_integration_initializes_log_server_discovery(monkeypatch):
    config = ZkConfig(zk_servers="127.0.0.1:2181", app_name="demo-app", agent_id="agent-1")
    fake_client = Mock()
    fake_client.connect.return_value = True

    fake_heartbeat = Mock()
    fake_heartbeat.initialize.return_value = True
    fake_heartbeat.start.return_value = True

    fake_discovery = Mock()
    fake_discovery.initialize.return_value = True
    fake_discovery.start.return_value = True
    fake_discovery.get_servers.return_value = []

    monkeypatch.setattr("pylinkagent.controller.zk_integration.get_heartbeat_manager", lambda cfg: fake_heartbeat)
    monkeypatch.setattr("pylinkagent.controller.zk_integration.get_log_server_discovery", lambda cfg: fake_discovery)

    integration = ZKIntegration(config)

    assert integration.initialize(fake_client) is True
    assert integration.start() is True
    assert integration.is_log_server_discovery_running() is True
    fake_discovery.initialize.assert_called_once_with(fake_client)
    fake_discovery.start.assert_called_once()

    integration.shutdown()
