"""
Flask 插桩模块验证测试

测试 Flask 插桩功能：
1. 模块加载验证
2. 请求拦截验证
3. 性能指标采集
4. 异常处理
"""

import sys
import time
import unittest
from unittest.mock import Mock, patch, MagicMock

# 添加项目路径
sys.path.insert(0, 'PyLinkAgent')


class TestFlaskModule(unittest.TestCase):
    """Flask 插桩模块测试"""

    def test_module_import(self):
        """测试模块导入"""
        try:
            from instrument_modules.flask_module import FlaskModule, FlaskPatcher
            print("[OK] Flask 模块导入成功")
        except ImportError as e:
            self.fail(f"Flask 模块导入失败：{e}")

    def test_flask_patcher_init(self):
        """测试 Patcher 初始化"""
        from instrument_modules.flask_module import FlaskPatcher

        patcher = FlaskPatcher(
            module_name="flask",
            config={"ignored_paths": ["/health"]},
            on_request=lambda **kw: None,
            on_response=lambda **kw: None,
            on_error=lambda **kw: None,
        )

        self.assertEqual(patcher.module_name, "flask")
        self.assertFalse(patcher._patched)
        print("[OK] FlaskPatcher 初始化成功")

    def test_flask_module_init(self):
        """测试 Module 初始化"""
        from instrument_modules.flask_module import FlaskModule

        module = FlaskModule()

        self.assertEqual(module.name, "flask")
        self.assertEqual(module.version, "1.0.0")
        self.assertFalse(module.is_active())
        print("[OK] FlaskModule 初始化成功")

    def test_dependencies_check(self):
        """测试依赖检查"""
        from instrument_modules.flask_module import FlaskModule

        module = FlaskModule()

        # 检查依赖定义
        self.assertIn("flask", module.dependencies)
        print(f"[OK] 依赖检查配置：{module.dependencies}")


class TestFlaskPatcherLogic(unittest.TestCase):
    """Flask Patcher 逻辑测试"""

    def test_trace_context_extraction(self):
        """测试 Trace 上下文提取"""
        from instrument_modules.flask_module import FlaskPatcher

        patcher = FlaskPatcher(
            module_name="flask",
            config={},
        )

        # 模拟 WSGI environ
        environ = {
            'HTTP_TRACEPARENT': '00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01'
        }

        trace_context = patcher._extract_trace_context(environ)

        self.assertIsNotNone(trace_context)
        self.assertEqual(trace_context['trace_id'], '0af7651916cd43dd8448eb211c80319c')
        self.assertEqual(trace_context['parent_span_id'], 'b7ad6b7169203331')
        print("[OK] Trace 上下文提取测试通过")

    def test_trace_context_extraction_empty(self):
        """测试无 Trace 上下文"""
        from instrument_modules.flask_module import FlaskPatcher

        patcher = FlaskPatcher(
            module_name="flask",
            config={},
        )

        environ = {}
        trace_context = patcher._extract_trace_context(environ)

        self.assertIsNone(trace_context)
        print("[OK] 无 Trace 上下文测试通过")

    def test_ignored_paths(self):
        """测试忽略的路径"""
        from instrument_modules.flask_module import FlaskPatcher

        ignored = ["/health", "/ready", "/metrics"]
        patcher = FlaskPatcher(
            module_name="flask",
            config={"ignored_paths": ignored},
        )

        self.assertEqual(patcher.config["ignored_paths"], ignored)
        print(f"[OK] 忽略的路径配置：{ignored}")


class TestFlaskIntegration(unittest.TestCase):
    """Flask 集成测试"""

    @unittest.skipIf(True, "需要 Flask 环境，跳过集成测试")
    def test_flask_request_handling(self):
        """测试 Flask 请求处理"""
        from flask import Flask
        from instrument_modules.flask_module import FlaskModule

        # 创建 Flask 应用
        app = Flask(__name__)

        @app.route('/test')
        def test_route():
            return "OK"

        # 创建 Flask 模块并插桩
        module = FlaskModule()
        module.set_config({"ignored_paths": ["/health"]})

        if not module.patch():
            self.fail("Flask 插桩失败")

        try:
            # 使用测试客户端
            with app.test_client() as client:
                response = client.get('/test')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, b"OK")

            print("[OK] Flask 集成测试通过")

        finally:
            module.unpatch()

    @unittest.skipIf(True, "需要 Flask 环境，跳过集成测试")
    def test_flask_error_handling(self):
        """测试 Flask 错误处理"""
        from flask import Flask
        from instrument_modules.flask_module import FlaskModule

        # 创建 Flask 应用
        app = Flask(__name__)

        @app.route('/error')
        def error_route():
            raise ValueError("Test error")

        # 创建 Flask 模块并插桩
        module = FlaskModule()

        if not module.patch():
            self.fail("Flask 插桩失败")

        try:
            # 使用测试客户端
            with app.test_client() as client:
                response = client.get('/error')
                self.assertEqual(response.status_code, 500)

            print("[OK] Flask 错误处理测试通过")

        finally:
            module.unpatch()


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Flask 插桩模块验证测试")
    print("=" * 60)
    print()

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestFlaskModule))
    suite.addTests(loader.loadTestsFromTestCase(TestFlaskPatcherLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestFlaskIntegration))

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
