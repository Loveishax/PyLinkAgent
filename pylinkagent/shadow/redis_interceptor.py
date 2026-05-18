"""
Redis 影子路由拦截器

包装 redis.Redis.__init__() / redis.Redis.from_url()，
在压测流量时自动路由到影子 Redis 服务器。
"""

import logging

from ..pradar import Pradar

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
                self._pylinkagent_shadow_target = {
                    "host": kwargs.get("host", host),
                    "port": int(kwargs.get("port", port)),
                    "db": int(kwargs.get("db", db) or 0),
                }

            @property
            def _router(self):
                return self.__class__._shadow_router

            def execute_command(self, *args, **kwargs):
                span_ctx = self.__class__._start_redis_span(
                    self._pylinkagent_shadow_target,
                    args,
                )
                try:
                    result = super().execute_command(*args, **kwargs)
                    if span_ctx:
                        Pradar.set_result_code("SUCCESS")
                        Pradar.set_response_summary("redis=ok")
                    return result
                except Exception as exc:
                    if span_ctx:
                        Pradar.set_error(str(exc))
                        Pradar.set_result_code("EXCEPTION")
                    raise
                finally:
                    if span_ctx and Pradar.get_context() is span_ctx:
                        Pradar.end_trace()

        ShadowRedisProxy._shadow_router = self.router
        ShadowRedisProxy._start_redis_span = staticmethod(self._start_redis_span)
        return ShadowRedisProxy

    @staticmethod
    def _start_redis_span(target, command_args):
        if not Pradar.has_context():
            return None

        command_name = "UNKNOWN"
        if command_args:
            command_name = str(command_args[0]).upper()
        host = target.get("host", "redis")
        port = int(target.get("port", 6379))
        db = int(target.get("db", 0))
        span_ctx = Pradar.start_child_span(
            service_name=f"{host}:{port}/{db}",
            method_name=command_name,
            middleware_name="REDIS",
            invoke_type="CACHE",
            remote_ip=host,
            port=port,
            up_app_name="redis",
            is_server=False,
        )
        if span_ctx:
            summary = " ".join(str(arg) for arg in command_args[:4])[:256]
            Pradar.set_request_summary(summary)
            Pradar.set_response_summary("redis=pending")
        return span_ctx
