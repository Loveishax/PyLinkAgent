#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查管理侧服务状态
"""

import requests
import sys
import json

def check_service(management_url):
    """检查管理侧服务是否可访问"""

    print("=" * 60)
    print("管理侧服务检查")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}\n")

    # 检查服务是否可访问
    try:
        response = requests.get(management_url, timeout=5)
        print(f"[OK] 管理侧服务可访问 (HTTP {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("[FAIL] 管理侧服务无法连接")
        return False
    except requests.exceptions.Timeout:
        print("[FAIL] 管理侧服务连接超时")
        return False

    # 检查 OpenController API
    endpoints = [
        ("/open/agent/heartbeat", "POST", {"test": "data"}),
        ("/open/service/poll", "POST", {"appName": "test", "agentId": "test"}),
    ]

    for path, method, data in endpoints:
        url = f"{management_url.rstrip('/')}{path}"
        try:
            if method == "POST":
                response = requests.post(url, json=data, timeout=5)
            else:
                response = requests.get(url, timeout=5)

            # 500 表示服务存在但数据有问题，这是正常的
            if response.status_code in [200, 500]:
                print(f"[OK] {path} ({method}) - HTTP {response.status_code}")
            else:
                print(f"[WARN] {path} ({method}) - HTTP {response.status_code}")
        except Exception as e:
            print(f"[FAIL] {path} ({method}) - {e}")

    print("\n" + "=" * 60)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python check_management_service.py <管理侧 URL>")
        print("示例：python check_management_service.py http://localhost:9999")
        sys.exit(1)

    management_url = sys.argv[1]
    success = check_service(management_url)
    sys.exit(0 if success else 1)
