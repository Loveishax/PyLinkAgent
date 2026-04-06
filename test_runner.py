"""
PyLinkAgent 集成测试脚本

用于自动化测试 PyLinkAgent 的各项功能
"""

import subprocess
import time
import requests
import json
import sys
from datetime import datetime
from typing import Dict, Any, List


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.results: List[Dict[str, Any]] = []
        self.start_time = None
        self.end_time = None

    def run_test(self, name: str, func, description: str) -> None:
        """运行单个测试"""
        print(f"\n{'='*60}")
        print(f"测试：{name}")
        print(f"描述：{description}")
        print('-'*60)

        start = time.time()
        try:
            result = func()
            elapsed = (time.time() - start) * 1000

            self.results.append({
                "name": name,
                "status": "PASS",
                "elapsed_ms": round(elapsed, 2),
                "description": description,
                "result": result
            })

            print(f"PASS: Result (elapsed: {elapsed:.2f}ms)")
            if result:
                print(f"   数据：{json.dumps(result, ensure_ascii=False)[:200]}")

        except Exception as e:
            elapsed = (time.time() - start) * 1000

            self.results.append({
                "name": name,
                "status": "FAIL",
                "elapsed_ms": round(elapsed, 2),
                "description": description,
                "error": str(e)
            })

            print(f"FAIL: {e}")

    def test_health_check(self) -> Dict:
        """测试健康检查接口"""
        resp = requests.get(f"{self.base_url}/health", timeout=5)
        assert resp.status_code == 200
        return resp.json()

    def test_root_endpoint(self) -> Dict:
        """测试根路径"""
        resp = requests.get(f"{self.base_url}/", timeout=5)
        assert resp.status_code == 200
        return resp.json()

    def test_user_endpoint(self) -> Dict:
        """测试用户接口"""
        resp = requests.get(f"{self.base_url}/users/123", timeout=5)
        assert resp.status_code == 200
        return resp.json()

    def test_user_not_found(self) -> Dict:
        """测试 404 错误"""
        try:
            resp = requests.get(f"{self.base_url}/users/-1", timeout=5)
            return {"status_code": resp.status_code}
        except requests.exceptions.HTTPError as e:
            return {"status_code": e.response.status_code}

    def test_external_api(self) -> Dict:
        """测试外部 API 调用"""
        resp = requests.get(f"{self.base_url}/external", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        return {
            "status_code": data.get("status_code"),
            "elapsed_ms": round(data.get("elapsed_ms", 0), 2)
        }

    def test_chain_call(self) -> Dict:
        """测试链路追踪"""
        resp = requests.get(f"{self.base_url}/chain", timeout=10)
        assert resp.status_code == 200
        return resp.json()

    def test_error_handling(self) -> Dict:
        """测试错误处理"""
        try:
            resp = requests.get(f"{self.base_url}/error", timeout=5)
            return {"status_code": resp.status_code, "handled": True}
        except Exception as e:
            return {"error_type": type(e).__name__, "message": str(e)}

    def test_http_error(self) -> Dict:
        """测试 HTTP 错误"""
        try:
            resp = requests.get(f"{self.base_url}/error/http", timeout=5)
            return {"status_code": resp.status_code}
        except requests.exceptions.HTTPError as e:
            return {"status_code": e.response.status_code}

    def test_slow_endpoint(self) -> Dict:
        """测试慢接口"""
        start = time.time()
        resp = requests.get(f"{self.base_url}/slow", timeout=10)
        elapsed = (time.time() - start) * 1000
        assert resp.status_code == 200
        return {
            "response_elapsed_ms": round(elapsed, 2),
            "server_slept": resp.json().get("slept")
        }

    def test_db_query(self) -> Dict:
        """测试数据库模拟接口"""
        resp = requests.get(f"{self.base_url}/db/query?query=SELECT+*+FROM+users", timeout=5)
        assert resp.status_code == 200
        return resp.json()

    def test_post_external(self) -> Dict:
        """测试 POST 请求"""
        test_data = {"name": "test", "value": 123}
        resp = requests.post(
            f"{self.base_url}/external/post",
            json=test_data,
            timeout=15
        )
        assert resp.status_code == 200
        data = resp.json()
        return {
            "status_code": data.get("status_code"),
            "echoed_data": data.get("data", {}).get("json")
        }

    def generate_report(self) -> str:
        """生成测试报告"""
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        total = len(self.results)
        total_time = sum(r["elapsed_ms"] for r in self.results)

        report = f"""
# PyLinkAgent 集成测试报告

## 测试概览

| 项目 | 值 |
|------|-----|
| **测试时间** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| **总测试数** | {total} |
| **通过数** | {passed} |
| **失败数** | {failed} |
| **通过率** | {passed/total*100:.1f}% |
| **总耗时** | {total_time:.2f}ms |

## 详细结果

"""

        for i, result in enumerate(self.results, 1):
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            report += f"""
### {i}. {result['name']}

- **状态**: {status_icon} {result['status']}
- **描述**: {result['description']}
- **耗时**: {result['elapsed_ms']:.2f}ms
"""
            if result["status"] == "PASS" and "result" in result:
                report += f"- **返回数据**: `{json.dumps(result['result'], ensure_ascii=False)[:150]}`\n"
            if result["status"] == "FAIL" and "error" in result:
                report += f"- **错误信息**: {result['error']}\n"

        return report

    def run_all(self) -> None:
        """运行所有测试"""
        print("\n" + "="*60)
        print("PyLinkAgent 集成测试")
        print("="*60)

        self.start_time = datetime.now()

        # 功能测试
        self.run_test(
            "健康检查接口",
            self.test_health_check,
            "验证健康检查接口正常工作（该接口应该被探针忽略）"
        )

        self.run_test(
            "根路径接口",
            self.test_root_endpoint,
            "验证根路径返回正确的应用信息"
        )

        self.run_test(
            "用户查询接口",
            self.test_user_endpoint,
            "验证 GET 参数传递和响应处理"
        )

        self.run_test(
            "404 错误处理",
            self.test_user_not_found,
            "验证 HTTP 404 错误正确处理"
        )

        self.run_test(
            "外部 API 调用",
            self.test_external_api,
            "验证 requests 客户端插桩和外部 HTTP 调用"
        )

        self.run_test(
            "链路追踪",
            self.test_chain_call,
            "验证 Span 嵌套和链路追踪功能"
        )

        self.run_test(
            "异常处理",
            self.test_error_handling,
            "验证 Python 异常被正确捕获和记录"
        )

        self.run_test(
            "HTTP 错误",
            self.test_http_error,
            "验证 HTTPException 被正确处理"
        )

        self.run_test(
            "慢接口",
            self.test_slow_endpoint,
            "验证慢接口的耗时统计（应该>2000ms）"
        )

        self.run_test(
            "数据库模拟",
            self.test_db_query,
            "验证 SQL 查询模拟接口"
        )

        self.run_test(
            "POST 外部 API",
            self.test_post_external,
            "验证 POST 请求和 JSON 数据处理"
        )

        self.end_time = datetime.now()

        # 生成并保存报告
        report = self.generate_report()

        with open("test_report.md", "w", encoding="utf-8") as f:
            f.write(report)

        print("\n" + "="*60)
        print(f"测试完成！报告已保存到 test_report.md")
        print(f"总耗时：{(self.end_time - self.start_time).total_seconds():.2f}秒")
        print("="*60)


def check_server_running(url: str = "http://localhost:8000") -> bool:
    """检查服务器是否运行"""
    try:
        resp = requests.get(f"{url}/health", timeout=3)
        return resp.status_code == 200
    except:
        return False


if __name__ == "__main__":
    print("检查测试服务器是否运行...")

    if not check_server_running():
        print("FAIL: Test server is not running!")
        print("")
        print("Please start the test server:")
        print("  1. export PYLINKAGENT_ENABLED=true")
        print("  2. export PYLINKAGENT_LOG_LEVEL=DEBUG")
        print("  3. python test_app.py")
        print("")
        print("Then run this test script in another terminal")
        sys.exit(1)

    print("OK: Server is running")

    runner = TestRunner()
    runner.run_all()
