"""
ZooKeeper integration for PyLinkAgent.

This module wires the heartbeat manager into the bootstrap lifecycle and keeps
the shutdown path close to the Java agent: stop the heartbeat node first, then
close the ZooKeeper client session.
"""

import logging
import os
import threading
from typing import Callable, Optional

from ..zookeeper import (
    AgentStatus,
    ZkClient,
    ZkClientFactory,
    ZkConfig,
    ZkHeartbeatManager,
    create_client,
    get_config,
    get_heartbeat_manager,
    get_log_server_discovery,
    LogServerSelector,
    reset_heartbeat_manager,
    reset_log_server_discovery,
)

logger = logging.getLogger(__name__)


class ZKIntegration:
    """Manage the ZooKeeper client and heartbeat lifecycle."""

    def __init__(self, config: Optional[ZkConfig] = None):
        self.config = config or get_config()
        self._client: Optional[ZkClient] = None
        self._heartbeat_manager: Optional[ZkHeartbeatManager] = None
        self._log_server_discovery = None
        self._log_server_selector: Optional[LogServerSelector] = None
        self._is_initialized = False
        self._is_running = False
        self._lock = threading.Lock()
        self._status_callbacks: list[Callable[[str], None]] = []

    def initialize(self, client: Optional[ZkClient] = None) -> bool:
        """Create the ZK client and initialize the heartbeat manager."""
        with self._lock:
            if self._is_initialized:
                logger.warning("ZK integration already initialized")
                return True

            try:
                logger.info("Initializing ZK integration: %s", self.config.zk_servers)

                self._client = client or create_client(self.config)
                if not self._client.connect():
                    logger.error("Failed to connect to ZooKeeper")
                    return False

                self._heartbeat_manager = get_heartbeat_manager(self.config)
                if not self._heartbeat_manager.initialize(self._client):
                    logger.error("Failed to initialize heartbeat manager")
                    return False

                if os.getenv("ZK_LOG_SERVER_DISCOVERY", "true").lower() == "true":
                    self._log_server_discovery = get_log_server_discovery(self.config)
                    if self._log_server_discovery and self._log_server_discovery.initialize(self._client):
                        self._log_server_selector = LogServerSelector(self._log_server_discovery)
                    else:
                        logger.warning("Failed to initialize ZK log server discovery")
                        self._log_server_discovery = None
                        self._log_server_selector = None

                self._is_initialized = True
                logger.info("ZK integration initialized")
                return True
            except Exception as exc:
                logger.error("Failed to initialize ZK integration: %s", exc)
                return False

    def start(self) -> bool:
        """Start the heartbeat node management."""
        with self._lock:
            if not self._is_initialized:
                logger.error("ZK integration is not initialized")
                return False

            if self._is_running:
                logger.warning("ZK heartbeat already started")
                return True

            try:
                if self._heartbeat_manager and self._heartbeat_manager.start():
                    if self._log_server_discovery:
                        self._log_server_discovery.start()
                    self._is_running = True
                    logger.info("ZK heartbeat started")
                    return True
                logger.error("Failed to start ZK heartbeat")
                return False
            except Exception as exc:
                logger.error("Failed to start ZK heartbeat: %s", exc)
                return False

    def stop(self) -> None:
        """Stop the heartbeat node and keep the client session for shutdown."""
        with self._lock:
            if not self._is_running:
                return

            try:
                self._is_running = False
                if self._heartbeat_manager:
                    self._heartbeat_manager.stop()
                if self._log_server_discovery:
                    self._log_server_discovery.stop()
                logger.info("ZK heartbeat stopped")
            except Exception as exc:
                logger.error("Failed to stop ZK heartbeat: %s", exc)

    def shutdown(self) -> None:
        """Fully close the ZK integration and release the cached client."""
        self.stop()

        with self._lock:
            try:
                if self._client:
                    ZkClientFactory.remove_client(self.config)
                    self._client = None

                self._heartbeat_manager = None
                if self._log_server_discovery:
                    self._log_server_discovery.stop()
                self._log_server_discovery = None
                self._log_server_selector = None
                reset_heartbeat_manager()
                reset_log_server_discovery()
                self._is_initialized = False
                self._is_running = False
                logger.info("ZK integration closed")
            except Exception as exc:
                logger.error("Failed to close ZK integration: %s", exc)

    def update_status(self, status: AgentStatus, error_msg: str = "") -> None:
        """Update the agent status payload stored in the heartbeat node."""
        if not self._is_running or not self._heartbeat_manager:
            logger.warning("ZK heartbeat is not running, status update skipped")
            return

        self._heartbeat_manager.update_status(status, error_msg)
        logger.info("ZK agent status updated: %s", status.value)

    def set_simulator_info(
        self,
        service: str,
        port: int,
        md5: str = "",
        jars: Optional[list] = None,
    ) -> None:
        """Refresh the heartbeat payload with simulator metadata."""
        if not self._heartbeat_manager:
            logger.warning("Heartbeat manager is not initialized")
            return

        self._heartbeat_manager.set_simulator_info(service, port, md5, jars)
        self._heartbeat_manager.refresh()
        logger.info("Simulator info updated: service=%s, port=%s", service, port)

    def add_status_callback(self, callback: Callable[[str], None]) -> None:
        """Register a status change listener."""
        self._status_callbacks.append(callback)
        if self._heartbeat_manager:
            self._heartbeat_manager.add_status_listener(callback)

    def is_running(self) -> bool:
        """Return whether the heartbeat manager is currently running."""
        return self._is_running

    def is_initialized(self) -> bool:
        """Return whether the integration has been initialized."""
        return self._is_initialized

    def get_log_servers(self) -> list[dict]:
        """Return discovered log servers for diagnostics."""
        if not self._log_server_discovery:
            return []
        return [item.to_dict() for item in self._log_server_discovery.get_servers()]

    def get_selected_log_server(self) -> Optional[dict]:
        """Return the preferred log server for diagnostics."""
        if not self._log_server_selector:
            return None
        server = self._log_server_selector.select()
        return server.to_dict() if server else None

    def is_log_server_discovery_running(self) -> bool:
        return bool(self._log_server_discovery and self._is_running)


