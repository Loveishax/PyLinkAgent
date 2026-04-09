#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断脚本
收集系统诊断信息
"""

import sys
import os
import socket
import requests
import json
from datetime import datetime

def diagnose():
    """运行诊断"""

    print("\n" + "=" * 60)
    print("PyLinkAgent 诊断报告")
    print("=" * 60)
    print(f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 系统信息
    print("\n[系统信息]")
    print(f"  Python 版本：{sys.version}")
    print(f"  平台：{sys.platform}")
    print(f"  主机名：{socket.gethostname()}")

    # 网络信息
    print("\n[网络信息]")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"  本地 IP: {local_ip}")
    except Exception as e:
        print(f"  本地 IP: 获取失败 - {e}")

    # 依赖检查
    print("\n[依赖检查]")
    deps = ["httpx", "requests", "pytest"]
    for dep in deps:
        try:
            __import__(dep)
            print(f"  {dep}: [OK]")
        except ImportError:
            print(f"  {dep}: [MISSING]")

    # PyLinkAgent 模块检查
    print("\n[PyLinkAgent 模块检查]")
    modules = [
        "pylinkagent.controller.external_api",
        "pylinkagent.controller.heartbeat",
        "pylinkagent.controller.config_fetcher",
        "pylinkagent.pradar",
    ]
    for mod in modules:
        try:
            __import__(mod)
            print(f"  {mod}: [OK]")
        except ImportError as e:
            print(f"  {mod}: [ERROR] - {e}")

    # 管理侧连通性
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    print(f"\n[管理侧连通性] ({management_url})")
    try:
        response = requests.get(management_url, timeout=5)
        print(f"  基础连接：[OK] HTTP {response.status_code}")
    except Exception as e:
        print(f"  基础连接：[FAIL] {e}")

    try:
        url = f"{management_url.rstrip('/')}/open/agent/heartbeat"
        response = requests.post(url, json={"test": "data"}, timeout=5)
        print(f"  心跳接口：[OK] HTTP {response.status_code}")
    except Exception as e:
        print(f"  心跳接口：[FAIL] {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    diagnose()
