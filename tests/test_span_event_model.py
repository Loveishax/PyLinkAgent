from pylinkagent.pradar import Pradar, get_event_store


def setup_function():
    Pradar.clear()
    get_event_store().clear()


def teardown_function():
    Pradar.clear()
    get_event_store().clear()


def test_root_trace_records_span_event():
    Pradar.start_trace("demo-app", "/orders", "GET")
    Pradar.set_span_semantics(
        middleware_name="HTTP",
        invoke_type="HTTP_SERVER",
        is_entry=True,
        is_server=True,
    )
    Pradar.set_request_summary("GET /orders")
    Pradar.set_result_code(200)

    Pradar.end_trace()

    spans = get_event_store().list_recent(limit=1)
    assert len(spans) == 1
    event = spans[0]
    assert event.trace_id
    assert event.invoke_id == "0"
    assert event.app_name == "demo-app"
    assert event.invoke_type == "HTTP_SERVER"
    assert event.middleware_name == "HTTP"
    assert event.request_summary == "GET /orders"
    assert event.result_code == "200"


def test_child_span_keeps_parent_relation():
    Pradar.start_trace("demo-app", "/entry", "POST")
    child = Pradar.start_child_span(
        service_name="example.com",
        method_name="GET /downstream",
        middleware_name="HTTP",
        invoke_type="HTTP_CLIENT",
        remote_ip="example.com",
        port=80,
        up_app_name="example.com",
    )

    assert child is not None
    Pradar.set_result_code(200)
    Pradar.end_trace()
    Pradar.end_trace()

    spans = get_event_store().list_recent(limit=2)
    assert spans[0].parent_invoke_id == "0"
    assert spans[0].invoke_id == "0.1"
    assert spans[0].invoke_type == "HTTP_CLIENT"
    assert spans[1].invoke_id == "0"
