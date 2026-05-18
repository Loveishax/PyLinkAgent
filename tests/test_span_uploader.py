from unittest.mock import Mock

from pylinkagent.pradar import Pradar, get_event_store
from pylinkagent.pradar.exporter import SpanEventExporter
from pylinkagent.pradar.uploader import SpanUploader


def setup_function():
    Pradar.clear()
    get_event_store().clear()


def teardown_function():
    Pradar.clear()
    get_event_store().clear()


def _append_http_span():
    Pradar.start_trace("demo-app", "/orders", "GET")
    Pradar.set_span_semantics(
        middleware_name="HTTP",
        invoke_type="HTTP_SERVER",
        is_entry=True,
        is_server=True,
    )
    Pradar.set_request_summary("GET /orders")
    Pradar.set_response_summary("status=200")
    Pradar.set_result_code(200)
    Pradar.end_trace()


def test_event_store_supports_incremental_reads():
    _append_http_span()
    _append_http_span()

    recent = get_event_store().list_recent()
    assert recent[0].event_id == 1
    assert recent[1].event_id == 2

    incremental = get_event_store().list_after(1)
    assert len(incremental) == 1
    assert incremental[0].event_id == 2


def test_span_uploader_flushes_to_explicit_url(monkeypatch):
    _append_http_span()
    observed = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, data=None, headers=None, timeout=None):
        observed["url"] = url
        observed["data"] = data
        observed["headers"] = headers
        observed["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("PYLINKAGENT_SPAN_UPLOAD_URL", "http://collector.example/upload")
    monkeypatch.setattr("pylinkagent.pradar.uploader.requests.post", fake_post)

    uploader = SpanUploader()
    assert uploader.flush_once() is True

    assert observed["url"] == "http://collector.example/upload"
    assert b'"protocol": "python-span-draft-v1"' in observed["data"]
    assert b'"span_count": 1' in observed["data"]
    assert uploader.get_status()["last_uploaded_event_id"] == 1


def test_span_uploader_uses_zk_selected_log_server(monkeypatch):
    _append_http_span()
    observed = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, data=None, headers=None, timeout=None):
        observed["url"] = url
        return FakeResponse()

    monkeypatch.delenv("PYLINKAGENT_SPAN_UPLOAD_URL", raising=False)
    monkeypatch.setattr("pylinkagent.pradar.uploader.requests.post", fake_post)

    fake_zk = Mock()
    fake_zk.get_selected_log_server.return_value = {
        "address": "10.0.0.8:9099",
        "serverType": "http",
        "status": "online",
    }

    uploader = SpanUploader(fake_zk)
    assert uploader.flush_once() is True
    assert observed["url"] == "http://10.0.0.8:9099/log/link/upload"


def test_span_uploader_switches_to_java_collector_draft(monkeypatch):
    _append_http_span()
    observed = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, data=None, headers=None, timeout=None):
        observed["url"] = url
        observed["data"] = data
        observed["headers"] = headers
        return FakeResponse()

    monkeypatch.setenv("PYLINKAGENT_SPAN_UPLOAD_URL", "http://collector.example/upload")
    monkeypatch.setenv(
        "PYLINKAGENT_SPAN_UPLOAD_PROTOCOL",
        SpanEventExporter.JAVA_COLLECTOR_DRAFT_PROTOCOL,
    )
    monkeypatch.setattr("pylinkagent.pradar.uploader.requests.post", fake_post)

    uploader = SpanUploader()
    assert uploader.flush_once() is True

    assert observed["headers"]["dataType"] == "collector-trace-draft"
    assert observed["headers"]["version"] == SpanEventExporter.JAVA_COLLECTOR_DRAFT_PROTOCOL
    assert b'"trace_data"' in observed["data"]
    assert b'"trace_payload_data"' in observed["data"]


def test_span_uploader_supports_java_http_trace_log_draft(monkeypatch):
    _append_http_span()
    observed = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"responseCode": 0}

    def fake_get(url, timeout=None):
        observed["health_url"] = url
        return FakeResponse()

    def fake_post(url, data=None, headers=None, timeout=None):
        observed["url"] = url
        observed["data"] = data
        observed["headers"] = headers
        return FakeResponse()

    monkeypatch.setenv(
        "PYLINKAGENT_SPAN_UPLOAD_URL",
        "http://collector.example/log/link/upload",
    )
    monkeypatch.setenv(
        "PYLINKAGENT_SPAN_UPLOAD_PROTOCOL",
        SpanEventExporter.JAVA_HTTP_TRACE_LOG_DRAFT_PROTOCOL,
    )
    monkeypatch.setattr("pylinkagent.pradar.uploader.requests.get", fake_get)
    monkeypatch.setattr("pylinkagent.pradar.uploader.requests.post", fake_post)

    uploader = SpanUploader()
    uploader.start()
    try:
        assert uploader.flush_once() is True
    finally:
        uploader.stop()

    assert observed["health_url"] == "http://collector.example/health"
    assert observed["headers"]["dataType"] == "1"
    assert observed["headers"]["version"] == "17"
    assert isinstance(observed["data"], bytes)
    assert b"|/orders|GET|200|" in observed["data"]
