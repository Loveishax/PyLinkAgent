# PyLinkAgent 模块扩展指南

## 1. 模块开发概述

PyLinkAgent 采用高度模块化的架构，所有插桩逻辑都以**可插拔模块**的形式存在。你可以快速为新的框架、库或中间件开发插桩模块。

### 模块类型

| 类型 | 描述 | 示例 |
|------|------|------|
| HTTP 客户端 | 拦截 HTTP 请求 | requests, httpx, aiohttp |
| Web 框架 | 拦截进入的请求 | FastAPI, Flask, Django |
| 数据库 | 拦截数据库操作 | SQLAlchemy, psycopg2 |
| 缓存 | 拦截缓存操作 | redis, aioredis |
| 消息队列 | 拦截消息收发 | kafka-python, pika |

## 2. 快速开始：创建你的第一个模块

### 步骤 1：创建模块目录结构

```bash
mkdir -p instrument_modules/mymodule_module
cd instrument_modules/mymodule_module
touch __init__.py module.py patcher.py
```

### 步骤 2：实现模块类

```python
# instrument_modules/mymodule_module/module.py

from typing import Dict, Any, Optional
import logging
from instrument_modules.base import InstrumentModule
from .patcher import MyModulePatcher


logger = logging.getLogger(__name__)


class MyModuleModule(InstrumentModule):
    name = "mymodule"
    version = "1.0.0"
    description = "我的自定义插桩模块"
    dependencies = {"mymodule": ">=1.0.0"}

    default_config = {
        "capture_headers": True,
        "sample_rate": 1.0,
    }

    def __init__(self):
        super().__init__()
        self._patcher: Optional[MyModulePatcher] = None

    def patch(self) -> bool:
        if self._active:
            return True

        if not self.check_dependencies():
            return False

        config = {**self.default_config, **self._config}
        self.set_config(config)

        self._patcher = MyModulePatcher(
            module_name=self.name,
            config=config,
            on_request=self._on_request,
            on_response=self._on_response,
            on_error=self._on_error,
        )

        try:
            success = self._patcher.patch()
            if success:
                self._active = True
            return success
        except Exception as e:
            logger.exception(f"插桩失败：{e}")
            return False

    def unpatch(self) -> bool:
        if not self._active:
            return True

        try:
            if self._patcher:
                return self._patcher.unpatch()
            return True
        except Exception as e:
            logger.exception(f"移除插桩失败：{e}")
            return False

    def _on_request(self, *args, **kwargs) -> None:
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            agent.get_context_manager().start_span(
                name="my_operation",
                attributes={"module": self.name}
            )

    def _on_response(self, *args, **kwargs) -> None:
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            agent.get_context_manager().end_span()

    def _on_error(self, exception: Exception, *args, **kwargs) -> None:
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            span = agent.get_context_manager().end_span()
            if span:
                span.set_attribute("error", True)
```

### 步骤 3：实现 Patcher

```python
# instrument_modules/mymodule_module/patcher.py

from typing import Dict, Any, Callable, List, Tuple
import logging

try:
    import wrapt
    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False

try:
    import mymodule
except ImportError:
    mymodule = None


logger = logging.getLogger(__name__)


class MyModulePatcher:
    def __init__(self, module_name: str, config: Dict[str, Any],
                 on_request: Callable, on_response: Callable, on_error: Callable):
        self.module_name = module_name
        self.config = config
        self.on_request = on_request
        self.on_response = on_response
        self.on_error = on_error
        self._patched = False
        self._original_methods: List[Tuple] = []

    def patch(self) -> bool:
        if not WRAPT_AVAILABLE:
            logger.error("wrapt 未安装")
            return False

        if mymodule is None:
            logger.error("目标模块未安装")
            return False

        try:
            self._patch_target_method()
            self._patched = True
            return True
        except Exception as e:
            logger.exception(f"插桩失败：{e}")
            self.unpatch()
            return False

    def unpatch(self) -> bool:
        if not self._patched:
            return True

        try:
            for target, attr, original in self._original_methods:
                if original is not None:
                    setattr(target, attr, original)
            self._original_methods.clear()
            self._patched = False
            return True
        except Exception as e:
            logger.exception(f"移除插桩失败：{e}")
            return False

    def _patch_target_method(self) -> None:
        @wrapt.decorator
        def wrapper(wrapped, instance, args, kwargs):
            self.on_request(*args, **kwargs)
            error = None
            result = None
            try:
                result = wrapped(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                raise
            finally:
                if error:
                    self.on_error(error)
                else:
                    self.on_response(result)

        target = mymodule.SomeClass
        attr = "some_method"
        original = getattr(target, attr, None)

        wrapt.wrap_function_wrapper(target, attr, wrapper)
        self._original_methods.append((target, attr, original))
```

### 步骤 4：创建模块入口

```python
# instrument_modules/mymodule_module/__init__.py

from .module import MyModuleModule

ModuleClass = MyModuleModule

__all__ = ["MyModuleModule", "ModuleClass"]
```

## 3. 异步模块开发

对于异步框架（如 FastAPI、aiohttp），需要使用异步包装器：

```python
@wrapt.decorator
async def async_wrapper(wrapped, instance, args, kwargs):
    self.on_before(*args, **kwargs)

    error = None
    result = None
    try:
        result = await wrapped(*args, **kwargs)
        return result
    except Exception as e:
        error = e
        raise
    finally:
        if error:
            self.on_error(error)
        else:
            self.on_after(result)
```

## 4. 最佳实践

### 零开销路径

```python
def wrapper(wrapped, instance, args, kwargs):
    from pylinkagent.core.switch import GlobalSwitch

    if not GlobalSwitch.is_enabled():
        return wrapped(*args, **kwargs)  # 直接调用，零开销

    # 正常插桩逻辑
    ...
```

### 异常隔离

```python
def wrapper(wrapped, instance, args, kwargs):
    try:
        return _probe_logic(wrapped, instance, args, kwargs)
    except Exception as e:
        _log_error_silently(e)
        return wrapped(*args, **kwargs)  # 降级为直接调用
```

### 延迟导入

```python
def patch(self) -> bool:
    try:
        import target_library
    except ImportError:
        return False
    # 继续插桩逻辑
```

## 5. 调试技巧

### 启用调试日志

```bash
export PYLINKAGENT_LOG_LEVEL=DEBUG
export PYLINKAGENT_DEBUG_MODULES=mymodule
```

### 验证插桩是否生效

```python
import mymodule
from instrument_modules.mymodule_module import ModuleClass

# 检查原始方法
print(f"原始类型：{type(mymodule.SomeClass.some_method)}")

# 应用插桩
module = ModuleClass()
module.patch()

# 检查包装后的方法
print(f"包装后类型：{type(mymodule.SomeClass.some_method)}")
```
