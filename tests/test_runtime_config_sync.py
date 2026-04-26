import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.bootstrap import PyLinkAgentBootstrapper
from pylinkagent.controller.config_fetcher import ConfigFetcher
from pylinkagent.pradar import PradarSwitcher, WhitelistManager
from pylinkagent.shadow import init_config_center


def test_config_fetcher_consumes_runtime_and_shadow_configs():
    api = Mock()
    api.is_initialized.return_value = True
    api.fetch_cluster_test_switch.return_value = True
    api.fetch_whitelist_switch.return_value = False
    api.fetch_shadow_database_config.return_value = [
        {
            "dsType": 0,
            "url": "jdbc:mysql://biz-host:3306/app",
            "shadowDbConfig": {
                "datasourceMediator": {
                    "dataSourceBusiness": "biz",
                    "dataSourcePerformanceTest": "shadow",
                },
                "dataSources": [
                    {
                        "id": "biz",
                        "url": "jdbc:mysql://biz-host:3306/app",
                        "username": "biz_user",
                    },
                    {
                        "id": "shadow",
                        "url": "jdbc:mysql://shadow-host:3306/app_pt",
                        "username": "shadow_user",
                    },
                ],
            },
        }
    ]
    api.fetch_remote_call_config.return_value = {
        "newBlists": [{"appName": "demo", "blacklists": ["cache:key:1"]}],
        "wLists": [
            {"TYPE": "http", "INTERFACE_NAME": "/api/orders"},
            {"TYPE": "rpc", "INTERFACE_NAME": "com.demo.OrderService.query"},
            {"TYPE": "mq", "INTERFACE_NAME": "topic_a#group_a"},
        ],
    }
    api.fetch_shadow_redis_config.return_value = [
        {
            "host": "redis-biz",
            "port": 6379,
            "shadowHost": "redis-shadow",
            "shadowPort": 6380,
        }
    ]
    api.fetch_shadow_es_config.return_value = [
        {
            "hosts": ["http://es-biz:9200"],
            "shadowHosts": ["http://es-shadow:9200"],
        }
    ]
    api.fetch_shadow_kafka_config.return_value = [
        {
            "originalBootstrapServers": "kafka-biz:9092",
            "shadowBootstrapServers": "kafka-shadow:9092",
            "topicMapping": {"topic_a": "topic_a_shadow"},
        }
    ]
    api.fetch_shadow_job_config.return_value = [{"jobName": "shadow-job"}]

    fetcher = ConfigFetcher(api)
    config = fetcher.fetch_now()

    assert config is not None
    assert config.cluster_test_switch is True
    assert config.whitelist_switch is False
    assert len(config.shadow_database_configs) == 1
    assert len(config.shadow_redis_configs) == 1
    assert len(config.shadow_es_configs) == 1
    assert len(config.shadow_kafka_configs) == 1
    assert config.url_whitelist == ["/api/orders"]
    assert config.rpc_whitelist == ["com.demo.OrderService.query"]
    assert config.mq_whitelist == ["topic_a#group_a"]
    assert config.cache_key_whitelist == ["cache:key:1"]


def test_bootstrapper_applies_runtime_and_shadow_config():
    PradarSwitcher.reset()
    WhitelistManager.init()
    init_config_center()

    fetcher = Mock()
    fetcher.get_config.return_value = Mock(
        cluster_test_switch=True,
        whitelist_switch=True,
        url_whitelist=["/api/demo"],
        rpc_whitelist=["com.demo.Service.call"],
        mq_whitelist=["topic_a#group_a"],
        cache_key_whitelist=["cache:key:1"],
        shadow_database_configs={},
        shadow_redis_configs={},
        shadow_es_configs={},
        shadow_kafka_configs={},
    )

    bootstrapper = PyLinkAgentBootstrapper()
    bootstrapper._config_fetcher = fetcher
    bootstrapper._apply_runtime_config()

    assert PradarSwitcher.is_cluster_test_enabled() is True
    assert PradarSwitcher.is_white_list_switch_on() is True
    assert WhitelistManager.is_url_in_whitelist("/api/demo") is True
    assert WhitelistManager.is_rpc_in_whitelist("com.demo.Service.call") is True
    assert WhitelistManager.is_mq_in_whitelist("topic_a#group_a") is True
    assert WhitelistManager.is_cache_key_in_whitelist("cache:key:1") is True
