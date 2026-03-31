"""
FastAPI 模块插桩

功能：
- 自动采集 HTTP 请求的 Trace 信息
- 记录请求/响应头、Body（可选）
- 支持请求耗时统计
- 支持异常捕获
- 注入 Trace 上下文到响应头
- 完整支持 asyncio 异步场景

配置项：
- capture_headers: bool - 是否捕获请求/响应头
- capture_body: bool - 是否捕获请求/响应体
- max_body_size: int - 最大捕获字节数
- ignored_paths: List[str] - 忽略的路径列表
- sample_rate: float - 采样率

Example:
    from instrument_modules.fastapi_module import ModuleClass

    module = ModuleClass()
    module.patch()  # 开始插桩
    # ... FastAPI 应用运行中 ...
    module.unpatch()  # 停止插桩
"""

from .module import FastAPIModule

# 导出模块类
ModuleClass = FastAPIModule

__all__ = ["FastAPIModule", "ModuleClass"]
