"""
测试 WhitelistManager 白名单管理
"""

import pytest
from pylinkagent.pradar.whitelist import (
    WhitelistManager,
    WhitelistEntry,
    MatchType
)


class TestWhitelistEntry:
    """WhitelistEntry 测试"""

    def test_exact_match(self):
        """测试精确匹配"""
        entry = WhitelistEntry("/health", MatchType.EXACT)

        assert entry.matches("/health") is True
        assert entry.matches("/healthcheck") is False
        assert entry.matches("/health/") is False

    def test_prefix_match(self):
        """测试前缀匹配"""
        entry = WhitelistEntry("/api/", MatchType.PREFIX)

        assert entry.matches("/api/users") is True
        assert entry.matches("/api/orders/123") is True
        assert entry.matches("/health") is False

    def test_contains_match(self):
        """测试包含匹配"""
        entry = WhitelistEntry("test", MatchType.CONTAINS)

        assert entry.matches("/api/test/endpoint") is True
        assert entry.matches("/test") is True
        assert entry.matches("/api/endpoint") is False

    def test_regex_match(self):
        """测试正则匹配"""
        entry = WhitelistEntry(r"/api/v\d+/users", MatchType.REGEX)

        assert entry.matches("/api/v1/users") is True
        assert entry.matches("/api/v2/users") is True
        assert entry.matches("/api/v10/users") is True
        assert entry.matches("/api/users") is False

    def test_invalid_regex(self):
        """测试无效正则"""
        with pytest.raises(ValueError):
            WhitelistEntry(r"[invalid", MatchType.REGEX)

    def test_disabled_entry(self):
        """测试禁用的条目"""
        entry = WhitelistEntry("/health", MatchType.EXACT, enabled=False)
        assert entry.matches("/health") is False


class TestWhitelistManagerURL:
    """URL 白名单测试"""

    def setup_method(self):
        """每个测试前的准备"""
        WhitelistManager.clear_all()

    def teardown_method(self):
        """每个测试后的清理"""
        WhitelistManager.clear_all()

    def test_add_url_whitelist(self):
        """测试添加 URL 白名单"""
        WhitelistManager.add_url_whitelist("/health", MatchType.EXACT)
        assert WhitelistManager.is_url_in_whitelist("/health") is True
        assert WhitelistManager.is_url_in_whitelist("/api") is False

    def test_add_url_whitelist_prefix(self):
        """测试添加 URL 前缀白名单"""
        WhitelistManager.add_url_whitelist("/static/", MatchType.PREFIX)

        assert WhitelistManager.is_url_in_whitelist("/static/js/app.js") is True
        assert WhitelistManager.is_url_in_whitelist("/static/css/style.css") is True
        assert WhitelistManager.is_url_in_whitelist("/api/static") is False

    def test_remove_url_whitelist(self):
        """测试移除 URL 白名单"""
        WhitelistManager.add_url_whitelist("/health", MatchType.EXACT)
        assert WhitelistManager.is_url_in_whitelist("/health") is True

        result = WhitelistManager.remove_url_whitelist("/health")
        assert result is True
        assert WhitelistManager.is_url_in_whitelist("/health") is False

    def test_get_url_whitelist(self):
        """测试获取 URL 白名单"""
        WhitelistManager.add_url_whitelist("/health", MatchType.EXACT, "Health check")
        WhitelistManager.add_url_whitelist("/api/", MatchType.PREFIX)

        whitelist = WhitelistManager.get_url_whitelist()
        assert len(whitelist) == 2
        assert whitelist[0]["pattern"] == "/health"
        assert whitelist[0]["match_type"] == "EXACT"
        assert whitelist[0]["description"] == "Health check"


class TestWhitelistManagerRPC:
    """RPC 白名单测试"""

    def setup_method(self):
        WhitelistManager.clear_all()

    def teardown_method(self):
        WhitelistManager.clear_all()

    def test_add_rpc_whitelist(self):
        """测试添加 RPC 白名单"""
        WhitelistManager.add_rpc_whitelist("echo", MatchType.EXACT)

        assert WhitelistManager.is_rpc_in_whitelist("echo") is True
        assert WhitelistManager.is_rpc_in_whitelist("userService") is False

    def test_add_rpc_whitelist_full_name(self):
        """测试添加 RPC 全名白名单"""
        WhitelistManager.add_rpc_whitelist("com.example.UserService.getUser", MatchType.EXACT)

        assert WhitelistManager.is_rpc_in_whitelist("com.example.UserService.getUser") is True
        assert WhitelistManager.is_rpc_in_whitelist("com.example.UserService.deleteUser") is False

    def test_remove_rpc_whitelist(self):
        """测试移除 RPC 白名单"""
        WhitelistManager.add_rpc_whitelist("echo", MatchType.EXACT)
        result = WhitelistManager.remove_rpc_whitelist("echo")

        assert result is True
        assert WhitelistManager.is_rpc_in_whitelist("echo") is False

    def test_get_rpc_whitelist(self):
        """测试获取 RPC 白名单"""
        WhitelistManager.add_rpc_whitelist("echo", MatchType.EXACT)

        whitelist = WhitelistManager.get_rpc_whitelist()
        assert len(whitelist) == 1
        assert whitelist[0]["pattern"] == "echo"


