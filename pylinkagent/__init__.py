"""
PyLinkAgent - Python 链路追踪探针 Agent

与 Takin-web / takin-ee-web 控制台对接，提供应用性能监控和压测流量标识能力。
"""

__version__ = "2.0.0"
__author__ = "PyLinkAgent Team"

# 核心模块
from .bootstrap import bootstrap, shutdown, is_running, get_bootstrapper

__all__ = [
    'bootstrap',
    'shutdown',
    'is_running',
    'get_bootstrapper',
    '__version__',
]
