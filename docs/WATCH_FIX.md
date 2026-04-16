# Watch 调用修复说明

> **日期**: 2026-04-17  
> **问题**: DataWatch 和 ChildrenWatch 调用错误  
> **状态**: 已修复

---

## 一、问题现象

日志报错：

```
ERROR - 添加 ChildrenWatch 失败:/config/log/pradar/status/..., error:__init__() missing 1 required positional argument: 'path'
ERROR - 添加 DataWatch 失败:/config/log/pradar/status/..., error:__init__() missing 1 required positional argument: 'path'
```

---

## 二、问题原因

kazoo 的 `DataWatch` 和 `ChildrenWatch` 装饰器的签名是：

```python
DataWatch(client, path, func, *args, **kwargs)
ChildrenWatch(client, path, func, allow_session_lost=False)
```

**第一个参数必须是 `client` (KazooClient 实例)**。

### 错误代码

```python
# 错误：缺少 client 参数
@DataWatch(path)
def watcher(data: bytes, stat: dict):
    pass

# 错误：缺少 client 参数
@ChildrenWatch(path)
def watcher(children: List[str]):
    pass
```

这种写法会被解释为 `DataWatch(path)`，即 `path` 被当作 `client` 参数，导致后续的 `path` 参数缺失。

---

## 三、修复方案

### 修复后的代码

**文件**: `pylinkagent/zookeeper/zk_client.py`

```python
def watch_data(self, path: str, callback: Callable[[bytes, dict], None]) -> bool:
    """监听节点数据变化"""
    if not self.is_connected():
        return False

    try:
        # 正确：传入 client 实例
        watcher = DataWatch(self._client, path, callback)
        self._data_watches[path] = watcher
        logger.debug(f"已添加 DataWatch: {path}")
        return True
    except Exception as e:
        logger.error(f"添加 DataWatch 失败：{path}, error: {e}")
        return False

def watch_children(self, path: str, callback: Callable[[List[str]], None]) -> bool:
    """监听子节点变化"""
    if not self.is_connected():
        return False

    try:
        # 正确：传入 client 实例
        watcher = ChildrenWatch(self._client, path, callback)
        self._children_watches[path] = watcher
        logger.debug(f"已添加 ChildrenWatch: {path}")
        return True
    except Exception as e:
        logger.error(f"添加 ChildrenWatch 失败：{path}, error: {e}")
        return False
```

---

## 四、验证方法

### 验证脚本

```bash
python scripts/verify_watch_fix.py
```

### 预期输出

```
DataWatch.__init__ 参数：('self', 'client', 'path', 'func', 'args')
ChildrenWatch.__init__ 参数：('self', 'client', 'path', 'func', 'allow_session_lost')
[OK] watch_data 使用正确的调用方式
[OK] watch_children 使用正确的调用方式
```

---

## 五、对比表

| 调用方式 | 错误/正确 | 说明 |
|----------|---------|------|
| `@DataWatch(path)` | ❌ 错误 | 缺少 `client` 参数 |
| `DataWatch(client, path, callback)` | ✅ 正确 | 完整的参数 |
| `@ChildrenWatch(path)` | ❌ 错误 | 缺少 `client` 参数 |
| `ChildrenWatch(client, path, callback)` | ✅ 正确 | 完整的参数 |

---

## 六、相关文件

| 文件 | 修改内容 |
|------|---------|
| `pylinkagent/zookeeper/zk_client.py` | 修复 `watch_data()` 和 `watch_children()` 方法 |
| `pylinkagent/zookeeper/zk_heartbeat.py` | 无修改 (调用方式正确) |
| `pylinkagent/zookeeper/zk_client_path.py` | 无修改 (调用方式正确) |
| `scripts/verify_watch_fix.py` | 新增验证脚本 |

---

## 七、测试日志

修复前的错误日志：

```
ERROR - 添加 ChildrenWatch 失败:/config/log/pradar/status/..., error:__init__() missing 1 required positional argument: 'path'
ERROR - 添加 DataWatch 失败:/config/log/pradar/status/..., error:__init__() missing 1 required positional argument: 'path'
```

修复后的预期日志：

```
DEBUG - 已添加 DataWatch: /config/log/pradar/status/...
DEBUG - 已添加 ChildrenWatch: /config/log/pradar/status/...
INFO - 心跳节点启动成功
```

---

**修复完成日期**: 2026-04-17  
**修复状态**: 已完成
