"""
测试控制台对接模块

测试 ExternalAPI, HeartbeatReporter, CommandPoller, ConfigFetcher
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from pylinkagent.controller.external_api import (
    ExternalAPI,
    CommandPacket,
    HeartRequest,
)
from pylinkagent.controller.heartbeat import HeartbeatReporter, AgentStatus
from pylinkagent.controller.command_poller import CommandPoller, CommandExecutor
from pylinkagent.controller.config_fetcher import ConfigFetcher, ConfigData


# ==================== CommandPacket 测试 ====================

class TestCommandPacket:
    """测试 CommandPacket 数据类"""

    def test_default_values(self):
        """测试默认值"""
        packet = CommandPacket()
        assert packet.id == -1
        assert packet.command_type == 1
        assert packet.operate_type == 1
        assert packet.data_path == ""
        assert packet.live_time == -1

    def test_no_action_packet(self):
        """测试无操作命令包"""
        packet = CommandPacket.no_action_packet()
        assert packet.id == -1
        assert packet.command_type == 1
        assert packet.operate_type == 1

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "id": 123,
            "commandType": 2,
            "operateType": 3,
            "dataPath": "http://example.com/module.jar",
            "liveTime": 3600,
            "extras": {"key": "value"},
        }
        packet = CommandPacket.from_dict(data)
        assert packet.id == 123
        assert packet.command_type == 2
        assert packet.operate_type == 3
        assert packet.data_path == "http://example.com/module.jar"
        assert packet.live_time == 3600
        assert packet.extras == {"key": "value"}

    def test_from_dict_missing_fields(self):
        """测试从字典创建 (缺少字段)"""
        data = {"id": 456}
        packet = CommandPacket.from_dict(data)
        assert packet.id == 456
        assert packet.command_type == 1  # 默认值
        assert packet.operate_type == 1  # 默认值


# ==================== HeartRequest 测试 ====================

class TestHeartRequest:
    """测试 HeartRequest 数据类"""

    def test_default_values(self):
        """测试默认值"""
        request = HeartRequest()
        assert request.project_name == ""
        assert request.agent_id == ""
        assert request.agent_status == "running"
        assert request.uninstall_status == 0
        assert request.dormant_status == 0

    def test_to_dict(self):
        """测试转换为字典"""
        request = HeartRequest(
            project_name="test-app",
            agent_id="agent-001",
            ip_address="192.168.1.1",
            agent_status="running",
        )
        data = request.to_dict()
        assert data["projectName"] == "test-app"
        assert data["agentId"] == "agent-001"
        assert data["ipAddress"] == "192.168.1.1"
        assert data["agentStatus"] == "running"


# ==================== ExternalAPI 测试 ====================

class TestExternalAPI:
    """测试 ExternalAPI 类"""

    def test_initialization(self):
        """测试初始化"""
        api = ExternalAPI(
            tro_web_url="http://localhost:8080",
            app_name="test-app",
            agent_id="agent-001",
        )
        assert api.tro_web_url == "http://localhost:8080"
        assert api.app_name == "test-app"
        assert api.agent_id == "agent-001"
        assert api.is_initialized() == False

    @patch('pylinkagent.controller.external_api.httpx')
    def test_initialize_success(self, mock_httpx):
        """测试初始化成功"""
        mock_client = MagicMock()
        mock_httpx.Client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_client.request.return_value = mock_response

        api = ExternalAPI(
            tro_web_url="http://localhost:8080",
            app_name="test-app",
            agent_id="agent-001",
        )
        result = api.initialize()

        assert result == True
        assert api.is_initialized() == True

    def test_get_latest_command_not_initialized(self):
        """测试获取命令 (未初始化)"""
        api = ExternalAPI(
            tro_web_url="http://localhost:8080",
            app_name="test-app",
            agent_id="agent-001",
        )
        command = api.get_latest_command()
        assert command.id == -1

    @patch.dict(os.environ, {"REGISTER_NAME": "kafka"})
    def test_get_latest_command_kafka_mode(self):
        """测试 Kafka 模式下获取命令"""
        api = ExternalAPI(
            tro_web_url="http://localhost:8080",
            app_name="test-app",
            agent_id="agent-001",
        )
        api._initialized = True
        command = api.get_latest_command()
        assert command.id == -1


# ==================== HeartbeatReporter 测试 ====================

class TestHeartbeatReporter:
    """测试 HeartbeatReporter 类"""

    def test_creation(self):
        """测试创建"""
        api = Mock(spec=ExternalAPI)
        reporter = HeartbeatReporter(api)
        assert reporter.interval == 30
        assert reporter.is_running() == False

    def test_update_status(self):
        """测试更新状态"""
        api = Mock(spec=ExternalAPI)
        reporter = HeartbeatReporter(api)
        reporter.update_status(agent_status="error", agent_error_info="test error")
        assert reporter._status.agent_status == "error"
        assert reporter._status.agent_error_info == "test error"

    def test_add_command_result(self):
        """测试添加命令结果"""
        api = Mock(spec=ExternalAPI)
        reporter = HeartbeatReporter(api)
        reporter.add_command_result(123, True)
        reporter.add_command_result(456, False, "error message")
        assert len(reporter._command_results) == 2

    def test_get_local_ip(self):
        """测试获取本地 IP"""
        api = Mock(spec=ExternalAPI)
        reporter = HeartbeatReporter(api)
        ip = reporter._get_local_ip()
        assert isinstance(ip, str)
        assert len(ip) > 0


# ==================== CommandPoller 测试 ====================

class TestCommandPoller:
    """测试 CommandPoller 类"""

    def test_creation(self):
        """测试创建"""
        api = Mock(spec=ExternalAPI)
        poller = CommandPoller(api)
        assert poller.interval == 30
        assert poller.is_running() == False

    def test_command_executor_framework_command(self):
        """测试命令执行器 (框架命令)"""
        executor = CommandExecutor()
        command = CommandPacket(
            id=123,
            command_type=1,  # 框架命令
            operate_type=1,  # 安装
        )
        result = executor.execute(command)
        assert result == True

    def test_command_executor_module_command(self):
        """测试命令执行器 (模块命令)"""
        executor = CommandExecutor()
        command = CommandPacket(
            id=456,
            command_type=2,  # 模块命令
            operate_type=3,  # 升级
        )
        result = executor.execute(command)
        assert result == True

    def test_poll_now_not_initialized(self):
        """测试轮询命令 (未初始化)"""
        api = Mock(spec=ExternalAPI)
        api.is_initialized.return_value = False
        poller = CommandPoller(api)
        commands = poller.poll_now()
        assert commands == []


# ==================== ConfigFetcher 测试 ====================

class TestConfigFetcher:
    """测试 ConfigFetcher 类"""

    def test_creation(self):
        """测试创建"""
        api = Mock(spec=ExternalAPI)
        fetcher = ConfigFetcher(api)
        assert fetcher.interval == 60
        assert fetcher.is_running() == False

    def test_get_config(self):
        """测试获取配置"""
        api = Mock(spec=ExternalAPI)
        fetcher = ConfigFetcher(api)
        config = fetcher.get_config()
        assert isinstance(config, ConfigData)

    def test_parse_shadow_database_config(self):
        """测试解析影子库配置"""
        api = Mock(spec=ExternalAPI)
        fetcher = ConfigFetcher(api)

        config_data = {
            "shadowDatabaseConfigs": {
                "mysql-primary": {
                    "url": "jdbc:mysql://primary:3306/test",
                    "username": "root",
                    "shadow": False,
                },
                "mysql-shadow": {
                    "url": "jdbc:mysql://shadow:3306/test",
                    "username": "root",
                    "shadow": True,
                },
            }
        }

        config = fetcher._parse_config(config_data)
        assert len(config.shadow_database_configs) == 2
        assert "mysql-primary" in config.shadow_database_configs
        assert "mysql-shadow" in config.shadow_database_configs

    def test_parse_global_switch(self):
        """测试解析全局开关"""
        api = Mock(spec=ExternalAPI)
        fetcher = ConfigFetcher(api)

        config_data = {
            "globalSwitch": {
                "shadow.database.enable": True,
                "shadow.redis.enable": False,
            }
        }

        config = fetcher._parse_config(config_data)
        assert config.global_switch["shadow.database.enable"] == True
        assert config.global_switch["shadow.redis.enable"] == False

    def test_is_global_switch_enabled(self):
        """测试检查全局开关"""
        api = Mock(spec=ExternalAPI)
        fetcher = ConfigFetcher(api)
        fetcher._current_config.global_switch = {"test.switch": True}
        assert fetcher.is_global_switch_enabled("test.switch") == True
        assert fetcher.is_global_switch_enabled("nonexistent") == False


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试"""

    @patch('pylinkagent.controller.external_api.httpx')
    def test_full_heartbeat_flow(self, mock_httpx):
        """测试完整心跳流程"""
        # 模拟 HTTP 客户端
        mock_client = MagicMock()
        mock_httpx.Client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "data": []  # 无命令
        }
        mock_client.request.return_value = mock_response

        # 创建 API
        api = ExternalAPI(
            tro_web_url="http://localhost:8080",
            app_name="test-app",
            agent_id="agent-001",
        )
        api.initialize()

        # 创建心跳上报器
        reporter = HeartbeatReporter(api)
        reporter.update_status(
            agent_status="running",
            simulator_status="running",
        )

        # 发送心跳
        commands = reporter.send_heartbeat_now()
        assert isinstance(commands, list)

    @patch('pylinkagent.controller.external_api.httpx')
    def test_full_command_poll_flow(self, mock_httpx):
        """测试完整命令轮询流程"""
        # 模拟 HTTP 客户端
        mock_client = MagicMock()
        mock_httpx.Client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "data": {
                "id": 789,
                "commandType": 2,
                "operateType": 1,
                "dataPath": "http://example.com/module.jar",
            },
        }
        mock_client.request.return_value = mock_response

        # 创建 API
        api = ExternalAPI(
            tro_web_url="http://localhost:8080",
            app_name="test-app",
            agent_id="agent-001",
        )
        api.initialize()

        # 创建命令轮询器
        poller = CommandPoller(api)

        # 轮询命令
        commands = poller.poll_now()
        assert len(commands) == 1
        assert commands[0].id == 789


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
