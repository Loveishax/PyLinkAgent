"""
Runtime snapshot helpers for intranet diagnostics.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from .bootstrap import get_bootstrapper, is_running
from .pradar import PradarSwitcher, get_event_store, get_span_exporter
from .shadow import get_config_center


def _summarize_db_configs() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    config_center = get_config_center()
    for key, config in sorted(config_center.get_all_db_configs().items()):
        items.append(
            {
                "match_key": key,
                "datasource_name": config.datasource_name,
                "business_url": config.url,
                "shadow_url": config.shadow_url,
                "ds_type": config.ds_type,
                "enabled": config.enabled,
                "shadow_tables": dict(config.business_shadow_tables),
            }
        )
    return items


def get_runtime_snapshot() -> Dict[str, Any]:
    """Return a safe runtime snapshot for diagnostics."""
    bootstrapper = get_bootstrapper()
    config_fetcher = getattr(bootstrapper, "_config_fetcher", None) if bootstrapper else None
    external_api = getattr(bootstrapper, "_external_api", None) if bootstrapper else None
    zk_integration = getattr(bootstrapper, "_zk_integration", None) if bootstrapper else None
    span_uploader = getattr(bootstrapper, "_span_uploader", None) if bootstrapper else None
    config = config_fetcher.get_config() if config_fetcher else None
    config_center = get_config_center()
    db_configs = config_center.get_all_db_configs()
    redis_configs = config_center.get_all_redis_configs()
    es_configs = config_center.get_all_es_configs()
    kafka_configs = config_center.get_all_kafka_configs()
    recent_spans = [item.to_dict() for item in get_event_store().list_recent(limit=10)]
    log_servers = zk_integration.get_log_servers() if zk_integration else []
    selected_log_server = zk_integration.get_selected_log_server() if zk_integration else None
    uploader_status = span_uploader.get_status() if span_uploader else None
    preview_protocol = (
        uploader_status.get("protocol")
        if uploader_status and uploader_status.get("protocol")
        else "python-span-draft-v1"
    )

    return {
        "running": is_running(),
        "app_name": os.getenv("APP_NAME", "default-app"),
        "agent_id": os.getenv("AGENT_ID", f"pylinkagent-{os.getpid()}"),
        "management_url": getattr(external_api, "tro_web_url", os.getenv("MANAGEMENT_URL", "")),
        "register_name": os.getenv("REGISTER_NAME", "zookeeper"),
        "zk_enabled": os.getenv("ZK_ENABLED", "true").lower() == "true",
        "zk_running": bool(zk_integration and zk_integration.is_running()),
        "log_server_discovery_running": bool(
            zk_integration and zk_integration.is_log_server_discovery_running()
        ),
        "log_server_count": len(log_servers),
        "selected_log_server": selected_log_server,
        "log_servers": log_servers,
        "span_uploader": uploader_status,
        "auto_register_app": os.getenv("AUTO_REGISTER_APP", "true").lower() == "true",
        "shadow_routing_enabled": os.getenv("SHADOW_ROUTING", "true").lower() == "true",
        "http_server_tracing_enabled": os.getenv("HTTP_SERVER_TRACING", "true").lower() == "true",
        "cluster_test_switch_enabled": PradarSwitcher.is_cluster_test_enabled(),
        "whitelist_switch_enabled": PradarSwitcher.is_white_list_switch_on(),
        "has_pressure_request": PradarSwitcher.has_pressure_request(),
        "config_fetcher_running": bool(config_fetcher and config_fetcher.is_running()),
        "shadow_db_config_count": len(db_configs),
        "shadow_redis_config_count": len(redis_configs),
        "shadow_es_config_count": len(es_configs),
        "shadow_kafka_config_count": len(kafka_configs),
        "url_whitelist_count": len(config.url_whitelist) if config else 0,
        "rpc_whitelist_count": len(config.rpc_whitelist) if config else 0,
        "mq_whitelist_count": len(config.mq_whitelist) if config else 0,
        "db_mappings": _summarize_db_configs(),
        "recent_spans": recent_spans,
        "span_export_preview": get_span_exporter().build_payload(
            limit=5,
            events=get_event_store().list_recent(limit=5),
            protocol=preview_protocol,
        ),
    }
