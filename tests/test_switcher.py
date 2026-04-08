"""
测试 PradarSwitcher 全局开关
"""

import pytest
from pylinkagent.pradar.switcher import (
    PradarSwitcher,
    PradarSwitcherListener,
    PradarSwitchEvent
)


class TestPradarSwitcherClusterTest:
    """压测开关测试"""

    def setup_method(self):
        """每个测试前的准备"""
        PradarSwitcher.turn_cluster_test_switch_off()
        PradarSwitcher.clear_cluster_test_unable()

    def teardown_method(self):
        """每个测试后的清理"""
        PradarSwitcher.turn_cluster_test_switch_off()
        PradarSwitcher.clear_cluster_test_unable()

    def test_turn_on(self):
        """测试打开压测开关"""
        result = PradarSwitcher.turn_cluster_test_switch_on()

        assert result is True
        assert PradarSwitcher.is_cluster_test_enabled() is True

    def test_turn_off(self):
        """测试关闭压测开关"""
        PradarSwitcher.turn_cluster_test_switch_on()
        result = PradarSwitcher.turn_cluster_test_switch_off()

        assert result is True
        assert PradarSwitcher.is_cluster_test_enabled() is False

    def test_unable_reason(self):
        """测试不可用原因"""
        PradarSwitcher.set_cluster_test_unable("ERR001", "Test error message")

        assert not PradarSwitcher.is_cluster_test_enabled()
        assert "Test error message" in PradarSwitcher.get_cluster_test_unable_reason()

    def test_clear_unable(self):
        """测试清除不可用状态"""
        PradarSwitcher.set_cluster_test_unable("ERR001", "Test error")
        PradarSwitcher.clear_cluster_test_unable()

        # 清除后开关状态应该恢复正常
        PradarSwitcher.turn_cluster_test_switch_on()
        assert PradarSwitcher.is_cluster_test_enabled() is True


class TestPradarSwitcherSilence:
    """静默开关测试"""

    def teardown_method(self):
        PradarSwitcher.turn_silence_switch_off()

    def test_turn_on(self):
        """测试打开静默开关"""
        PradarSwitcher.turn_silence_switch_on()
        assert PradarSwitcher.is_silence_switch_on() is True

    def test_turn_off(self):
        """测试关闭静默开关"""
        PradarSwitcher.turn_silence_switch_on()
        PradarSwitcher.turn_silence_switch_off()
        assert PradarSwitcher.is_silence_switch_on() is False


class TestPradarSwitcherWhiteList:
    """白名单开关测试"""

    def teardown_method(self):
        PradarSwitcher.turn_white_list_switch_on()

    def test_turn_on(self):
        """测试打开白名单开关"""
        PradarSwitcher.turn_white_list_switch_on()
        assert PradarSwitcher.is_white_list_switch_on() is True

    def test_turn_off(self):
        """测试关闭白名单开关"""
        PradarSwitcher.turn_white_list_switch_off()
        assert PradarSwitcher.is_white_list_switch_on() is False


class TestPradarSwitcherTraceMonitor:
    """Trace 和 Monitor 开关测试"""

    def teardown_method(self):
        PradarSwitcher.turn_trace_on()
        PradarSwitcher.turn_monitor_on()

    def test_trace_on_off(self):
        """测试 Trace 开关"""
        PradarSwitcher.turn_trace_off()
        assert not PradarSwitcher.is_trace_enabled()

        PradarSwitcher.turn_trace_on()
        assert PradarSwitcher.is_trace_enabled()

    def test_monitor_on_off(self):
        """测试 Monitor 开关"""
        PradarSwitcher.turn_monitor_off()
        assert PradarSwitcher.is_monitor_off() is True

        PradarSwitcher.turn_monitor_on()
        assert PradarSwitcher.is_monitor_off() is False


class TestPradarSwitcherRPC:
    """RPC 开关测试"""

    def teardown_method(self):
        PradarSwitcher.turn_rpc_on()

    def test_rpc_on_off(self):
        """测试 RPC 开关"""
        PradarSwitcher.turn_rpc_off()
        assert PradarSwitcher.is_rpc_off() is True

        PradarSwitcher.turn_rpc_on()
        assert PradarSwitcher.is_rpc_off() is False


class TestPradarSwitcherUserData:
    """用户数据开关测试"""

    def teardown_method(self):
        PradarSwitcher.turn_user_data_on()

    def test_user_data_on_off(self):
        """测试用户数据开关"""
        PradarSwitcher.turn_user_data_off()
        assert not PradarSwitcher.is_user_data_enabled()

        PradarSwitcher.turn_user_data_on()
        assert PradarSwitcher.is_user_data_enabled()


class TestPradarSwitcherConfig:
    """配置开关测试"""

    def teardown_method(self):
        PradarSwitcher._config_switchers.clear()

    def test_config_switcher_on(self):
        """测试配置开关打开"""
        PradarSwitcher.turn_config_switcher_on("test-config")
        assert PradarSwitcher.is_config_switcher_on("test-config") is True

    def test_config_switcher_off(self):
        """测试配置开关关闭"""
        PradarSwitcher.turn_config_switcher_on("test-config")
        PradarSwitcher.turn_config_switcher_off("test-config")
        assert PradarSwitcher.is_config_switcher_on("test-config") is False

    def test_config_switcher_default(self):
        """测试配置开关默认值"""
        assert PradarSwitcher.is_config_switcher_on("non-exist") is False


