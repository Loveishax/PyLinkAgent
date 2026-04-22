"""
Redis 影子路由拦截器

包装 redis.Redis.__init__() / redis.Redis.from_url()，
在压测流量时自动路由到影子 Redis 服务器。
"""

import logging

try:
    import wrapt
    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False

logger = logging.getLogger(__name__)


class RedisShadowInterceptor:
    """
    Redis 影子路由拦截器

    包装 redis.Redis 和 redis.cluster.RedisCluster，
    压测流量时替换为影子 Redis 连接参数。
    """

    def __init__(self, router):
        """
        Args:
            router: ShadowRouter 实例
        """
        self.router = router
        self._original_redis = None
        self._original_from_url = None
        self._patched = False

    def patch(self) -> bool:
        """启用 Redis 拦截"""
        if self._patched:
            return True
        if not WRAPT_AVAILABLE:
            logger.warning("wrapt 不可用，无法启用 Redis 拦截")
            return False

        try:
            import redis
            self._original_redis = redis.Redis
            self._original_from_url = redis.Redis.from_url

            redis.Redis = self._wrapped_redis_class(self._original_redis)
            self._patched = True
            logger.info("Redis 影子拦截已启用")
            return True
        except ImportError:
            logger.warning("redis 未安装，跳过 Redis 拦截")
            return False
        except Exception as e:
            logger.error(f"启用 Redis 拦截失败: {e}")
            return False

    def unpatch(self) -> None:
        """恢复原始 Redis"""
        if self._patched and self._original_redis:
            try:
                import redis
                redis.Redis = self._original_redis
                self._patched = False
                logger.info("Redis 影子拦截已恢复")
            except ImportError:
                pass

    def _wrapped_redis_class(self, original_cls):
        """包装 Redis 类"""
        import functools

        class ShadowRedisProxy(original_cls):
            """Shadow Redis 代理"""

            def __init__(self, *args, **kwargs):
                host = kwargs.get('host', 'localhost')
                port = kwargs.get('port', 6379)
                db = kwargs.get('db', kwargs.get('db', 0))
                password = kwargs.get('password')

                # 查询影子路由
                shadow_params = self._router.route_redis(host, port)

                if shadow_params:
                    kwargs['host'] = shadow_params['host']
                    kwargs['port'] = shadow_params['port']
                    kwargs['db'] = shadow_params.get('db', db)
                    if shadow_params.get('password'):
                        kwargs['password'] = shadow_params['password']
                    logger.info(
                        f"Redis 路由到影子: "
                        f"{shadow_params['host']}:{shadow_params['port']}"
                    )

                super().__init__(*args, **kwargs)

            @property
            def _router(self):
                return self.__class__._shadow_router

        ShadowRedisProxy._shadow_router = self.router
        return ShadowRedisProxy
