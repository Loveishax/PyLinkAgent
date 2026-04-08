"""
测试 Pradar 核心 API
"""

import pytest
from pylinkagent.pradar.pradar import Pradar
from pylinkagent.pradar.context import get_context_manager


class TestPradarBasic:
    """Pradar 基础功能测试"""

    def setup_method(self):
        """每个测试前的准备"""
        get_context_manager().clear()

    def teardown_method(self):
        """每个测试后的清理"""
        get_context_manager().clear()

    def test_start_trace(self):
        """测试开始追踪"""
        ctx = Pradar.start_trace("test-app", "test-service", "test-method")

        assert ctx is not None
        assert ctx.trace_id != ""
        assert ctx.app_name == "test-app"
        assert ctx.service_name == "test-service"
        assert ctx.method_name == "test-method"

    def test_end_trace(self):
        """测试结束追踪"""
        Pradar.start_trace("app", "service", "method")
        ctx = Pradar.end_trace()

        assert ctx is not None
        assert ctx.end_time is not None
        assert ctx.cost_time >= 0

    def test_has_context(self):
        """测试是否有上下文"""
        assert not Pradar.has_context()

        Pradar.start_trace("app", "service", "method")
        assert Pradar.has_context()

        Pradar.end_trace()
        assert not Pradar.has_context()

    def test_get_context(self):
        """测试获取上下文"""
        assert Pradar.get_context() is None

        ctx = Pradar.start_trace("app", "service", "method")
        assert Pradar.get_context() == ctx

    def test_get_trace_id(self):
        """测试获取 Trace ID"""
        assert Pradar.get_trace_id() == ""

        Pradar.start_trace("app", "service", "method")
        trace_id = Pradar.get_trace_id()
        assert trace_id != ""

        Pradar.end_trace()
        assert Pradar.get_trace_id() == ""

    def test_get_invoke_id(self):
        """测试获取 Invoke ID"""
        assert Pradar.get_invoke_id() == ""

        Pradar.start_trace("app", "service", "method")
        assert Pradar.get_invoke_id() == "0"


class TestPradarClusterTest:
    """Pradar 压测功能测试"""

    def setup_method(self):
        get_context_manager().clear()

    def teardown_method(self):
        get_context_manager().clear()

    def test_set_cluster_test(self):
        """测试设置压测标识"""
        Pradar.start_trace("app", "service", "method")

        Pradar.set_cluster_test(True)
        assert Pradar.is_cluster_test() is True
        assert Pradar.get_cluster_test_flag() == "1"

        Pradar.set_cluster_test(False)
        assert Pradar.is_cluster_test() is False
        assert Pradar.get_cluster_test_flag() == "0"

    def test_cluster_test_string(self):
        """测试字符串形式的压测标识"""
        Pradar.start_trace("app", "service", "method")

        Pradar.cluster_test("1")
        assert Pradar.is_cluster_test() is True

        Pradar.cluster_test("0")
        assert Pradar.is_cluster_test() is False


class TestPradarUserData:
    """Pradar 用户数据测试"""

    def setup_method(self):
        get_context_manager().clear()

    def teardown_method(self):
        get_context_manager().clear()

    def test_set_user_data(self):
        """测试设置用户数据"""
        Pradar.start_trace("app", "service", "method")

        Pradar.set_user_data("key1", "value1")
        Pradar.set_user_data("key2", "value2")

        assert Pradar.get_user_data("key1") == "value1"
        assert Pradar.get_user_data("key2") == "value2"

    def test_get_all_user_data(self):
        """测试获取所有用户数据"""
        Pradar.start_trace("app", "service", "method")

        Pradar.set_user_data("key1", "value1")
        Pradar.set_user_data("key2", "value2")

        all_data = Pradar.get_all_user_data()
        assert len(all_data) == 2
        assert all_data["key1"] == "value1"
        assert all_data["key2"] == "value2"

    def test_remove_user_data(self):
        """测试移除用户数据"""
        Pradar.start_trace("app", "service", "method")

        Pradar.set_user_data("key1", "value1")
        Pradar.remove_user_data("key1")

        assert Pradar.get_user_data("key1") is None


