"""
Minimal background span uploader.

This uploader is intentionally conservative:
- disabled by default
- uses the local SpanEvent exporter payload
- does not claim Java collector compatibility yet
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import json
from typing import Any, Dict, List, Optional

import requests

from .events import SpanEvent, get_event_store
from .exporter import SpanEventExporter, get_span_exporter


logger = logging.getLogger(__name__)


class SpanUploader:
    """Upload locally collected spans to a configured HTTP endpoint."""

    def __init__(self, zk_integration=None, interval: Optional[int] = None):
        self.zk_integration = zk_integration
        self.interval = interval or int(os.getenv("PYLINKAGENT_SPAN_UPLOAD_INTERVAL", "5"))
        self.batch_size = int(os.getenv("PYLINKAGENT_SPAN_UPLOAD_BATCH_SIZE", "50"))
        self.timeout = int(os.getenv("PYLINKAGENT_SPAN_UPLOAD_TIMEOUT", "5"))
        self.upload_path = os.getenv("PYLINKAGENT_SPAN_UPLOAD_PATH", "/log/link/upload")
        self.health_path = os.getenv("PYLINKAGENT_SPAN_UPLOAD_HEALTH_PATH", "/health")
        self.explicit_url = os.getenv("PYLINKAGENT_SPAN_UPLOAD_URL", "").strip()
        self.protocol = os.getenv(
            "PYLINKAGENT_SPAN_UPLOAD_PROTOCOL",
            SpanEventExporter.PYTHON_DRAFT_PROTOCOL,
        ).strip()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False
        self._lock = threading.Lock()
        self._last_uploaded_event_id = 0
        self._last_target = ""
        self._last_error = ""
        self._last_uploaded_count = 0

    def start(self) -> bool:
        with self._lock:
            if self._is_running:
                return True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="pylinkagent-span-uploader",
                daemon=True,
            )
            self._health_check_target()
            self._thread.start()
            self._is_running = True
            logger.info("Span uploader started")
            return True

    def stop(self) -> None:
        with self._lock:
            if not self._is_running:
                return
            self._stop_event.set()
            thread = self._thread
            self._thread = None
            self._is_running = False
        if thread:
            thread.join(timeout=self.timeout + 1)
        logger.info("Span uploader stopped")

    def is_running(self) -> bool:
        return self._is_running

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._is_running,
            "explicit_url": self.explicit_url,
            "upload_path": self.upload_path,
            "last_uploaded_event_id": self._last_uploaded_event_id,
            "last_uploaded_count": self._last_uploaded_count,
            "last_target": self._last_target,
            "last_error": self._last_error,
            "protocol": self.protocol,
        }

    def flush_once(self) -> bool:
        target = self._resolve_target_url()
        if not target:
            self._last_error = "no upload target available"
            return False

        events = get_event_store().list_after(self._last_uploaded_event_id, limit=self.batch_size)
        if not events:
            self._last_error = ""
            self._last_target = target
            self._last_uploaded_count = 0
            return True

        payload = self._build_upload_payload(events)
        body, headers = self._build_http_request(payload, events)
        headers["time"] = str(payload["generated_at_ms"])
        headers["hostIp"] = self._safe_local_ip()
        response = requests.post(target, data=body, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        self._assert_upload_success(response)

        self._last_uploaded_event_id = events[-1].event_id
        self._last_target = target
        self._last_uploaded_count = len(events)
        self._last_error = ""
        return True

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval):
            try:
                self.flush_once()
            except Exception as exc:
                self._last_error = str(exc)
                logger.debug("Span uploader flush failed: %s", exc)

    def _resolve_target_url(self) -> str:
        if self.explicit_url:
            return self.explicit_url

        if self.zk_integration:
            selected = self.zk_integration.get_selected_log_server() or {}
            address = selected.get("address") or ""
            if address:
                if address.startswith("http://") or address.startswith("https://"):
                    return address.rstrip("/") + self.upload_path
                return f"http://{address}{self.upload_path}"

        return ""

    def _build_upload_payload(self, events: List[SpanEvent]) -> Dict[str, Any]:
        payload = get_span_exporter().build_payload(events=events, protocol=self.protocol)
        payload["target_source"] = "explicit_url" if self.explicit_url else "zk_log_server"
        return payload

    def _resolve_data_type(self) -> str:
        if self.protocol == SpanEventExporter.JAVA_HTTP_TRACE_LOG_DRAFT_PROTOCOL:
            return str(SpanEventExporter.TRACE_LOG_DATA_TYPE)
        if self.protocol == SpanEventExporter.JAVA_COLLECTOR_DRAFT_PROTOCOL:
            return "collector-trace-draft"
        return "python-span"

    def _resolve_version(self) -> str:
        if self.protocol == SpanEventExporter.JAVA_HTTP_TRACE_LOG_DRAFT_PROTOCOL:
            return str(SpanEventExporter.TRACE_LOG_VERSION)
        return self.protocol

    def _build_http_request(
        self,
        payload: Dict[str, Any],
        events: List[SpanEvent],
    ) -> tuple[bytes, Dict[str, str]]:
        headers = {
            "Content-Type": "application/json",
            "dataType": self._resolve_data_type(),
            "version": self._resolve_version(),
        }
        if self.protocol == SpanEventExporter.JAVA_HTTP_TRACE_LOG_DRAFT_PROTOCOL:
            return get_span_exporter().build_http_trace_log_bytes(events), headers
        return json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers

    def _assert_upload_success(self, response) -> None:
        if self.protocol != SpanEventExporter.JAVA_HTTP_TRACE_LOG_DRAFT_PROTOCOL:
            return
        try:
            payload = response.json()
        except Exception:
            return
        response_code = payload.get("responseCode")
        if response_code not in (0, 200):
            raise ValueError(f"upload rejected, responseCode={response_code}, body={payload}")

    def _health_check_target(self) -> bool:
        target = self._resolve_health_url()
        if not target:
            return False
        try:
            response = requests.get(target, timeout=self.timeout)
            response.raise_for_status()
            return True
        except Exception as exc:
            self._last_error = f"health check failed: {exc}"
            logger.debug("Span uploader health check failed: %s", exc)
            return False

    def _resolve_health_url(self) -> str:
        if self.explicit_url:
            if self.explicit_url.endswith(self.upload_path):
                return self.explicit_url[: -len(self.upload_path)] + self.health_path
            return self.explicit_url.rstrip("/") + self.health_path

        if self.zk_integration:
            selected = self.zk_integration.get_selected_log_server() or {}
            address = selected.get("address") or ""
            if address:
                if address.startswith("http://") or address.startswith("https://"):
                    return address.rstrip("/") + self.health_path
                return f"http://{address}{self.health_path}"
        return ""

    @staticmethod
    def _safe_local_ip() -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except Exception:
            return "unknown"
