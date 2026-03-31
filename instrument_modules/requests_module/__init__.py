"""
requests 模块插桩

功能：
- 自动采集 HTTP 请求的 Trace 信息
- 记录请求/响应头、Body（可选）
- 支持请求耗时统计
- 支持请求失败重试检测
- 注入 Trace 上下文到请求头

配置项：
- capture_headers: bool - 是否捕获请求/响应头
- capture_body: bool - 是否捕获请求/响应体
- max_body_size: int - 最大捕获字节数
- ignored_hosts: List[str] - 忽略的主机列表

Example:
    from instrument_modules.requests_module import ModuleClass

    module = ModuleClass()
    module.patch()  # 开始插桩
    # ... 使用 requests ...
    module.unpatch()  # 停止插桩
"""

from .module import RequestsModule

# 导出模块类，供 ModuleLoader 加载
ModuleClass = RequestsModule

__all__ = ["RequestsModule", "ModuleClass"]