class TestPradarRequestResponse:
    """Pradar 请求响应测试"""

    def setup_method(self):
        get_context_manager().clear()

    def teardown_method(self):
        get_context_manager().clear()

    def test_set_request_params(self):
        """测试设置请求参数"""
        Pradar.start_trace("app", "service", "method")

        params = {"param1": "value1", "param2": 123}
        Pradar.set_request_params(params)

        result = Pradar.get_request_params()
        assert result == params

    def test_set_response_result(self):
        """测试设置响应结果"""
        Pradar.start_trace("app", "service", "method")

        Pradar.set_response_result({"result": "success"})
        assert Pradar.get_response_result() == {"result": "success"}


class TestPradarError:
    """Pradar 错误处理测试"""

    def setup_method(self):
        get_context_manager().clear()

    def teardown_method(self):
        get_context_manager().clear()

    def test_set_error(self):
        """测试设置错误"""
        Pradar.start_trace("app", "service", "method")

        Pradar.set_error("Test error message")
        assert Pradar.has_error() is True


class TestPradarServerInvoke:
    """Pradar 服务端调用测试"""

    def setup_method(self):
        get_context_manager().clear()

    def teardown_method(self):
        get_context_manager().clear()

    def test_start_server_invoke(self):
        """测试开始服务端调用"""
        # 先创建根上下文
        Pradar.start_trace("app", "service", "method")

        # 开始服务端调用
        ctx = Pradar.start_server_invoke("rpc-service", "rpc-method", "remote-app")

        assert ctx is not None
        assert ctx.service_name == "rpc-service"
        assert ctx.method_name == "rpc-method"
        assert ctx.middleware_type == "RPC"

        # 应该继承 trace_id
        root_trace_id = Pradar.get_context().trace_id
        assert ctx.trace_id == root_trace_id

        Pradar.end_server_invoke()

    def test_end_server_invoke(self):
        """测试结束服务端调用"""
        Pradar.start_trace("app", "service", "method")
        Pradar.start_server_invoke("rpc-service", "rpc-method")

        ctx = Pradar.end_server_invoke()
        assert ctx is not None
        assert ctx.end_time is not None


class TestPradarClientInvoke:
    """Pradar 客户端调用测试"""

    def setup_method(self):
        get_context_manager().clear()

    def teardown_method(self):
        get_context_manager().clear()

    def test_start_client_invoke(self):
        """测试开始客户端调用"""
        Pradar.start_trace("app", "service", "method")

        ctx = Pradar.start_client_invoke("rpc-service", "rpc-method", "remote-app")

        assert ctx.service_name == "rpc-service"
        assert ctx.method_name == "rpc-method"
        assert Pradar.get_remote_appname() == "remote-app"

        Pradar.end_client_invoke()

    def test_set_remote_appname(self):
        """测试设置远程应用名称"""
        Pradar.start_trace("app", "service", "method")

        Pradar.set_remote_appname("test-remote-app")
        assert Pradar.get_remote_appname() == "test-remote-app"


class TestPradarContextExportImport:
    """Pradar 上下文导出导入测试"""

    def setup_method(self):
        get_context_manager().clear()

    def teardown_method(self):
        get_context_manager().clear()

    def test_export_context(self):
        """测试导出上下文"""
        Pradar.start_trace("app", "service", "method")
        Pradar.set_cluster_test(True)
        Pradar.set_user_data("key1", "value1")

        exported = Pradar.export_context()

        assert Pradar.TRACE_ID_KEY in exported
        assert Pradar.INVOKE_ID_KEY in exported
        assert Pradar.CLUSTER_TEST_KEY in exported
        assert exported[Pradar.CLUSTER_TEST_KEY] == "1"

    def test_import_context(self):
        """测试导入上下文"""
        context_data = {
            Pradar.TRACE_ID_KEY: "test-trace-id-123",
            Pradar.INVOKE_ID_KEY: "0.1",
            Pradar.CLUSTER_TEST_KEY: "1",
            Pradar.USER_DATA_KEY: "{'key1': 'value1'}",
        }

        Pradar.import_context(context_data)

        assert Pradar.get_trace_id() == "test-trace-id-123"
        assert Pradar.is_cluster_test() is True
        assert Pradar.get_user_data("key1") == "value1"

        Pradar.clear()


class TestPradarClear:
    """Pradar 清空测试"""

    def setup_method(self):
        get_context_manager().clear()

    def teardown_method(self):
        get_context_manager().clear()

    def test_clear(self):
        """测试清空上下文"""
        Pradar.start_trace("app", "service", "method")
        assert Pradar.has_context() is True

        Pradar.clear()
        assert Pradar.has_context() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
