"""
Elasticsearch Instrumentation Module

Elasticsearch 搜索引擎插桩模块 - 支持 elasticsearch7 库的操作拦截
"""

from .module import ElasticsearchModule
from .patcher import ElasticsearchPatcher

__all__ = ["ElasticsearchModule", "ElasticsearchPatcher"]
