from unittest.mock import Mock

from pylinkagent.pradar import Pradar, get_event_store
from pylinkagent.runtime_snapshot import get_runtime_snapshot


def setup_function():
    Pradar.clear()
    get_event_store().clear()


def teardown_function():
    Pradar.clear()
    get_event_store().clear()


def test_runtime_snapshot_contains_span_preview(monkeypatch):
    fake_zk = Mock()
    fake_zk.is_running.return_value = True
    fake_zk.is_log_server_discovery_running.return_value = True
    fake_zk.get_log_servers.return_value = [
        {"address": "10.0.0.1:9000", "serverType": "http", "status": "online"}
    ]
    fake_zk.get_selected_log_server.return_value = {
        "address": "10.0.0.1:9000",
        "serverType": "http",
        "status": "online",
    }
    fake_bootstrapper = Mock()
    fake_bootstrapper._config_fetcher = None
    fake_bootstrapper._external_api = None
    fake_bootstrapper._zk_integration = fake_zk
    fake_bootstrapper._span_uploader = Mock()
    fake_bootstrapper._span_uploader.get_status.return_value = {
        "running": True,
        "last_target": "http://10.0.0.1:9000/log/link/upload",
        "last_error": "",
    }

    monkeypatch.setattr("pylinkagent.runtime_snapshot.get_bootstrapper", lambda: fake_bootstrapper)
    monkeypatch.setattr("pylinkagent.runtime_snapshot.is_running", lambda: True)

    Pradar.start_trace("demo-app", "/orders", "GET")
    Pradar.set_span_semantics(middleware_name="HTTP", invoke_type="HTTP_SERVER")
    Pradar.set_result_code(200)
    Pradar.end_trace()

    snapshot = get_runtime_snapshot()

    assert snapshot["log_server_discovery_running"] is True
    assert snapshot["log_server_count"] == 1
    assert snapshot["selected_log_server"]["address"] == "10.0.0.1:9000"
    assert len(snapshot["recent_spans"]) == 1
    assert snapshot["span_export_preview"]["span_count"] == 1
    assert snapshot["span_uploader"]["running"] is True
