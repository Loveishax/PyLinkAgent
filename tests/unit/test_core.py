"""
PyLinkAgent 基础功能测试
"""

import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfig:
    """测试配置加载"""

    def test_load_default_config(self):
        from pylinkagent.config import Config, load_config

        config = load_config()

        assert config.enabled is True
        assert config.log_level == "INFO"
        assert config.agent_id == ""
        assert "requests" in config.enabled_modules

    def test_load_yaml_config(self, tmp_path):
        from pylinkagent.config import load_config

        # 创建临时配置文件
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
enabled: true
log_level: DEBUG
agent_id: test-agent-001
enabled_modules:
  - requests
  - fastapi
""")

        config = load_config(str(config_file))

        assert config.enabled is True
        assert config.log_level == "DEBUG"
        assert config.agent_id == "test-agent-001"


class TestGlobalSwitch:
    """测试全局开关"""

    def test_switch_enable_disable(self):
        from pylinkagent.core.switch import GlobalSwitch

        switch = GlobalSwitch()

        # 初始状态
        assert switch.is_enabled() is False

        # 启用
        switch.enable()
        assert switch.is_enabled() is True

        # 禁用
        switch.disable()
        assert switch.is_enabled() is False

    def test_switch_toggle(self):
        from pylinkagent.core.switch import GlobalSwitch

        switch = GlobalSwitch()

        assert switch.toggle() is True
        assert switch.toggle() is False


class TestContextManager:
    """测试上下文管理"""

    def test_create_and_get_context(self):
        from pylinkagent.core.context import ContextManager, TraceContext

        manager = ContextManager()
        context = manager.create_context("test-root")

        assert context is not None
        assert isinstance(context.trace_id, str)
        assert len(context.trace_id) == 32

        # 获取当前上下文
        current = manager.get_context()
        assert current is context

    def test_start_and_end_span(self):
        from pylinkagent.core.context import ContextManager

        manager = ContextManager()
        manager.create_context("test")

        # 创建 Span
        span = manager.start_span("test-span")
        assert span is not None
        assert span.name == "test-span"

        # 结束 Span
        ended_span = manager.end_span()
        assert ended_span is span
        assert ended_span.end_time is not None


class TestSampler:
    """测试采样器"""

    def test_100_percent_sample(self):
        from pylinkagent.config import Config
        from pylinkagent.core.sampler import Sampler

        config = Config()
        config.trace_sample_rate = 1.0
        sampler = Sampler(config)

        # 100% 采样率应该总是返回 True
        for _ in range(100):
            assert sampler.should_sample() is True

    def test_0_percent_sample(self):
        from pylinkagent.config import Config
        from pylinkagent.core.sampler import Sampler

        config = Config()
        config.trace_sample_rate = 0.0
        sampler = Sampler(config)

        # 0% 采样率应该总是返回 False
        for _ in range(100):
            assert sampler.should_sample() is False

    def test_deterministic_sample(self):
        from pylinkagent.config import Config
        from pylinkagent.core.sampler import Sampler

        config = Config()
        config.trace_sample_rate = 0.5
        sampler = Sampler(config)

        # 相同的 trace_id 应该得到相同的结果
        trace_id = "test-trace-id-12345"
        result1 = sampler.should_sample(trace_id)
        result2 = sampler.should_sample(trace_id)

        assert result1 == result2


class TestInstrumentModule:
    """测试插桩模块基类"""

    def test_module_base_class(self):
        from instrument_modules.base import InstrumentModule

        # 抽象类不能直接实例化
        with pytest.raises(TypeError):
            InstrumentModule()

    def test_module_concrete_implementation(self):
        from instrument_modules.base import InstrumentModule

        class TestModule(InstrumentModule):
            name = "test"
            version = "1.0.0"

            def patch(self):
                self._active = True  # 设置活动状态
                return True

            def unpatch(self):
                self._active = False  # 清除活动状态
                return True

        module = TestModule()

        assert module.name == "test"
        assert module.version == "1.0.0"
        assert module.is_active() is False

        # 测试 patch
        assert module.patch() is True
        assert module.is_active() is True

        # 测试 unpatch
        assert module.unpatch() is True
        assert module.is_active() is False


class TestRequestsModule:
    """测试 requests 模块"""

    def test_requests_module_creation(self):
        from instrument_modules.requests_module import ModuleClass

        module = ModuleClass()

        assert module.name == "requests"
        assert module.version == "1.0.0"
        assert module.is_active() is False

    @pytest.mark.skip(reason="需要安装 requests 库")
    def test_requests_module_patch(self):
        from instrument_modules.requests_module import ModuleClass

        module = ModuleClass()
        result = module.patch()

        # 如果 requests 已安装，应该成功
        assert result is True
        assert module.is_active() is True

        module.unpatch()


class TestFastAPIModule:
    """测试 FastAPI 模块"""

    def test_fastapi_module_creation(self):
        from instrument_modules.fastapi_module import ModuleClass

        module = ModuleClass()

        assert module.name == "fastapi"
        assert module.version == "1.0.0"
        assert module.is_active() is False


class TestAgent:
    """测试 Agent 主类"""

    def test_agent_creation(self):
        from pylinkagent.config import Config
        from pylinkagent.core.agent import Agent

        config = Config()
        config.agent_id = "test-agent"

        agent = Agent(config)

        assert agent.agent_id == "test-agent"
        assert agent.is_running() is False

    def test_agent_start_stop(self):
        from pylinkagent.config import Config
        from pylinkagent.core.agent import Agent

        config = Config()
        agent = Agent(config)

        # 启动
        assert agent.start() is True
        assert agent.is_running() is True

        # 停止
        assert agent.stop() is True
        assert agent.is_running() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