_global_integration: Optional[ZKIntegration] = None
_integration_lock = threading.Lock()


def get_integration(config: Optional[ZkConfig] = None) -> Optional[ZKIntegration]:
    """Return the process-global ZK integration instance."""
    global _global_integration

    with _integration_lock:
        if _global_integration is None:
            _global_integration = ZKIntegration(config)
        return _global_integration


def reset_integration() -> None:
    """Reset the process-global ZK integration singleton."""
    global _global_integration

    with _integration_lock:
        if _global_integration:
            _global_integration.shutdown()
            _global_integration = None


def initialize_zk() -> bool:
    """Initialize and start ZK integration when enabled by env config."""
    register_name = os.getenv("REGISTER_NAME", "zookeeper")
    zk_enabled = os.getenv("ZK_ENABLED", "true").lower() == "true"

    if register_name.lower() != "zookeeper" or not zk_enabled:
        logger.info(
            "ZK integration disabled: REGISTER_NAME=%s, ZK_ENABLED=%s",
            register_name,
            zk_enabled,
        )
        return False

    try:
        integration = get_integration()
        if not integration.initialize():
            logger.warning("Failed to initialize ZK integration")
            return False
        if not integration.start():
            logger.warning("Failed to start ZK integration")
            return False

        logger.info("ZK integration started")
        return True
    except Exception as exc:
        logger.warning("Falling back to HTTP-only mode because ZK init failed: %s", exc)
        return False


def shutdown_zk() -> None:
    """Shut down the process-global ZK integration."""
    try:
        integration = get_integration()
        if integration:
            integration.shutdown()
            reset_integration()
            logger.info("ZK integration shut down")
    except Exception as exc:
        logger.error("Failed to shut down ZK integration: %s", exc)
