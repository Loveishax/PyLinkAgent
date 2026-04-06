"""
PyLinkAgent Shadow Database Test Runner

影子库功能测试脚本，验证:
- 流量染色识别
- 影子库路由
- 影子表名映射
- SQL 重写
"""

import subprocess
import time
import requests
import json
import sys
from datetime import datetime
from typing import Dict, Any, List


class ShadowTestRunner:
    """影子库测试运行器"""

    def __init__(self):
        self.base_url = "http://localhost:8001"
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
                print(f"   数据：{json.dumps(result, ensure_ascii=False)[:300]}")

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

    def test_register_shadow_config(self) -> Dict:
        """测试注册影子库配置"""
        config = {
            "ds_type": 0,
            "url": "jdbc:mysql://localhost:3306/test",
            "username": "root",
            "password": "password",
            "shadow_url": "jdbc:mysql://localhost:3306/shadow_test",
            "shadow_username": "PT_root",
            "shadow_password": "PT_password",
            "shadow_account_prefix": "PT_",
            "shadow_account_suffix": "",
            "business_shadow_tables": {
                "users": "shadow_users",
                "orders": "shadow_orders",
            }
        }

        resp = requests.post(
            f"{self.base_url}/db/config/register",
            json=config,
            timeout=5
        )
        assert resp.status_code == 200
        return resp.json()

    def test_normal_user_request(self) -> Dict:
        """测试正常用户请求 (非压测流量)"""
        resp = requests.get(f"{self.base_url}/users/1", timeout=5)
        assert resp.status_code == 200
        data = resp.json()

        # 验证返回的是正常数据
        assert data.get("is_shadow") is None or data.get("is_shadow") == False
        assert data.get("is_pressure_test") == False

        return data

    def test_pressure_user_request(self) -> Dict:
        """测试压测用户请求"""
        resp = requests.get(
            f"{self.base_url}/users/1",
            headers={"x-pressure-test": "true"},
            timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()

        # 验证返回的是影子数据
        assert data.get("is_shadow") == True
        assert data.get("is_pressure_test") == True

        return data

    def test_normal_order_request(self) -> Dict:
        """测试正常订单请求"""
        resp = requests.get(f"{self.base_url}/orders/101", timeout=5)
        assert resp.status_code == 200
        return resp.json()

    def test_pressure_order_request(self) -> Dict:
        """测试压测订单请求"""
        resp = requests.get(
            f"{self.base_url}/orders/101",
            headers={"x-pressure-test": "true"},
            timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data.get("is_shadow") == True
        return data

    def test_chain_call_normal(self) -> Dict:
        """测试正常链路调用"""
        resp = requests.get(f"{self.base_url}/chain/1", timeout=5)
        assert resp.status_code == 200
        return resp.json()

    def test_chain_call_pressure(self) -> Dict:
        """测试压测链路调用"""
        resp = requests.get(
            f"{self.base_url}/chain/1",
            headers={"x-pressure-test": "true"},
            timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()

        # 验证影子路由
        assert data.get("routing", {}).get("user_table") == "shadow_users"
        assert data.get("routing", {}).get("order_table") == "shadow_orders"

        return data

    def test_sql_rewrite_normal(self) -> Dict:
        """测试 SQL 重写 (正常流量)"""
        resp = requests.get(
            f"{self.base_url}/sql/rewrite?sql=SELECT+*+FROM+users",
            timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()

        # 正常流量不重写
        assert data.get("rewritten_sql") == data.get("original_sql")
        assert data.get("is_pressure_test") in (False, None)

        return data

    def test_sql_rewrite_pressure(self) -> Dict:
        """测试 SQL 重写 (压测流量)"""
        resp = requests.get(
            f"{self.base_url}/sql/rewrite?sql=SELECT+*+FROM+users",
            headers={"x-pressure-test": "true"},
            timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()

        # 压测流量重写表名
        assert "shadow_users" in data.get("rewritten_sql", "")
        assert data.get("is_pressure_test") == True

        return data

    def test_db_status(self) -> Dict:
        """测试数据库状态"""
        resp = requests.get(f"{self.base_url}/db/status", timeout=5)
        assert resp.status_code == 200
        return resp.json()

    def test_shadow_config_registered(self) -> Dict:
        """验证影子库配置已注册"""
        resp = requests.get(f"{self.base_url}/db/config", timeout=5)
        assert resp.status_code == 200
        data = resp.json()

        assert len(data.get("configs", [])) > 0

        return data

    def test_health_check(self) -> Dict:
        """测试健康检查"""
        resp = requests.get(f"{self.base_url}/health", timeout=5)
        assert resp.status_code == 200
        return resp.json()

    def generate_report(self) -> str:
        """生成测试报告"""
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        total = len(self.results)
        total_time = sum(r["elapsed_ms"] for r in self.results)

        report = f"""
# PyLinkAgent 影子库功能测试报告

## 测试概览

| 项目 | 值 |
|------|-----|
| **测试时间** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| **总测试数** | {total} |
| **通过数** | {passed} |
| **失败数** | {failed} |
| **通过率** | {passed/total*100:.1f}% |
| **总耗时** | {total_time:.2f}ms |

## 测试分类

### 1. 配置管理测试

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 影子库配置注册 | {"✅ PASS" if self.results[0]["status"] == "PASS" else "❌ FAIL"} | 动态注册影子库配置 |

### 2. 流量染色测试

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 正常用户请求 | {"✅ PASS" if self.results[1]["status"] == "PASS" else "❌ FAIL"} | 非压测流量正确识别 |
| 压测用户请求 | {"✅ PASS" if self.results[2]["status"] == "PASS" else "❌ FAIL"} | 压测流量正确识别 |
| 正常订单请求 | {"✅ PASS" if self.results[3]["status"] == "PASS" else "❌ FAIL"} | 业务库数据返回 |
| 压测订单请求 | {"✅ PASS" if self.results[4]["status"] == "PASS" else "❌ FAIL"} | 影子库数据返回 |

### 3. 影子路由测试

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 正常链路调用 | {"✅ PASS" if self.results[5]["status"] == "PASS" else "❌ FAIL"} | 业务库路由 |
| 压测链路调用 | {"✅ PASS" if self.results[6]["status"] == "PASS" else "❌ FAIL"} | 影子库路由 |
| 影子表映射 | {"✅ PASS" if self.results[6]["status"] == "PASS" else "❌ FAIL"} | 表名正确替换 |

### 4. SQL 重写测试

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 正常 SQL | {"✅ PASS" if self.results[7]["status"] == "PASS" else "❌ FAIL"} | 不重写表名 |
| 压测 SQL | {"✅ PASS" if self.results[8]["status"] == "PASS" else "❌ FAIL"} | 重写为影子表 |

### 5. 状态检查测试

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 数据库状态 | {"✅ PASS" if self.results[9]["status"] == "PASS" else "❌ FAIL"} | 状态查询正常 |
| 配置查询 | {"✅ PASS" if self.results[10]["status"] == "PASS" else "❌ FAIL"} | 配置列表正确 |
| 健康检查 | {"✅ PASS" if self.results[11]["status"] == "PASS" else "❌ FAIL"} | 服务健康 |

## 详细测试结果

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
                result_str = json.dumps(result['result'], ensure_ascii=False)
                report += f"- **返回数据**: `{result_str[:200]}`\n"
            if result["status"] == "FAIL" and "error" in result:
                report += f"- **错误信息**: {result['error']}\n"

        report += f"""
## 测试结论

### 功能验证状态

| 功能模块 | 验证状态 | 说明 |
|----------|----------|------|
| 流量染色识别 | {"✅ 已验证" if self.results[1]["status"] == "PASS" and self.results[2]["status"] == "PASS" else "❌ 未通过"} | Header 识别压测流量 |
| 影子库路由 | {"✅ 已验证" if self.results[4]["status"] == "PASS" and self.results[6]["status"] == "PASS" else "❌ 未通过"} | 压测流量路由到影子库 |
| 影子表映射 | {"✅ 已验证" if self.results[6]["status"] == "PASS" and self.results[8]["status"] == "PASS" else "❌ 未通过"} | 表名自动替换 |
| SQL 重写 | {"✅ 已验证" if self.results[8]["status"] == "PASS" else "❌ 未通过"} | SQL 语句表名替换 |
| 配置管理 | {"✅ 已验证" if self.results[0]["status"] == "PASS" else "❌ 未通过"} | 动态注册配置 |

### 测试总结

PyLinkAgent 影子库功能测试结果：**{"全部通过 ✅" if failed == 0 else f"{failed} 个失败 ❌"}**

- 流量染色：支持通过 `x-pressure-test` Header 标识压测流量
- 影子路由：压测流量自动路由到影子库/影子表
- 表名映射：支持业务表→影子表的自动映射
- SQL 重写：压测流量下 SQL 表名自动替换

---

**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**PyLinkAgent Shadow DB v1.0.0**
"""

        return report

    def run_all(self) -> None:
        """运行所有测试"""
        print("\n" + "="*60)
        print("PyLinkAgent 影子库功能测试")
        print("="*60)

        self.start_time = datetime.now()

        # 1. 配置管理
        self.run_test(
            "影子库配置注册",
            self.test_register_shadow_config,
            "动态注册影子库配置"
        )

        # 2. 流量染色测试
        self.run_test(
            "正常用户请求",
            self.test_normal_user_request,
            "非压测流量验证"
        )

        self.run_test(
            "压测用户请求",
            self.test_pressure_user_request,
            "压测流量验证"
        )

        self.run_test(
            "正常订单请求",
            self.test_normal_order_request,
            "业务库订单查询"
        )

        self.run_test(
            "压测订单请求",
            self.test_pressure_order_request,
            "影子库订单查询"
        )

        # 3. 影子路由测试
        self.run_test(
            "正常链路调用",
            self.test_chain_call_normal,
            "业务库链路查询"
        )

        self.run_test(
            "压测链路调用",
            self.test_chain_call_pressure,
            "影子库链路查询"
        )

        # 4. SQL 重写测试
        self.run_test(
            "正常 SQL 重写",
            self.test_sql_rewrite_normal,
            "非压测 SQL 不重写"
        )

        self.run_test(
            "压测 SQL 重写",
            self.test_sql_rewrite_pressure,
            "压测 SQL 表名替换"
        )

        # 5. 状态检查
        self.run_test(
            "数据库状态",
            self.test_db_status,
            "影子库状态查询"
        )

        self.run_test(
            "配置查询",
            self.test_shadow_config_registered,
            "影子库配置列表"
        )

        self.run_test(
            "健康检查",
            self.test_health_check,
            "服务健康检查"
        )

        self.end_time = datetime.now()

        # 生成并保存报告
        report = self.generate_report()

        with open("test_shadow_report.md", "w", encoding="utf-8") as f:
            f.write(report)

        print("\n" + "="*60)
        print(f"测试完成！报告已保存到 test_shadow_report.md")
        print(f"总耗时：{(self.end_time - self.start_time).total_seconds():.2f}秒")
        print("="*60)


def check_server_running(url: str = "http://localhost:8001") -> bool:
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
        print("请先启动测试服务器:")
        print("  python test_shadow_app.py")
        print("")
        print("然后在另一个终端运行此测试脚本")
        sys.exit(1)

    print("OK: Server is running")

    runner = ShadowTestRunner()
    runner.run_all()
