"""
测试 InvokeContext 和 ContextManager
"""

import pytest
import threading
import time
from pylinkagent.pradar.context import InvokeContext, ContextManager, get_context_manager


class TestInvokeContext:
    """InvokeContext 测试"""

    def test_create_context(self):
        """测试创建上下文"""
        ctx = InvokeContext(
            app_name="test-app",
            service_name="test-service",
            method_name="test-method"
        )

        assert ctx.app_name == "test-app"
        assert ctx.service_name == "test-service"
        assert ctx.method_name == "test-method"
        assert ctx.invoke_id == "0"
        assert ctx.is_root()

    def test_start_end(self):
        """测试开始和结束"""
        ctx = InvokeContext()
        ctx.start()
        time.sleep(0.1)
        ctx.end()

        assert ctx.end_time is not None
        assert ctx.cost_time >= 100  # 至少 100ms

    def test_set_user_data(self):
        """测试设置用户数据"""
        ctx = InvokeContext()
        ctx.set_user_data("key1", "value1")
        ctx.set_user_data("key2", "value2")

        assert ctx.get_user_data("key1") == "value1"
        assert ctx.get_user_data("key2") == "value2"

    def test_user_data_limits(self):
        """测试用户数据限制"""
        ctx = InvokeContext()

        # 测试 key 长度限制
        long_key = "k" * 100
        ctx.set_user_data(long_key, "value")
        # key 应该被截断
        assert len(max(ctx.user_data.keys(), key=len)) <= 16

        # 测试 value 长度限制
        long_value = "v" * 1000
        ctx.set_user_data("test", long_value)
        assert len(ctx.user_data["test"]) <= 256

        # 测试数量限制
        for i in range(20):
            ctx.set_user_data(f"key{i}", f"value{i}")
        assert len(ctx.user_data) <= 10

    def test_set_cluster_test(self):
        """测试设置压测标识"""
        ctx = InvokeContext()
        ctx.set_cluster_test(True)

        assert ctx.cluster_test is True
        assert ctx.cluster_test_flag == "1"

        ctx.set_cluster_test(False)
        assert ctx.cluster_test is False
        assert ctx.cluster_test_flag == "0"

    def test_set_error(self):
        """测试设置错误"""
        ctx = InvokeContext()
        ctx.set_error("Test error message")

        assert ctx.has_error is True
        assert ctx.error_msg == "Test error message"

    def test_get_next_invoke_id(self):
        """测试获取下一个 invoke_id"""
        ctx = InvokeContext()
        ctx.invoke_id = "0"

        assert ctx.get_next_invoke_id() == "0.1"

        ctx.invoke_id = "0.1.2"
        assert ctx.get_next_invoke_id() == "0.1.2.1"

        # 测试递增
        ctx.invoke_id = "0"
        id1 = ctx.get_next_invoke_id()
        ctx.add_child(InvokeContext())
        id2 = ctx.get_next_invoke_id()

        assert id1 == "0.1"
        assert id2 == "0.2"

    def test_add_child(self):
        """测试添加子上下文"""
        parent = InvokeContext()
        parent.invoke_id = "0"

        child = InvokeContext()
        child.invoke_id = "1"

        parent.add_child(child)

        assert child.parent_context == parent
        assert len(parent.children) == 1

    def test_get_full_invoke_id(self):
        """测试获取完整 invoke_id"""
        root = InvokeContext()
        root.invoke_id = "0"

        child = InvokeContext()
        child.invoke_id = "1"
        root.add_child(child)

        grandchild = InvokeContext()
        grandchild.invoke_id = "2"
        child.add_child(grandchild)

        assert grandchild.get_full_invoke_id() == "0.1.2"

    def test_to_dict(self):
        """测试转换为字典"""
        ctx = InvokeContext(
            app_name="test-app",
            service_name="test-service"
        )
        ctx.set_cluster_test(True)
        ctx.set_error("error")

        data = ctx.to_dict()

        assert data["app_name"] == "test-app"
        assert data["service_name"] == "test-service"
        assert data["cluster_test"] is True
        assert data["has_error"] is True


class TestContextManager:
    """ContextManager 测试"""

    def setup_method(self):
        """每个测试前的准备"""
        self.manager = ContextManager()

    def teardown_method(self):
        """每个测试后的清理"""
        self.manager.clear()

    def test_create_context(self):
        """测试创建上下文"""
        ctx = self.manager.create_context(
            app_name="test-app",
            service_name="test-service",
            method_name="test-method",
            middleware_type="RPC"
        )

        assert ctx.app_name == "test-app"
        assert ctx.service_name == "test-service"
        assert ctx.middleware_type == "RPC"

    def test_start_trace(self):
        """测试开始追踪"""
        ctx = self.manager.start_trace("app", "service", "method")

        assert ctx.trace_id != ""
        assert ctx.invoke_id == "0"
        assert ctx.is_root()

    def test_push_pop_context(self):
        """测试压入弹出上下文"""
        ctx1 = self.manager.create_context()
        ctx1.invoke_id = "0"
        self.manager.push_context(ctx1)

        assert self.manager.get_current_context() == ctx1

        ctx2 = self.manager.create_context()
        ctx2.invoke_id = "1"
        self.manager.push_context(ctx2)

        assert self.manager.get_current_context() == ctx2

        popped = self.manager.pop_context()
        assert popped == ctx2
        assert self.manager.get_current_context() == ctx1

    def test_has_context(self):
        """测试是否有上下文"""
        assert not self.manager.has_context()

        ctx = self.manager.create_context()
        self.manager.push_context(ctx)

        assert self.manager.has_context()

    def test_get_trace_id(self):
        """测试获取 Trace ID"""
        assert self.manager.get_trace_id() == ""

        ctx = self.manager.start_trace("app", "service", "method")
        assert self.manager.get_trace_id() == ctx.trace_id

    def test_get_invoke_id(self):
        """测试获取 Invoke ID"""
        assert self.manager.get_invoke_id() == ""

        ctx = self.manager.start_trace("app", "service", "method")
        assert self.manager.get_invoke_id() == "0"

    def test_is_cluster_test(self):
        """测试压测标识"""
        assert not self.manager.is_cluster_test()

        ctx = self.manager.start_trace("app", "service", "method")
        ctx.set_cluster_test(True)

        assert self.manager.is_cluster_test()

    def test_user_data(self):
        """测试用户数据"""
        self.manager.start_trace("app", "service", "method")

        self.manager.set_user_data("key1", "value1")
        self.manager.set_user_data("key2", "value2")

        assert self.manager.get_user_data("key1") == "value1"
        assert self.manager.get_user_data("key2") == "value2"

        all_data = self.manager.get_all_user_data()
        assert len(all_data) == 2

    def test_thread_safety(self):
        """测试线程安全"""
        results = []

        def worker(thread_id):
            manager = ContextManager()
            ctx = manager.start_trace(f"app-{thread_id}", "service", "method")
            manager.set_user_data("thread_id", str(thread_id))
            results.append((thread_id, manager.get_trace_id(), manager.get_user_data("thread_id")))
            manager.pop_context()

        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 每个线程应该有独立的数据
        thread_ids = [r[0] for r in results]
        assert len(set(thread_ids)) == 10


class TestGetContextManager:
    """获取全局 ContextManager 测试"""

    def teardown_method(self):
        """清理全局状态"""
        get_context_manager().clear()

    def test_singleton(self):
        """测试单例"""
        manager1 = get_context_manager()
        manager2 = get_context_manager()

        assert manager1 is manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