class TestPradarSwitcherSecurityField:
    """字段脱敏测试"""

    def teardown_method(self):
        PradarSwitcher._security_field_collection.clear()

    def test_set_security_fields(self):
        """测试设置脱敏字段"""
        fields = ["password", "secret", "token"]
        PradarSwitcher.set_security_field_collection(fields)

        assert PradarSwitcher.is_security_field_open() is True
        assert PradarSwitcher.get_security_field_collection() == fields

    def test_security_field_empty(self):
        """测试空脱敏字段"""
        assert PradarSwitcher.is_security_field_open() is False


class TestPradarSwitcherSampling:
    """采样配置测试"""

    def teardown_method(self):
        PradarSwitcher._sampling_interval = 1
        PradarSwitcher._cluster_test_sampling_interval = 1

    def test_sampling_interval(self):
        """测试采样间隔"""
        PradarSwitcher.set_sampling_interval(10)
        assert PradarSwitcher.get_sampling_interval() == 10

    def test_cluster_test_sampling_interval(self):
        """测试压测采样间隔"""
        PradarSwitcher.set_cluster_test_sampling_interval(5)
        assert PradarSwitcher.get_cluster_test_sampling_interval() == 5


class TestPradarSwitcherOther:
    """其他配置测试"""

    def teardown_method(self):
        PradarSwitcher._is_kafka_message_headers_enabled = True
        PradarSwitcher._is_rabbitmq_routingkey_enabled = True
        PradarSwitcher._is_pradar_log_daemon_enabled = True
        PradarSwitcher._use_local_ip = False
        PradarSwitcher._is_silence_degraded = False
        PradarSwitcher._has_pressure_request = False
        PradarSwitcher._http_pass_prefix = None

    def test_kafka_headers(self):
        """测试 Kafka Header 配置"""
        PradarSwitcher.set_kafka_message_headers_enabled(False)
        assert not PradarSwitcher.is_kafka_message_headers_enabled()

    def test_rabbitmq_routingkey(self):
        """测试 RabbitMQ RoutingKey 配置"""
        PradarSwitcher.set_rabbitmq_routingkey_enabled(False)
        assert not PradarSwitcher.is_rabbitmq_routingkey_enabled()

    def test_pradar_log_daemon(self):
        """测试日志守护进程配置"""
        PradarSwitcher.set_pradar_log_daemon_enabled(False)
        assert not PradarSwitcher.is_pradar_log_daemon_enabled()

    def test_use_local_ip(self):
        """测试本地 IP 配置"""
        PradarSwitcher.set_use_local_ip(True)
        assert PradarSwitcher.get_use_local_ip() is True

    def test_silence_degraded(self):
        """测试静默降级"""
        PradarSwitcher.set_silence_degraded(True)
        assert PradarSwitcher.is_silence_degraded() is True

    def test_has_pressure_request(self):
        """测试压测请求"""
        PradarSwitcher.set_has_pressure_request(True)
        assert PradarSwitcher.has_pressure_request() is True

    def test_http_pass_prefix(self):
        """测试 HTTP 放过前缀"""
        PradarSwitcher.set_http_pass_prefix("/health")
        assert PradarSwitcher.get_http_pass_prefix() == "/health"


class TestPradarSwitcherListener:
    """监听器测试"""

    def setup_method(self):
        PradarSwitcher._listeners.clear()

    def teardown_method(self):
        PradarSwitcher._listeners.clear()

    def test_register_listener(self):
        """测试注册监听器"""
        listener = PradarSwitcherListener()
        PradarSwitcher.register_listener(listener)

        assert listener in PradarSwitcher._listeners

    def test_unregister_listener(self):
        """测试注销监听器"""
        listener = PradarSwitcherListener()
        PradarSwitcher.register_listener(listener)
        PradarSwitcher.unregister_listener(listener)

        assert listener not in PradarSwitcher._listeners

    def test_notify_listeners(self):
        """测试通知监听器"""
        class TestListener(PradarSwitcherListener):
            def __init__(self):
                self.events = []

            def on_listen(self, event: PradarSwitchEvent):
                self.events.append(event)

        listener = TestListener()
        PradarSwitcher.register_listener(listener)

        PradarSwitcher.turn_cluster_test_switch_on()

        assert len(listener.events) == 1
        assert listener.events[0].is_cluster_test_enabled is True


class TestPradarSwitcherReset:
    """重置测试"""

    def setup_method(self):
        # 修改一些状态
        PradarSwitcher.turn_cluster_test_switch_on()
        PradarSwitcher.turn_silence_switch_on()
        PradarSwitcher.turn_trace_off()
        PradarSwitcher.set_security_field_collection(["password"])
        PradarSwitcher.turn_config_switcher_on("test")

    def test_reset(self):
        """测试重置所有开关"""
        PradarSwitcher.reset()

        assert not PradarSwitcher.is_cluster_test_enabled()
        assert not PradarSwitcher.is_silence_switch_on()
        assert PradarSwitcher.is_trace_enabled()
        assert not PradarSwitcher.is_security_field_open()
        assert not PradarSwitcher.is_config_switcher_on("test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
