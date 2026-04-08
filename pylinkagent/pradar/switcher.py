"""
PradarSwitcher - Pradar 全局开关

参考 Java LinkAgent 的 PradarSwitcher 实现，提供全局开关管理。
"""

import logging
import threading
from typing import Callable, List, Optional
from dataclasses import dataclass
import time


logger = logging.getLogger(__name__)


@dataclass
class PradarSwitchEvent:
    """压测开关事件"""
    is_cluster_test_enabled: bool
    unable_reason: str = ""


class PradarSwitcherListener:
    """开关监听器接口"""

    def on_listen(self, event: PradarSwitchEvent) -> None:
        """
        监听开关变化

        Args:
            event: 开关事件
        """
        pass


class PradarSwitcher:
    """
    Pradar 全局开关管理器

    对应 Java 的 PradarSwitcher
    """

    # Trace 日志开关
    _is_trace_enabled: bool = True

    # Monitor 日志开关
    _is_monitor_enabled: bool = True

    # RPC 日志开关
    _rpc_status: bool = True

    # 用户数据透传开关
    _user_data_enabled: bool = True

    # 静默开关
    _silent_switch: bool = False

    # 白名单开关
    _white_list_switch_on: bool = True

    # 配置同步开关
    _config_sync_switch_on: bool = True

    # 日志守护进程开关
    _is_pradar_log_daemon_enabled: bool = True

    # 压测开关
    _cluster_test_switch: bool = False

    # 压测不可用原因
    _cluster_test_unable_reason: str = ""

    # 错误编码
    _error_code: Optional[str] = None

    # 错误信息
    _error_msg: Optional[str] = None

    # 监听器列表
    _listeners: List[PradarSwitcherListener] = []
    _listeners_lock = threading.Lock()

    # 字段脱敏集合
    _security_field_collection: List[str] = []

    # 配置开关（动态配置）
    _config_switchers: dict = {}

    # 采样间隔
    _sampling_interval: int = 1
    _cluster_test_sampling_interval: int = 1

    # 是否使用本地 IP
    _use_local_ip: bool = False

    # Kafka 消息 Header 支持
    _is_kafka_message_headers_enabled: bool = True

    # RabbitMQ RoutingKey 支持
    _is_rabbitmq_routingkey_enabled: bool = True

    # RPC 关闭状态
    _is_rpc_off: bool = False

    # Monitor 关闭状态
    _is_monitor_off: bool = False

    # 采样是否使用 ZK 配置
    _sampling_zk_config: bool = False

    # 静默降级状态
    _is_silence_degraded: bool = False

    # HTTP 放过前缀
    _http_pass_prefix: Optional[str] = None

    # 是否有压测请求
    _has_pressure_request: bool = False

    @classmethod
    def register_listener(cls, listener: PradarSwitcherListener) -> None:
        """
        注册监听器

        Args:
            listener: 监听器
        """
        with cls._listeners_lock:
            if listener not in cls._listeners:
                cls._listeners.append(listener)
                logger.debug(f"PradarSwitcher: 注册监听器 {listener}")

    @classmethod
    def unregister_listener(cls, listener: PradarSwitcherListener) -> None:
        """
        注销监听器

        Args:
            listener: 监听器
        """
        with cls._listeners_lock:
            if listener in cls._listeners:
                cls._listeners.remove(listener)

    @classmethod
    def _notify_listeners(cls, event: PradarSwitchEvent) -> None:
        """通知所有监听器"""
        for listener in cls._listeners:
            try:
                listener.on_listen(event)
            except Exception as e:
                logger.error(f"PradarSwitcher: 监听器执行失败 {e}")

    # ==================== 压测开关 ====================

    @classmethod
    def turn_cluster_test_switch_on(cls) -> bool:
        """
        打开压测开关

        Returns:
            bool: 是否成功
        """
        before = cls.is_cluster_test_enabled()
        cls._cluster_test_switch = True
        cls._cluster_test_unable_reason = ""

        after = cls.is_cluster_test_enabled()
        if before != after:
            logger.info("PradarSwitcher: 压测开关已打开")
            cls._notify_listeners(PradarSwitchEvent(True, ""))

        return True

    @classmethod
    def turn_cluster_test_switch_off(cls) -> bool:
        """
        关闭压测开关

        Returns:
            bool: 是否成功
        """
        before = cls.is_cluster_test_enabled()
        cls._cluster_test_switch = False

        after = cls.is_cluster_test_enabled()
        if before != after:
            logger.info("PradarSwitcher: 压测开关已关闭")
            cls._notify_listeners(PradarSwitchEvent(False, ""))

        return True

    @classmethod
    def is_cluster_test_enabled(cls) -> bool:
        """
        检查压测是否启用

        Returns:
            bool: 是否启用
        """
        if cls._error_code is not None:
            return False
        return cls._cluster_test_switch

    @classmethod
    def get_cluster_test_unable_reason(cls) -> str:
        """获取压测不可用原因"""
        if cls._error_code is not None:
            return cls._error_msg or "未知错误"
        return cls._cluster_test_unable_reason

    @classmethod
    def set_cluster_test_unable(
        cls,
        error_code: str,
        error_msg: str
    ) -> None:
        """
        设置压测不可用

        Args:
            error_code: 错误编码
            error_msg: 错误信息
        """
        cls._error_code = error_code
        cls._error_msg = error_msg
        logger.warning(
            f"PradarSwitcher: 压测不可用 code={error_code}, msg={error_msg}"
        )

    @classmethod
    def clear_cluster_test_unable(cls) -> None:
        """清除压测不可用状态"""
        cls._error_code = None
        cls._error_msg = None

    # ==================== 静默开关 ====================

    @classmethod
    def turn_silence_switch_on(cls) -> None:
        """打开静默开关"""
        cls._silent_switch = True
        logger.info("PradarSwitcher: 静默开关已打开")

    @classmethod
    def turn_silence_switch_off(cls) -> None:
        """关闭静默开关"""
        cls._silent_switch = False
        logger.info("PradarSwitcher: 静默开关已关闭")

    @classmethod
    def is_silence_switch_on(cls) -> bool:
        """检查静默开关是否打开"""
        return cls._silent_switch

    # ==================== 白名单开关 ====================

    @classmethod
    def turn_white_list_switch_on(cls) -> None:
        """打开白名单开关"""
        cls._white_list_switch_on = True
        logger.info("PradarSwitcher: 白名单开关已打开")

    @classmethod
    def turn_white_list_switch_off(cls) -> None:
        """关闭白名单开关"""
        cls._white_list_switch_on = False
        logger.info("PradarSwitcher: 白名单开关已关闭")

    @classmethod
    def is_white_list_switch_on(cls) -> bool:
        """检查白名单开关是否打开"""
        return cls._white_list_switch_on

    # ==================== Trace/Monitor 开关 ====================

    @classmethod
    def is_trace_enabled(cls) -> bool:
        """检查 Trace 是否启用"""
        return cls._is_trace_enabled

    @classmethod
    def turn_trace_on(cls) -> None:
        """打开 Trace"""
        cls._is_trace_enabled = True
        logger.info("PradarSwitcher: Trace 已打开")

    @classmethod
    def turn_trace_off(cls) -> None:
        """关闭 Trace"""
        cls._is_trace_enabled = False
        logger.info("PradarSwitcher: Trace 已关闭")

    @classmethod
    def is_monitor_enabled(cls) -> bool:
        """检查 Monitor 是否启用"""
        return cls._is_monitor_enabled

    @classmethod
    def turn_monitor_on(cls) -> None:
        """打开 Monitor"""
        cls._is_monitor_enabled = True

    @classmethod
    def turn_monitor_off(cls) -> None:
        """关闭 Monitor"""
        cls._is_monitor_enabled = False

    @classmethod
    def is_monitor_off(cls) -> bool:
        """检查 Monitor 是否关闭"""
        return not cls._is_monitor_enabled

    # ==================== RPC 开关 ====================

    @classmethod
    def is_rpc_enabled(cls) -> bool:
        """检查 RPC 是否启用"""
        return cls._rpc_status

    @classmethod
    def turn_rpc_on(cls) -> None:
        """打开 RPC"""
        cls._rpc_status = True

    @classmethod
    def turn_rpc_off(cls) -> None:
        """关闭 RPC"""
        cls._rpc_status = False

    @classmethod
    def is_rpc_off(cls) -> bool:
        """检查 RPC 是否关闭"""
        return not cls._rpc_status

    # ==================== 用户数据开关 ====================

    @classmethod
    def is_user_data_enabled(cls) -> bool:
        """检查用户数据透传是否启用"""
        return cls._user_data_enabled

    @classmethod
    def turn_user_data_on(cls) -> None:
        """打开用户数据透传"""
        cls._user_data_enabled = True

    @classmethod
    def turn_user_data_off(cls) -> None:
        """关闭用户数据透传"""
        cls._user_data_enabled = False

    # ==================== 配置开关 ====================

    @classmethod
    def turn_config_switcher_on(cls, config_name: str) -> None:
        """
        打开配置开关

        Args:
            config_name: 配置名称
        """
        old_value = cls._config_switchers.get(config_name, False)
        cls._config_switchers[config_name] = True

        if not old_value:
            logger.info(f"PradarSwitcher: 配置开关 {config_name} 已打开")
            cls._notify_listeners(
                PradarSwitchEvent(cls.is_cluster_test_enabled(), "")
            )

    @classmethod
    def turn_config_switcher_off(cls, config_name: str) -> None:
        """
        关闭配置开关

        Args:
            config_name: 配置名称
        """
        old_value = cls._config_switchers.get(config_name, True)
        cls._config_switchers[config_name] = False

        if old_value:
            logger.info(f"PradarSwitcher: 配置开关 {config_name} 已关闭")
            cls._notify_listeners(
                PradarSwitchEvent(cls.is_cluster_test_enabled(), "")
            )

    @classmethod
    def is_config_switcher_on(cls, config_name: str) -> bool:
        """
        检查配置开关是否打开

        Args:
            config_name: 配置名称

        Returns:
            bool: 是否打开
        """
        return cls._config_switchers.get(config_name, False)

    # ==================== 字段脱敏 ====================

    @classmethod
    def is_security_field_open(cls) -> bool:
        """检查字段脱敏是否开启"""
        return len(cls._security_field_collection) > 0

    @classmethod
    def set_security_field_collection(
        cls,
        fields: List[str]
    ) -> None:
        """
        设置脱敏字段集合

        Args:
            fields: 字段列表
        """
        cls._security_field_collection = fields
        logger.info(
            f"PradarSwitcher: 脱敏字段已设置 {fields}"
        )

    @classmethod
    def get_security_field_collection(cls) -> List[str]:
        """获取脱敏字段集合"""
        return cls._security_field_collection.copy()

    # ==================== 采样配置 ====================

    @classmethod
    def get_sampling_interval(cls) -> int:
        """获取采样间隔"""
        return cls._sampling_interval

    @classmethod
    def set_sampling_interval(cls, interval: int) -> None:
        """设置采样间隔"""
        cls._sampling_interval = interval

    @classmethod
    def get_cluster_test_sampling_interval(cls) -> int:
        """获取压测采样间隔"""
        return cls._cluster_test_sampling_interval

    @classmethod
    def set_cluster_test_sampling_interval(cls, interval: int) -> None:
        """设置压测采样间隔"""
        cls._cluster_test_sampling_interval = interval

    # ==================== 其他配置 ====================

    @classmethod
    def is_kafka_message_headers_enabled(cls) -> bool:
        """检查 Kafka 消息 Header 是否启用"""
        return cls._is_kafka_message_headers_enabled

    @classmethod
    def set_kafka_message_headers_enabled(cls, enabled: bool) -> None:
        """设置 Kafka 消息 Header 是否启用"""
        cls._is_kafka_message_headers_enabled = enabled

    @classmethod
    def is_rabbitmq_routingkey_enabled(cls) -> bool:
        """检查 RabbitMQ RoutingKey 是否启用"""
        return cls._is_rabbitmq_routingkey_enabled

    @classmethod
    def set_rabbitmq_routingkey_enabled(cls, enabled: bool) -> None:
        """设置 RabbitMQ RoutingKey 是否启用"""
        cls._is_rabbitmq_routingkey_enabled = enabled

    @classmethod
    def is_pradar_log_daemon_enabled(cls) -> bool:
        """检查日志守护进程是否启用"""
        return cls._is_pradar_log_daemon_enabled

    @classmethod
    def set_pradar_log_daemon_enabled(cls, enabled: bool) -> None:
        """设置日志守护进程是否启用"""
        cls._is_pradar_log_daemon_enabled = enabled

    @classmethod
    def get_use_local_ip(cls) -> bool:
        """获取是否使用本地 IP"""
        return cls._use_local_ip

    @classmethod
    def set_use_local_ip(cls, use: bool) -> None:
        """设置是否使用本地 IP"""
        cls._use_local_ip = use

    @classmethod
    def is_silence_degraded(cls) -> bool:
        """检查是否静默降级"""
        return cls._is_silence_degraded

    @classmethod
    def set_silence_degraded(cls, degraded: bool) -> None:
        """设置静默降级状态"""
        cls._is_silence_degraded = degraded

    @classmethod
    def has_pressure_request(cls) -> bool:
        """检查是否有压测请求"""
        return cls._has_pressure_request

    @classmethod
    def set_has_pressure_request(cls, has: bool) -> None:
        """设置是否有压测请求"""
        cls._has_pressure_request = has

    @classmethod
    def get_http_pass_prefix(cls) -> Optional[str]:
        """获取 HTTP 放过前缀"""
        return cls._http_pass_prefix

    @classmethod
    def set_http_pass_prefix(cls, prefix: str) -> None:
        """设置 HTTP 放过前缀"""
        cls._http_pass_prefix = prefix

    @classmethod
    def reset(cls) -> None:
        """重置所有开关到默认状态"""
        cls._cluster_test_switch = False
        cls._silent_switch = False
        cls._white_list_switch_on = True
        cls._is_trace_enabled = True
        cls._is_monitor_enabled = True
        cls._rpc_status = True
        cls._user_data_enabled = True
        cls._error_code = None
        cls._error_msg = None
        cls._config_switchers.clear()
        cls._security_field_collection.clear()
        logger.info("PradarSwitcher: 所有开关已重置")


# 全局配置开关字典（用于 PradarService 兼容）
config_switchers: dict = {}
cluster_test_switch: bool = False