class TestWhitelistManagerMQ:
    """MQ 白名单测试"""

    def setup_method(self):
        WhitelistManager.clear_all()

    def teardown_method(self):
        WhitelistManager.clear_all()

    def test_add_mq_whitelist(self):
        """测试添加 MQ 白名单"""
        WhitelistManager.add_mq_whitelist("order-topic", MatchType.EXACT)

        assert WhitelistManager.is_mq_in_whitelist("order-topic") is True
        assert WhitelistManager.is_mq_in_whitelist("user-topic") is False

    def test_mq_whitelist_with_queue(self):
        """测试 MQ 队列白名单"""
        WhitelistManager.add_mq_whitelist("test-queue", MatchType.EXACT)

        assert WhitelistManager.is_mq_in_whitelist("", "test-queue") is True
        assert WhitelistManager.is_mq_in_whitelist("other-queue") is False

    def test_get_mq_whitelist(self):
        """测试获取 MQ 白名单"""
        WhitelistManager.add_mq_whitelist("order-topic", MatchType.EXACT)

        whitelist = WhitelistManager.get_mq_whitelist()
        assert len(whitelist) == 1


class TestWhitelistManagerCacheKey:
    """Cache Key 白名单测试"""

    def setup_method(self):
        WhitelistManager.clear_all()

    def teardown_method(self):
        WhitelistManager.clear_all()

    def test_add_cache_key_whitelist(self):
        """测试添加 Cache Key 白名单"""
        WhitelistManager.add_cache_key_whitelist("user:", MatchType.PREFIX)

        assert WhitelistManager.is_cache_key_in_whitelist("user:123") is True
        assert WhitelistManager.is_cache_key_in_whitelist("order:456") is False

    def test_add_cache_key_whitelist_regex(self):
        """测试添加 Cache Key 正则白名单"""
        WhitelistManager.add_cache_key_whitelist(r"temp:\d+", MatchType.REGEX)

        assert WhitelistManager.is_cache_key_in_whitelist("temp:123") is True
        assert WhitelistManager.is_cache_key_in_whitelist("temp:abc") is False

    def test_get_cache_key_whitelist(self):
        """测试获取 Cache Key 白名单"""
        WhitelistManager.add_cache_key_whitelist("user:", MatchType.PREFIX)

        whitelist = WhitelistManager.get_cache_key_whitelist()
        assert len(whitelist) == 1


class TestWhitelistManagerGlobal:
    """全局控制测试"""

    def setup_method(self):
        WhitelistManager.clear_all()

    def teardown_method(self):
        WhitelistManager.clear_all()
        WhitelistManager.enable_whitelist()

    def test_enable_disable_whitelist(self):
        """测试启用禁用白名单"""
        WhitelistManager.add_url_whitelist("/health", MatchType.EXACT)

        # 禁用白名单后，所有检查都应该返回 False
        WhitelistManager.disable_whitelist()
        assert WhitelistManager.is_whitelist_enabled() is False
        assert WhitelistManager.is_url_in_whitelist("/health") is False

        # 启用后恢复正常
        WhitelistManager.enable_whitelist()
        assert WhitelistManager.is_whitelist_enabled() is True
        assert WhitelistManager.is_url_in_whitelist("/health") is True

    def test_clear_all(self):
        """测试清空所有白名单"""
        WhitelistManager.add_url_whitelist("/health", MatchType.EXACT)
        WhitelistManager.add_rpc_whitelist("echo", MatchType.EXACT)
        WhitelistManager.add_mq_whitelist("topic", MatchType.EXACT)
        WhitelistManager.add_cache_key_whitelist("key", MatchType.EXACT)

        WhitelistManager.clear_all()

        stats = WhitelistManager.get_stats()
        assert stats["url_count"] == 0
        assert stats["rpc_count"] == 0
        assert stats["mq_count"] == 0
        assert stats["cache_key_count"] == 0

    def test_get_stats(self):
        """测试获取统计信息"""
        WhitelistManager.add_url_whitelist("/health", MatchType.EXACT)
        WhitelistManager.add_rpc_whitelist("echo", MatchType.EXACT)

        stats = WhitelistManager.get_stats()
        assert stats["url_count"] == 1
        assert stats["rpc_count"] == 1
        assert stats["enabled"] is True


class TestWhitelistManagerInit:
    """初始化测试"""

    def teardown_method(self):
        WhitelistManager.clear_all()

    def test_init_with_defaults(self):
        """测试初始化加载默认配置"""
        WhitelistManager.init()

        # 检查默认 URL 白名单
        assert WhitelistManager.is_url_in_whitelist("/health") is True
        assert WhitelistManager.is_url_in_whitelist("/ping") is True
        assert WhitelistManager.is_url_in_whitelist("/static/js/app.js") is True

        # 检查默认 RPC 白名单
        assert WhitelistManager.is_rpc_in_whitelist("echo") is True
        assert WhitelistManager.is_rpc_in_whitelist("ping") is True
        assert WhitelistManager.is_rpc_in_whitelist("health") is True

        stats = WhitelistManager.get_stats()
        assert stats["url_count"] > 0
        assert stats["rpc_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
