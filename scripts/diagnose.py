#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent intranet diagnosis helper.

Usage:
  python scripts/diagnose.py
  python scripts/diagnose.py http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime
from typing import Any, Dict, List

import requests


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _safe_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return "unknown"


def _fetch_runtime_endpoint(base_url: str) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/debug/runtime"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


def _print_runtime_summary(snapshot: Dict[str, Any], title: str) -> None:
    print(f"\n[{title}]")
    print(
        "  running={running} app={app_name} agent={agent_id}".format(
            running=snapshot.get("running"),
            app_name=snapshot.get("app_name"),
            agent_id=snapshot.get("agent_id"),
        )
    )
    print(
        "  zk_running={zk_running} log_server_discovery_running={ls_running} log_server_count={count}".format(
            zk_running=snapshot.get("zk_running"),
            ls_running=snapshot.get("log_server_discovery_running"),
            count=snapshot.get("log_server_count"),
        )
    )
    selected = snapshot.get("selected_log_server") or {}
    if selected:
        print(
            "  selected_log_server={address} type={server_type} status={status}".format(
                address=selected.get("address") or selected.get("host"),
                server_type=selected.get("serverType"),
                status=selected.get("status"),
            )
        )
    recent_spans: List[Dict[str, Any]] = snapshot.get("recent_spans") or []
    print(f"  recent_spans={len(recent_spans)}")
    for item in recent_spans[-5:]:
        print(
            "    - {invoke_type}/{middleware_name} {service_name} {method_name} result={result_code} cost={cost_ms}".format(
                invoke_type=item.get("invoke_type", ""),
                middleware_name=item.get("middleware_name", ""),
                service_name=item.get("service_name", ""),
                method_name=item.get("method_name", ""),
                result_code=item.get("result_code", ""),
                cost_ms=item.get("cost_ms", 0),
            )
        )


def main() -> int:
    runtime_url = sys.argv[1] if len(sys.argv) > 1 else ""

    print("=" * 72)
    print("PyLinkAgent 联调诊断")
    print("=" * 72)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"平台: {sys.platform}")
    print(f"主机名: {socket.gethostname()}")
    print(f"本机IP: {_safe_local_ip()}")

    print("\n[环境变量]")
    for key in [
        "PYLINKAGENT_ENABLED",
        "MANAGEMENT_URL",
        "APP_NAME",
        "AGENT_ID",
        "AUTO_REGISTER_APP",
        "ZK_ENABLED",
        "REGISTER_NAME",
        "SIMULATOR_ZK_SERVERS",
        "SIMULATOR_ZK_SESSION_TIMEOUT_MS",
        "SIMULATOR_ZK_CONNECTION_TIMEOUT_MS",
        "ZK_SESSION_TIMEOUT_MS",
        "ZK_CONNECTION_TIMEOUT_MS",
        "SHADOW_ROUTING",
        "HTTP_SERVER_TRACING",
        "USER_APP_KEY",
        "TENANT_APP_KEY",
        "USER_ID",
        "ENV_CODE",
    ]:
        print(f"  {key}={os.getenv(key, '')}")

    print("\n[控制台基础连通性]")
    management_url = os.getenv("MANAGEMENT_URL", "").strip()
    if management_url:
        try:
            response = requests.get(management_url, timeout=5)
            print(f"  {management_url} -> HTTP {response.status_code}")
        except Exception as exc:
            print(f"  {management_url} -> FAIL: {exc}")
    else:
        print("  MANAGEMENT_URL 未设置")

    print("\n[本进程探针状态]")
    try:
        import pylinkagent

        snapshot = pylinkagent.get_runtime_snapshot()
        _print_runtime_summary(snapshot, "本进程快照摘要")
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"  无法获取本进程快照: {exc}")

    if runtime_url:
        print("\n[应用运行时快照]")
        try:
            payload = _fetch_runtime_endpoint(runtime_url)
            _print_runtime_summary(payload, "应用 /debug/runtime 摘要")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        except Exception as exc:
            print(f"  获取 {runtime_url}/debug/runtime 失败: {exc}")

    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
