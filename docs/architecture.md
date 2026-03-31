# PyLinkAgent 架构设计文档

## 1. 与 LinkAgent 的核心差异对比

| 维度 | LinkAgent (Java) | PyLinkAgent (Python) | 差异说明 |
|------|------------------|---------------------|----------|
| **Attach 机制** | JVM Agent / Instrumentation API | 环境变量注入 + 站点 customize + wrapt patch | Python 无官方 Attach API，需借助 PYTHONPATH/USER_SITEcustomize |
| **字节码修改** | ASM / Javassist | wrapt 装饰器 + importlib hook | Python 动态特性更强，无需真正修改字节码 |
| **类加载隔离** | 自定义 ClassLoader | sys.modules 隔离 + import hook | Python 模块系统天然支持热插拔 |
| **线程模型** | 多线程 + ThreadLocal | 多线程 + ContextVar + asyncio | 需同时支持同步/异步上下文传递 |
| **热更新能力** | 重新定义 Class | 重新 Patch 目标对象 | Python 热更新更轻量，但需注意引用清理 |
| **性能开销** | JVM JIT 优化后极低 | 解释器开销 + patch 调用链 | 需特别注意装饰器链的性能累积 |
| **异步支持** | 无原生 async | asyncio + Task 上下文传递 | Python 需额外处理 async/await 插桩 |
| **打包分发** | JAR 文件 | Wheel / 源码安装 | Python 生态更倾向源码安装 |
| **调试友好性** | 需特殊配置 | 天然支持 pdb/ipdb | Python 探针需避免干扰调试器 |

## 2. 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Control Platform                           │
│                      (控制平台)                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/gRPC
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PyLinkAgent                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌──────────────────┐                   │
│  │ simulator-agent │    │ instrument-      │                   │
│  │  (控制面)       │◄──►│ simulator        │                   │
│  │                 │    │ (探针框架)        │                   │
│  │ - Communicator  │    │                  │                   │
│  │ - UpgradeMgr    │    │ - ModuleLoader   │                   │
│  │ - ConfigMgr     │    │ - ModuleRegistry │                   │
│  │ - HealthCheck   │    │ - Commands       │                   │
│  └─────────────────┘    └─────────┬────────┘                   │
│                                   │                             │
│                          ┌────────▼────────┐                   │
│                          │ instrument-     │                   │
│                          │ modules         │                   │
│                          │ (插桩模块)       │                   │
│                          │                 │                   │
│                          │ ┌─────────────┐ │                   │
│                          │ │  requests   │ │                   │
│                          │ │  fastapi    │ │                   │
│                          │ │  redis      │ │                   │
│                          │ │  ...        │ │                   │
│                          │ └─────────────┘ │                   │
│                          └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                             │ wrapt patch
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Target Python Application                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  FastAPI    │  │  requests   │  │  SQLAlchemy │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 探针加载/Attach 机制

### 3.1 加载策略优先级

```
┌─────────────────────────────────────────────────────────────────┐
│                    PyLinkAgent 加载策略                         │
├─────────────────────────────────────────────────────────────────┤
│  优先级 1: 环境变量注入 (PYTHONPATH + pylinkagent_hook)         │
│  优先级 2: 用户站点自定义 (usercustomize.py)                    │
│  优先级 3: 系统站点自定义 (sitecustomize.py)                    │
│  优先级 4: 包装器脚本 (wrapper script)                          │
│  优先级 5: import hook 动态注入                                │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 环境变量注入方案（推荐）

```bash
# 方式一：直接设置 PYTHONPATH
export PYTHONPATH="/path/to/pylinkagent:$PYTHONPATH"
export PYLINKAGENT_ENABLED=true
export PYLINKAGENT_CONFIG_PATH="/etc/pylinkagent/config.yaml"
python app.py

# 方式二：通过包装器
pylinkagent-run python app.py
```

### 3.3 sitecustomize 自动加载机制

Python 启动时会自动导入 `sitecustomize`（如果存在），我们利用此机制：

```python
# 用户将以下代码放入 site-packages/sitecustomize.py 或用户 sitecustomize
try:
    import pylinkagent
    pylinkagent.bootstrap()
except ImportError:
    pass  # 未安装时静默失败
```

## 4. 模块热更新与生命周期管理

### 4.1 模块状态机

```
[UNLOADED] ──load──> [LOADING] ──success──> [ACTIVE]
                           │                    │
                         fail                 unload
                           │                    │
                           ▼                    ▼
                        [FAILED]          [UNLOADING]
                           │                    │
                         cleanup              success
                           │                    │
                           └────────────────────┘
```

### 4.2 模块热更新流程

1. 控制平台下发更新指令（含新版本模块 URL/哈希）
2. simulator-agent 下载新模块到临时目录
3. 通知 instrument-simulator 准备热更新
4. 探针框架：
   - a. 暂停模块数据采集（设置全局开关）
   - b. 清理旧模块的 patch（调用 module.unpatch()）
   - c. 从 sys.modules 移除旧模块引用
   - d. 导入新模块
   - e. 调用新模块.patch() 重新插桩
   - f. 恢复数据采集开关
5. 上报更新结果

## 5. 异步支持方案

### 5.1 ContextVar 上下文传递

```python
from contextvars import ContextVar

trace_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "trace_context",
    default=None
)
```

### 5.2 Async 函数插桩

```python
@wrapt.decorator
async def async_wrapper(wrapped, instance, args, kwargs):
    # 前置逻辑
    before_call(wrapped, instance, args, kwargs)

    try:
        result = await wrapped(*args, **kwargs)
        after_call(wrapped, instance, args, kwargs, result)
        return result
    except Exception as e:
        on_error(wrapped, instance, args, kwargs, e)
        raise
```

## 6. 性能优化策略

### 6.1 零开销路径（Zero-Overhead Path）

```python
_probe_enabled = True

def smart_wrapper(wrapped, instance, args, kwargs):
    if not _probe_enabled:
        return wrapped(*args, **kwargs)  # 直接调用，零开销

    # 正常插桩逻辑
    ...
```

### 6.2 采样率控制

```python
@dataclass
class SamplingConfig:
    trace_sample_rate: float = 0.1  # 10% 采样
```

### 6.3 缓冲与批量上报

```python
class BatchReporter:
    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        # 队列缓冲 + 定时刷新
```
