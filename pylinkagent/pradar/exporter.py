"""
Span payload builder for diagnostics and future collector upload.
"""

from __future__ import annotations

import os
import socket
import time
from typing import Any, Dict, List, Optional

from .events import SpanEvent, get_event_store


class SpanEventExporter:
    """Build batch payloads from recent local span events."""

    PYTHON_DRAFT_PROTOCOL = "python-span-draft-v1"
    JAVA_COLLECTOR_DRAFT_PROTOCOL = "java-collector-draft-v1"
    JAVA_HTTP_TRACE_LOG_DRAFT_PROTOCOL = "java-http-trace-log-draft-v1"
    TRACE_LOG_DATA_TYPE = 1
    TRACE_LOG_VERSION = 17

    def build_payload(
        self,
        limit: int = 50,
        events: Optional[List[SpanEvent]] = None,
        protocol: str = PYTHON_DRAFT_PROTOCOL,
    ) -> Dict[str, Any]:
        items = events if events is not None else get_event_store().list_recent(limit=limit)
        payload = {
            "generated_at_ms": int(time.time() * 1000),
            "agent_id": os.getenv("AGENT_ID", f"pylinkagent-{os.getpid()}"),
            "app_name": os.getenv("APP_NAME", "default-app"),
            "host_name": socket.gethostname(),
            "env_code": os.getenv("ENV_CODE", "test"),
            "tenant_app_key": os.getenv("TENANT_APP_KEY", ""),
            "user_id": os.getenv("USER_ID", ""),
            "protocol": protocol,
            "span_count": len(items),
        }
        if protocol == self.JAVA_COLLECTOR_DRAFT_PROTOCOL:
            payload["trace_data"] = [self._to_java_collector_trace_data(item) for item in items]
            payload["trace_payload_data"] = [
                self._to_java_collector_trace_payload(item) for item in items
            ]
        elif protocol == self.JAVA_HTTP_TRACE_LOG_DRAFT_PROTOCOL:
            payload["data_type"] = self.TRACE_LOG_DATA_TYPE
            payload["version"] = self.TRACE_LOG_VERSION
            payload["trace_lines"] = [self._to_java_trace_log_line(item) for item in items]
        else:
            payload["spans"] = [item.to_dict() for item in items]
        return payload

    def _to_java_collector_trace_data(self, item: SpanEvent) -> Dict[str, Any]:
        return {
            "traceId": item.trace_id,
            "timestamp": item.start_time_ms,
            "agentId": item.agent_id or os.getenv("AGENT_ID", f"pylinkagent-{os.getpid()}"),
            "invokeId": item.invoke_id,
            "invokeType": self._map_invoke_type(item.invoke_type),
            "appName": item.app_name or os.getenv("APP_NAME", "default-app"),
            "cost": int(item.cost_ms),
            "middlewareName": item.middleware_name,
            "serviceName": item.service_name,
            "methodName": item.method_name,
            "resultCode": item.result_code,
            "pressureTest": item.cluster_test,
            "debugTest": False,
            "entrance": item.is_entry,
            "server": item.is_server,
            "upAppName": item.up_app_name,
            "remoteIp": item.remote_ip,
            "port": int(item.port or 0),
            "eventId": item.event_id,
        }

    def _to_java_collector_trace_payload(self, item: SpanEvent) -> Dict[str, Any]:
        return {
            "traceId": item.trace_id,
            "timestamp": item.start_time_ms,
            "agentId": item.agent_id or os.getenv("AGENT_ID", f"pylinkagent-{os.getpid()}"),
            "invokeId": item.invoke_id,
            "invokeType": self._map_invoke_type(item.invoke_type),
            "appName": item.app_name or os.getenv("APP_NAME", "default-app"),
            "middlewareName": item.middleware_name,
            "serviceName": item.service_name,
            "methodName": item.method_name,
            "pressureTest": item.cluster_test,
            "entrance": item.is_entry,
            "server": item.is_server,
            "request": item.request_summary,
            "response": item.response_summary,
            "callbackMsg": item.error_message,
            "requestSize": 0,
            "responseSize": 0,
            "rpcContent": self._build_rpc_content(item),
            "ext": "",
            "eventId": item.event_id,
        }

    @staticmethod
    def _build_rpc_content(item: SpanEvent) -> str:
        return (
            f"tenantAppKey={item.tenant_app_key};"
            f"envCode={item.env_code};"
            f"userId={item.user_id};"
            f"parentInvokeId={item.parent_invoke_id}"
        )

    @staticmethod
    def _map_invoke_type(invoke_type: str) -> int:
        mapping = {
            "HTTP_SERVER": 1,
            "HTTP_CLIENT": 2,
            "DB": 3,
            "CACHE": 4,
            "MQ_PRODUCER": 5,
            "MQ_CONSUMER": 6,
        }
        return mapping.get(invoke_type, 0)

    def build_http_trace_log_bytes(self, events: List[SpanEvent]) -> bytes:
        lines = [self._to_java_trace_log_line(item) for item in events]
        if not lines:
            return b""
        return "".join(lines).encode("utf-8")

    def _to_java_trace_log_line(self, item: SpanEvent) -> str:
        fields: List[str] = [
            self._safe_text(item.trace_id),
            str(item.start_time_ms),
        ]
        if item.tenant_app_key or item.env_code or item.user_id:
            fields.extend(
                [
                    self._safe_text(item.tenant_app_key),
                    self._safe_text(item.env_code),
                    self._safe_text(item.user_id),
                ]
            )
        fields.extend(
            [
                self._safe_text(item.agent_id or os.getenv("AGENT_ID", f"pylinkagent-{os.getpid()}")),
                self._safe_text(item.invoke_id),
                str(self._map_invoke_type(item.invoke_type)),
                self._safe_text(item.app_name or os.getenv("APP_NAME", "default-app")),
                str(int(item.cost_ms)),
                self._safe_text(item.middleware_name),
                self._safe_text(item.service_name),
                self._safe_text(item.method_name),
                self._safe_text(item.result_code),
                self._safe_text(item.request_summary),
                self._safe_text(item.response_summary),
                self._combine_fields(
                    "1" if item.cluster_test else "0",
                    "0",
                    "1" if item.is_entry else "0",
                    "1" if item.is_server else "0",
                ),
                self._safe_text(item.error_message),
                "#1",
                "@" + self._combine_fields("", "", ""),
                "@"
                + self._combine_fields(
                    item.up_app_name,
                    item.remote_ip,
                    item.port,
                    0,
                    0,
                ),
            ]
        )
        return "|".join(fields) + "\r\n"

    @staticmethod
    def _combine_fields(*values: Any) -> str:
        return "~".join(SpanEventExporter._safe_text(value) for value in values)

    @staticmethod
    def _safe_text(value: Any) -> str:
        text = "" if value is None else str(value)
        text = text.replace("\r\n", "\t").replace("\n", "\t").replace("\r", "\t")
        return text.replace("|", "\\")


_exporter: Optional[SpanEventExporter] = None


def get_span_exporter() -> SpanEventExporter:
    global _exporter
    if _exporter is None:
        _exporter = SpanEventExporter()
    return _exporter
