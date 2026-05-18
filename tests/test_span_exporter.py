from pylinkagent.pradar import Pradar, get_event_store, get_span_exporter
from pylinkagent.pradar.exporter import SpanEventExporter


def setup_function():
    Pradar.clear()
    get_event_store().clear()


def teardown_function():
    Pradar.clear()
    get_event_store().clear()


def test_span_exporter_builds_payload_from_recent_events():
    Pradar.start_trace("demo-app", "/orders", "GET")
    Pradar.set_span_semantics(
        middleware_name="HTTP",
        invoke_type="HTTP_SERVER",
        is_entry=True,
        is_server=True,
    )
    Pradar.set_result_code(200)
    Pradar.end_trace()

    payload = get_span_exporter().build_payload(limit=10)

    assert payload["app_name"] == "default-app" or payload["app_name"]
    assert payload["span_count"] == 1
    assert len(payload["spans"]) == 1
    assert payload["spans"][0]["invoke_type"] == "HTTP_SERVER"
    assert payload["spans"][0]["result_code"] == "200"


def test_span_exporter_builds_java_collector_draft_payload():
    Pradar.start_trace("demo-app", "/orders", "GET")
    Pradar.set_span_semantics(
        middleware_name="HTTP",
        invoke_type="HTTP_SERVER",
        is_entry=True,
        is_server=True,
    )
    Pradar.set_remote_endpoint("10.0.0.8", 8080)
    Pradar.set_request_summary("GET /orders")
    Pradar.set_response_summary("status=200")
    Pradar.set_result_code(200)
    Pradar.end_trace()

    payload = get_span_exporter().build_payload(
        protocol=SpanEventExporter.JAVA_COLLECTOR_DRAFT_PROTOCOL
    )

    assert payload["protocol"] == SpanEventExporter.JAVA_COLLECTOR_DRAFT_PROTOCOL
    assert "trace_data" in payload
    assert "trace_payload_data" in payload
    assert len(payload["trace_data"]) == 1
    assert len(payload["trace_payload_data"]) == 1
    trace_data = payload["trace_data"][0]
    trace_payload = payload["trace_payload_data"][0]
    assert trace_data["invokeType"] == 1
    assert trace_data["entrance"] is True
    assert trace_data["server"] is True
    assert trace_data["remoteIp"] == "10.0.0.8"
    assert trace_payload["request"] == "GET /orders"
    assert trace_payload["response"] == "status=200"


def test_span_exporter_builds_java_http_trace_log_bytes():
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

    events = get_event_store().list_recent()
    body = get_span_exporter().build_http_trace_log_bytes(events).decode("utf-8")

    assert body.endswith("\r\n")
    assert "demo-app" in body
    assert "GET /orders" in body
    assert "status=200" in body
