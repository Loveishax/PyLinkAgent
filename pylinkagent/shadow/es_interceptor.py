"""
Elasticsearch 影子路由拦截器

包装 elasticsearch.Elasticsearch.__init__()，
在压测流量时自动路由到影子 ES 集群。
"""

import logging

try:
    import wrapt
    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False

logger = logging.getLogger(__name__)


class ESShadowInterceptor:
    """
    Elasticsearch 影子路由拦截器

    包装 elasticsearch.Elasticsearch 构造函数，
    压测流量时替换为影子 ES 集群地址。
    """

    def __init__(self, router):
        """
        Args:
            router: ShadowRouter 实例
        """
        self.router = router
        self._original_es = None
        self._patched = False

    def patch(self) -> bool:
        """启用 ES 拦截"""
        if self._patched:
            return True
        if not WRAPT_AVAILABLE:
            logger.warning("wrapt 不可用，无法启用 ES 拦截")
            return False

        try:
            from elasticsearch import Elasticsearch
            self._original_es = Elasticsearch
            import elasticsearch
            elasticsearch.Elasticsearch = self._wrapped_es_class(self._original_es)
            self._patched = True
            logger.info("Elasticsearch 影子拦截已启用")
            return True
        except ImportError:
            try:
                from elasticsearch7 import Elasticsearch
                self._original_es = Elasticsearch
                import elasticsearch7
                elasticsearch7.Elasticsearch = self._wrapped_es_class(self._original_es)
                self._patched = True
                logger.info("Elasticsearch7 影子拦截已启用")
                return True
            except ImportError:
                logger.warning("elasticsearch 未安装，跳过 ES 拦截")
                return False
        except Exception as e:
            logger.error(f"启用 ES 拦截失败: {e}")
            return False

    def unpatch(self) -> None:
        """恢复原始 Elasticsearch"""
        if self._patched and self._original_es:
            try:
                import elasticsearch
                elasticsearch.Elasticsearch = self._original_es
                self._patched = False
                logger.info("ES 影子拦截已恢复")
            except ImportError:
                try:
                    import elasticsearch7
                    elasticsearch7.Elasticsearch = self._original_es
                    self._patched = False
                except ImportError:
                    pass

    def _wrapped_es_class(self, original_cls):
        """包装 Elasticsearch 类"""
        import functools

        class ShadowESProxy(original_cls):
            """Shadow Elasticsearch 代理"""

            def __init__(self, hosts=None, *args, **kwargs):
                original_hosts = hosts or kwargs.get('hosts', [])

                # 查询影子路由
                shadow_params = self._router.route_es(
                    original_hosts if isinstance(original_hosts, list) else [original_hosts]
                )

                if shadow_params:
                    kwargs['hosts'] = shadow_params['hosts']
                    if shadow_params.get('api_key'):
                        kwargs['api_key'] = shadow_params['api_key']
                    if shadow_params.get('basic_auth'):
                        kwargs['basic_auth'] = shadow_params['basic_auth']
                    logger.info(
                        f"ES 路由到影子集群: {shadow_params['hosts']}"
                    )

                super().__init__(*args, **kwargs)

            @property
            def _router(self):
                return self.__class__._shadow_router

        ShadowESProxy._shadow_router = self.router
        return ShadowESProxy
