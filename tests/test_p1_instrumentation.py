"""
P1 优先级插桩模块验证测试

测试 Kafka 和 Elasticsearch 插桩功能
"""

import sys
import unittest

sys.path.insert(0, '.')


class TestKafkaModule(unittest.TestCase):
    """Kafka 插桩模块测试"""

    def test_module_import(self):
        """测试模块导入"""
        try:
            from instrument_modules.kafka_module import KafkaModule, KafkaPatcher
            print("[OK] Kafka 模块导入成功")
        except ImportError as e:
            self.fail(f"Kafka 模块导入失败：{e}")

    def test_kafka_patcher_init(self):
        """测试 Patcher 初始化"""
        from instrument_modules.kafka_module import KafkaPatcher

        patcher = KafkaPatcher(
            module_name="kafka",
            config={"ignored_topics": ["_internal"]},
            on_produce=lambda **kw: None,
            on_consume=lambda **kw: None,
            on_error=lambda **kw: None,
        )

        self.assertEqual(patcher.module_name, "kafka")
        self.assertFalse(patcher._patched)
        print("[OK] KafkaPatcher 初始化成功")

    def test_kafka_module_init(self):
        """测试 Module 初始化"""
        from instrument_modules.kafka_module import KafkaModule

        module = KafkaModule()

        self.assertEqual(module.name, "kafka")
        self.assertEqual(module.version, "1.0.0")
        self.assertFalse(module.is_active())
        print("[OK] KafkaModule 初始化成功")

    def test_dependencies_check(self):
        """测试依赖检查"""
        from instrument_modules.kafka_module import KafkaModule

        module = KafkaModule()

        # 检查依赖定义
        self.assertIn("confluent-kafka", module.dependencies)
        print(f"[OK] 依赖检查配置：{module.dependencies}")

    def test_trace_context_methods(self):
        """测试 Trace 上下文方法"""
        from instrument_modules.kafka_module import KafkaPatcher

        patcher = KafkaPatcher(
            module_name="kafka",
            config={},
        )

        # 测试注入
        trace_context = {'trace_id': 'test123', 'span_id': 'span456'}
        headers = patcher._inject_trace_context(None, trace_context)
        self.assertIsNotNone(headers)
        self.assertTrue(len(headers) > 0)

        # 测试提取
        extracted = patcher._extract_trace_context_from_headers(headers)
        self.assertIsNotNone(extracted)
        self.assertEqual(extracted['trace_id'], 'test123')

        print("[OK] Trace 上下文方法测试通过")


class TestElasticsearchModule(unittest.TestCase):
    """Elasticsearch 插桩模块测试"""

    def test_module_import(self):
        """测试模块导入"""
        try:
            from instrument_modules.elasticsearch_module import ElasticsearchModule, ElasticsearchPatcher
            print("[OK] Elasticsearch 模块导入成功")
        except ImportError as e:
            self.fail(f"Elasticsearch 模块导入失败：{e}")

    def test_es_patcher_init(self):
        """测试 Patcher 初始化"""
        from instrument_modules.elasticsearch_module import ElasticsearchPatcher

        patcher = ElasticsearchPatcher(
            module_name="elasticsearch",
            config={"ignored_indices": [".monitoring"]},
            on_request=lambda **kw: None,
            on_response=lambda **kw: None,
            on_error=lambda **kw: None,
        )

        self.assertEqual(patcher.module_name, "elasticsearch")
        self.assertFalse(patcher._patched)
        print("[OK] ElasticsearchPatcher 初始化成功")

    def test_es_module_init(self):
        """测试 Module 初始化"""
        from instrument_modules.elasticsearch_module import ElasticsearchModule

        module = ElasticsearchModule()

        self.assertEqual(module.name, "elasticsearch")
        self.assertEqual(module.version, "1.0.0")
        self.assertFalse(module.is_active())
        print("[OK] ElasticsearchModule 初始化成功")

    def test_dependencies_check(self):
        """测试依赖检查"""
        from instrument_modules.elasticsearch_module import ElasticsearchModule

        module = ElasticsearchModule()

        # 检查依赖定义
        self.assertIn("elasticsearch7", module.dependencies)
        print(f"[OK] 依赖检查配置：{module.dependencies}")

    def test_helper_methods(self):
        """测试辅助方法"""
        from instrument_modules.elasticsearch_module import ElasticsearchPatcher

        patcher = ElasticsearchPatcher(
            module_name="elasticsearch",
            config={},
        )

        # 测试结果大小计算
        result = {'hits': {'total': 10}}
        size = patcher._calculate_result_size(result)
        self.assertGreater(size, 0)

        # 测试 bulk 数量计算
        body = [{'index': {}}, {'doc': 1}, {'index': {}}, {'doc': 2}]
        count = patcher._calculate_bulk_count(body)
        self.assertEqual(count, 2)

        print("[OK] 辅助方法测试通过")


class TestP1ModuleConfig(unittest.TestCase):
    """P1 模块配置测试"""

    def test_kafka_config(self):
        """测试 Kafka 配置"""
        from instrument_modules.kafka_module import KafkaModule

        module = KafkaModule()
        expected_keys = [
            "capture_message_value",
            "max_message_size",
            "ignored_topics",
            "inject_trace_context",
            "sample_rate",
        ]

        for key in expected_keys:
            self.assertIn(key, module.default_config)

        print(f"[OK] Kafka 配置项：{len(expected_keys)} 个")

    def test_es_config(self):
        """测试 Elasticsearch 配置"""
        from instrument_modules.elasticsearch_module import ElasticsearchModule

        module = ElasticsearchModule()
        expected_keys = [
            "capture_body",
            "capture_result",
            "max_body_size",
            "ignored_indices",
            "sample_rate",
        ]

        for key in expected_keys:
            self.assertIn(key, module.default_config)

        print(f"[OK] Elasticsearch 配置项：{len(expected_keys)} 个")


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("P1 优先级插桩模块验证测试")
    print("=" * 60)
    print()

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestKafkaModule))
    suite.addTests(loader.loadTestsFromTestCase(TestElasticsearchModule))
    suite.addTests(loader.loadTestsFromTestCase(TestP1ModuleConfig))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 60)
    print(f"测试完成：{result.testsRun} 个测试")
    print(f"通过：{result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败：{len(result.failures)}")
    print(f"错误：{len(result.errors)}")
    print("=" * 60)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
