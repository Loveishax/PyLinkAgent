#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证 Watch 修复
测试 DataWatch 和 ChildrenWatch 是否正确调用
"""

import sys
sys.path.insert(0, 'PyLinkAgent')

from kazoo.recipe.watchers import DataWatch, ChildrenWatch

print("=" * 60)
print("Watch API 验证")
print("=" * 60)

# 1. 验证签名
print("\n1. 验证 DataWatch 和 ChildrenWatch 签名:")
print(f"   DataWatch.__init__ 参数：{DataWatch.__init__.__code__.co_varnames[:5]}")
print(f"   ChildrenWatch.__init__ 参数：{ChildrenWatch.__init__.__code__.co_varnames[:5]}")

# 期望输出:
# DataWatch: (self, client, path, func, args)
# ChildrenWatch: (self, client, path, func, allow_session_lost)

# 2. 验证调用方式
print("\n2. 验证调用方式:")
print("   正确的调用方式：DataWatch(client, path, callback)")
print("   正确的调用方式：ChildrenWatch(client, path, callback)")

# 3. 检查 zk_client.py 的实现
print("\n3. 检查 zk_client.py 的实现:")
from pylinkagent.zookeeper.zk_client import ZkClient
import inspect

source = inspect.getsource(ZkClient.watch_data)
if "DataWatch(self._client, path, callback)" in source:
    print("   [OK] watch_data 使用正确的调用方式")
else:
    print("   [FAIL] watch_data 调用方式可能有误")
    print(f"   源码：{source}")

source = inspect.getsource(ZkClient.watch_children)
if "ChildrenWatch(self._client, path, callback)" in source:
    print("   [OK] watch_children 使用正确的调用方式")
else:
    print("   [FAIL] watch_children 调用方式可能有误")
    print(f"   源码：{source}")

# 4. 总结
print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
print("\n修复内容:")
print("1. watch_data: 从 @DataWatch(path) 改为 DataWatch(self._client, path, callback)")
print("2. watch_children: 从 @ChildrenWatch(path) 改为 ChildrenWatch(self._client, path, callback)")
print("\n原因:")
print("kazoo 的 DataWatch 和 ChildrenWatch 装饰器需要 client 作为第一个参数")
print("旧代码缺少 client 参数，导致 '__init__() missing 1 required positional argument: path'")
