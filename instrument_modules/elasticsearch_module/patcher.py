"""
ElasticsearchPatcher - Elasticsearch 搜索引擎插桩实现

负责拦截 Elasticsearch 操作并采集数据
"""

from typing import Any, Optional, Callable, Dict
import logging
import time
import json

import wrapt

logger = logging.getLogger(__name__)


class ElasticsearchPatcher:
    """
    Elasticsearch 搜索引擎插桩器

    支持 elasticsearch7 库的插桩:
    - Elasticsearch.index
    - Elasticsearch.get
    - Elasticsearch.search
    - Elasticsearch.update
    - Elasticsearch.delete
    - Bulk 操作
    """

    def __init__(
        self,
        module_name: str,
        config: Dict[str, Any],
        on_request: Optional[Callable] = None,
        on_response: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.module_name = module_name
        self.config = config
        self.on_request = on_request
        self.on_response = on_response
        self.on_error = on_error
        self._patched = False
        self._original_methods = {}

    def patch(self) -> bool:
        """应用 Elasticsearch 插桩"""
        if self._patched:
            logger.warning("Elasticsearch 已经处于插桩状态")
            return True

        try:
            from elasticsearch7 import Elasticsearch
        except ImportError:
            logger.warning("elasticsearch7 未安装，跳过插桩")
            return False

        logger.info(f"检测到 elasticsearch7 库")

        # 拦截核心操作
        self._patch_index_operations()
        self._patch_search_operations()
        self._patch_bulk_operations()

        self._patched = True
        logger.info("Elasticsearch 插桩成功")
        return True

    def unpatch(self) -> bool:
        """移除 Elasticsearch 插桩"""
        if not self._patched:
            return True

        try:
            from elasticsearch7 import Elasticsearch

            # 恢复原始方法
            for key, original in self._original_methods.items():
                if hasattr(Elasticsearch, key):
                    setattr(Elasticsearch, key, original)

            self._original_methods.clear()
            self._patched = False
            logger.info("Elasticsearch 插桩已移除")
            return True

        except Exception as e:
            logger.exception(f"Elasticsearch 插桩移除异常：{e}")
            return False

    def _patch_index_operations(self) -> None:
        """拦截索引操作 (index, update, delete)"""
        try:
            from elasticsearch7 import Elasticsearch
        except ImportError:
            return

        operations = ['index', 'update', 'delete']

        for op_name in operations:
            if not hasattr(Elasticsearch, op_name):
                continue

            original_method = getattr(Elasticsearch, op_name)
            self._original_methods[f'Elasticsearch.{op_name}'] = original_method

            @wrapt.decorator
            def operation_wrapper(wrapped, instance, args, kwargs):
                # 提取参数
                index_name = kwargs.get('index', 'unknown')
                doc_id = kwargs.get('id', args[0] if args else 'unknown')
                body = kwargs.get('body', args[1] if len(args) > 1 else None)

                # 检查是否忽略该 index
                ignored_indices = self.config.get('ignored_indices', [])
                if any(index_name.startswith(ignored) for ignored in ignored_indices):
                    return wrapped(*args, **kwargs)

                operation_name = wrapped.__name__
                start_time = time.time()
                body_size = len(json.dumps(body)) if body else 0

                # 前置钩子
                if self.on_request:
                    self.on_request(
                        operation=operation_name,
                        index=index_name,
                        doc_id=doc_id,
                        body=body,
                        body_size=body_size,
                        start_time=start_time,
                        instance=instance
                    )

                try:
                    result = wrapped(*args, **kwargs)
                    elapsed_ms = (time.time() - start_time) * 1000

                    # 后置钩子
                    if self.on_response:
                        self.on_response(
                            operation=operation_name,
                            index=index_name,
                            doc_id=doc_id,
                            result=result,
                            elapsed_ms=elapsed_ms,
                            instance=instance
                        )

                    return result

                except Exception as e:
                    elapsed_ms = (time.time() - start_time) * 1000

                    # 错误钩子
                    if self.on_error:
                        self.on_error(
                            operation=operation_name,
                            index=index_name,
                            doc_id=doc_id,
                            exception=e,
                            elapsed_ms=elapsed_ms,
                            instance=instance
                        )

                    raise

            setattr(Elasticsearch, op_name, operation_wrapper(original_method))

    def _patch_search_operations(self) -> None:
        """拦截搜索操作 (search, get, msearch)"""
        try:
            from elasticsearch7 import Elasticsearch
        except ImportError:
            return

        operations = ['search', 'get', 'msearch', 'count', 'exists']

        for op_name in operations:
            if not hasattr(Elasticsearch, op_name):
                continue

            original_method = getattr(Elasticsearch, op_name)
            self._original_methods[f'Elasticsearch.{op_name}'] = original_method

            @wrapt.decorator
            def search_wrapper(wrapped, instance, args, kwargs):
                # 提取参数
                index_name = kwargs.get('index', args[0] if args else 'unknown')
                query = kwargs.get('body', kwargs.get('query', None))
                doc_id = kwargs.get('id', None)

                # 检查是否忽略该 index
                ignored_indices = self.config.get('ignored_indices', [])
                if isinstance(index_name, str) and any(index_name.startswith(ignored) for ignored in ignored_indices):
                    return wrapped(*args, **kwargs)

                operation_name = wrapped.__name__
                start_time = time.time()

                # 前置钩子
                if self.on_request:
                    self.on_request(
                        operation=operation_name,
                        index=index_name,
                        doc_id=doc_id,
                        query=query,
                        start_time=start_time,
                        instance=instance
                    )

                try:
                    result = wrapped(*args, **kwargs)
                    elapsed_ms = (time.time() - start_time) * 1000

                    # 后置钩子
                    if self.on_response:
                        # 计算结果大小
                        result_size = self._calculate_result_size(result)

                        self.on_response(
                            operation=operation_name,
                            index=index_name,
                            doc_id=doc_id,
                            result=result,
                            result_size=result_size,
                            elapsed_ms=elapsed_ms,
                            instance=instance
                        )

                    return result

                except Exception as e:
                    elapsed_ms = (time.time() - start_time) * 1000

                    # 错误钩子
                    if self.on_error:
                        self.on_error(
                            operation=operation_name,
                            index=index_name,
                            doc_id=doc_id,
                            exception=e,
                            elapsed_ms=elapsed_ms,
                            instance=instance
                        )

                    raise

            setattr(Elasticsearch, op_name, search_wrapper(original_method))

    def _patch_bulk_operations(self) -> None:
        """拦截批量操作 (bulk)"""
        try:
            from elasticsearch7 import Elasticsearch
        except ImportError:
            return

        if not hasattr(Elasticsearch, 'bulk'):
            return

        original_method = getattr(Elasticsearch, 'bulk')
        self._original_methods['Elasticsearch.bulk'] = original_method

        @wrapt.decorator
        def bulk_wrapper(wrapped, instance, args, kwargs):
            # 提取参数
            body = kwargs.get('body', args[0] if args else [])
            index_name = kwargs.get('index', 'bulk')

            # 检查是否忽略
            ignored_indices = self.config.get('ignored_indices', [])
            if any(isinstance(index_name, str) and index_name.startswith(ignored) for ignored in ignored_indices):
                return wrapped(*args, **kwargs)

            start_time = time.time()

            # 计算批量操作数量
            bulk_count = self._calculate_bulk_count(body)
            body_size = len(json.dumps(body)) if body else 0

            # 前置钩子
            if self.on_request:
                self.on_request(
                    operation='bulk',
                    index=index_name,
                    body=body,
                    body_size=body_size,
                    bulk_count=bulk_count,
                    start_time=start_time,
                    instance=instance
                )

            try:
                result = wrapped(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                # 后置钩子
                if self.on_response:
                    self.on_response(
                        operation='bulk',
                        index=index_name,
                        result=result,
                        bulk_count=bulk_count,
                        elapsed_ms=elapsed_ms,
                        instance=instance
                    )

                return result

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000

                # 错误钩子
                if self.on_error:
                    self.on_error(
                        operation='bulk',
                        index=index_name,
                        exception=e,
                        elapsed_ms=elapsed_ms,
                        instance=instance
                    )

                raise

        setattr(Elasticsearch, 'bulk', bulk_wrapper(original_method))

    def _calculate_result_size(self, result: Any) -> int:
        """计算结果大小"""
        try:
            if isinstance(result, dict):
                return len(json.dumps(result))
            elif isinstance(result, (list, tuple)):
                return len(result)
            return 0
        except Exception:
            return 0

    def _calculate_bulk_count(self, body: Any) -> int:
        """计算批量操作数量"""
        try:
            if isinstance(body, list):
                # bulk body 是 action/data 对
                return len(body) // 2
            elif isinstance(body, dict):
                ops = body.get('operations', [])
                return len(ops) if isinstance(ops, list) else 1
            return 1
        except Exception:
            return 1
