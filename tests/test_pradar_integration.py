"""
PyLinkAgent Pradar 集成测试

验证 Pradar 链路追踪与现有模块的集成
"""

import pytest
from pylinkagent.pradar import (
    Pradar,
    PradarSwitcher,
    TraceIdGenerator,
    ContextManager,
    WhitelistManager,
    MatchType
)
from pylinkagent.pradar.context import get_context_manager


class TestPradarIntegration:
    """Pradar 集成测试"""

    def setup_method(self):
        """每个测试前的准备"""
        get_context_manager().clear()
        PradarSwitcher.turn_cluster_test_switch_off()
        PradarSwitcher.clear_cluster_test_unable()
        WhitelistManager.clear_all()

    def teardown_method(self):
        """每个测试后的清理"""
        get_context_manager().clear()
        PradarSwitcher.turn_cluster_test_switch_off()
        PradarSwitcher.clear_cluster_test_unable()
        WhitelistManager.clear_all()

    def test_full_trace_lifecycle(self):
        """测试完整追踪生命周期"""
        # 开始追踪
        root = Pradar.start_trace("test-app", "user-service", "getUser")
        assert root is not None
        assert root.trace_id != ""
        assert root.invoke_id == "0"

        # 设置压测标识
        Pradar.set_cluster_test(True)
        assert Pradar.is_cluster_test() is True

        # 设置用户数据
        Pradar.set_user_data("user_id", "12345")
        Pradar.set_user_data("request_id", "req-001")

        # 嵌套调用 - 服务端（子节点 invoke_id 从 0.1 开始）
        server_ctx = Pradar.start_server_invoke("db-service", "query", "mysql")
        assert server_ctx.trace_id == root.trace_id
        assert server_ctx.invoke_id == "0.1"

        Pradar.end_server_invoke()

        # 嵌套调用 - 客户端
        client_ctx = Pradar.start_client_invoke("cache-service", "get", "redis")
        assert client_ctx.trace_id == root.trace_id
        assert client_ctx.invoke_id == "0.2"

        Pradar.end_client_invoke()

        # 设置响应结果
        Pradar.set_response_result({"id": 1, "name": "test"})

        # 结束追踪
        result = Pradar.end_trace()
        assert result is not None
        assert result.end_time is not None
        assert result.cost_time >= 0

    def test_cluster_test_flow(self):
        """测试压测流量追踪"""
        # 打开压测开关
        PradarSwitcher.turn_cluster_test_switch_on()

        # 开始追踪应该自动继承压测标识
        ctx = Pradar.start_trace("app", "service", "method")
        assert ctx.cluster_test is True
        assert ctx.cluster_test_flag == "1"

        # 导出上下文应该包含压测标识
        exported = Pradar.export_context()
        assert exported[Pradar.CLUSTER_TEST_KEY] == "1"

    def test_whitelist_integration(self):
        """测试白名单集成"""
        # 添加 URL 白名单
        WhitelistManager.add_url_whitelist("/health", MatchType.EXACT)
        WhitelistManager.add_url_whitelist("/api/", MatchType.PREFIX)

        # 检查白名单
        assert WhitelistManager.is_url_in_whitelist("/health") is True
        assert WhitelistManager.is_url_in_whitelist("/api/users") is True
        assert WhitelistManager.is_url_in_whitelist("/other") is False

        # 添加 RPC 白名单
        WhitelistManager.add_rpc_whitelist("echo", MatchType.EXACT)
        assert WhitelistManager.is_rpc_in_whitelist("echo") is True

        # 添加 MQ 白名单
        WhitelistManager.add_mq_whitelist("test-topic", MatchType.EXACT)
        assert WhitelistManager.is_mq_in_whitelist("test-topic") is True

    def test_switcher_integration(self):
        """测试开关集成"""
        # 测试 Trace 开关
        assert PradarSwitcher.is_trace_enabled() is True
        PradarSwitcher.turn_trace_off()
        assert PradarSwitcher.is_trace_enabled() is False

        # 测试 Monitor 开关
        assert PradarSwitcher.is_monitor_enabled() is True
        PradarSwitcher.turn_monitor_off()
        assert PradarSwitcher.is_monitor_off() is True

        # 测试用户数据开关
        assert PradarSwitcher.is_user_data_enabled() is True
        PradarSwitcher.turn_user_data_off()
        assert not PradarSwitcher.is_user_data_enabled()

    def test_trace_id_generation(self):
        """测试 Trace ID 生成"""
        trace_id1 = TraceIdGenerator.generate()
        trace_id2 = TraceIdGenerator.generate()

        # Trace ID 应该唯一
        assert trace_id1 != trace_id2

        # 格式验证
        assert len(trace_id1) == 36
        assert trace_id1.isdigit()

    def test_context_propagation(self):
        """测试上下文传递"""
        # 创建根上下文
        root = Pradar.start_trace("app", "service", "method")
        Pradar.set_user_data("key1", "value1")

        # 导出上下文
        exported = Pradar.export_context()

        # 清空上下文
        Pradar.clear()
        assert not Pradar.has_context()

        # 导入上下文
        Pradar.import_context(exported)
        assert Pradar.has_context()
        assert Pradar.get_user_data("key1") == "value1"

        Pradar.clear()

    def test_error_handling(self):
        """测试错误处理"""
        Pradar.start_trace("app", "service", "method")

        # 设置错误
        Pradar.set_error("Database connection failed")
        assert Pradar.has_error() is True

        # 结束追踪
        ctx = Pradar.end_trace()
        assert ctx.has_error is True
        assert ctx.error_msg == "Database connection failed"

    def test_nested_invoke(self):
        """测试嵌套调用"""
        root = Pradar.start_trace("app", "gateway", "request")

        # 第一层嵌套（子节点 invoke_id 从 0.1 开始）
        ctx1 = Pradar.start_server_invoke("service1", "method1")
        assert ctx1.invoke_id == "0.1"

        # 第二层嵌套（ctx1 的子节点）
        ctx2 = Pradar.start_client_invoke("service2", "method2", "remote")
        assert ctx2.invoke_id == "0.1.1"

        # 第三层嵌套（ctx2 的子节点）
        ctx3 = Pradar.start_server_invoke("db", "query")
        assert ctx3.invoke_id == "0.1.1.1"

        # 逐层结束
        Pradar.end_trace()  # ctx3
        Pradar.end_trace()  # ctx2
        Pradar.end_trace()  # ctx1
        Pradar.end_trace()  # root

    def test_multiple_threads(self):
        """测试多线程场景"""
        import threading
        import time

        results = {}
        lock = threading.Lock()

        def worker(thread_id):
            # 每个线程独立的追踪
            ctx = Pradar.start_trace(f"app-{thread_id}", "service", "method")
            trace_id = Pradar.get_trace_id()
            Pradar.set_user_data("thread_id", str(thread_id))
            time.sleep(0.01)
            Pradar.end_trace()

            with lock:
                results[thread_id] = trace_id

        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 每个线程应该有独立的 Trace ID
        trace_ids = list(results.values())
        assert len(set(trace_ids)) == 5  # 全部唯一

    def test_sampling_config(self):
        """测试采样配置"""
        # 设置采样间隔
        PradarSwitcher.set_sampling_interval(10)
        assert PradarSwitcher.get_sampling_interval() == 10

        # 设置压测采样间隔
        PradarSwitcher.set_cluster_test_sampling_interval(5)
        assert PradarSwitcher.get_cluster_test_sampling_interval() == 5

    def test_security_field_masking(self):
        """测试字段脱敏"""
        # 设置脱敏字段
        sensitive_fields = ["password", "secret", "token", "credit_card"]
        PradarSwitcher.set_security_field_collection(sensitive_fields)

        assert PradarSwitcher.is_security_field_open() is True
        fields = PradarSwitcher.get_security_field_collection()
        assert fields == sensitive_fields

    def test_kafka_rabbitmq_config(self):
        """测试 MQ 配置"""
        # Kafka Header 配置
        assert PradarSwitcher.is_kafka_message_headers_enabled() is True
        PradarSwitcher.set_kafka_message_headers_enabled(False)
        assert not PradarSwitcher.is_kafka_message_headers_enabled()

        # RabbitMQ RoutingKey 配置
        assert PradarSwitcher.is_rabbitmq_routingkey_enabled() is True
        PradarSwitcher.set_rabbitmq_routingkey_enabled(False)
        assert not PradarSwitcher.is_rabbitmq_routingkey_enabled()


class TestPradarWithExistingModules:
    """Pradar 与现有模块集成测试"""

    def setup_method(self):
        get_context_manager().clear()

    def teardown_method(self):
        get_context_manager().clear()

    def test_pradar_switcher_listener(self):
        """测试开关监听器"""
        events = []

        class TestListener:
            def on_listen(self, event):
                events.append(event)

        listener = TestListener()
        PradarSwitcher.register_listener(listener)

        # 触发开关变化
        PradarSwitcher.turn_cluster_test_switch_on()

        assert len(events) == 1
        assert events[0].is_cluster_test_enabled is True

        PradarSwitcher.unregister_listener(listener)

    def test_whitelist_init(self):
        """测试白名单初始化"""
        WhitelistManager.init()

        # 检查默认白名单
        assert WhitelistManager.is_url_in_whitelist("/health") is True
        assert WhitelistManager.is_url_in_whitelist("/ping") is True
        assert WhitelistManager.is_rpc_in_whitelist("echo") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
