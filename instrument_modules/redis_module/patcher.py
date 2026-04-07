"""
RedisPatcher - Redis 客户端插桩实现

负责拦截 Redis 命令执行并采集数据
"""

from typing import Any, Optional, Callable, Dict
import logging
import time
import functools

import wrapt

logger = logging.getLogger(__name__)


class RedisPatcher:
    """
    Redis 客户端插桩器

    支持 redis-py 库的插桩:
    - Redis.execute_command
    - RedisPipeline.execute
    - ConnectionPool 连接管理
    """

    def __init__(
        self,
        module_name: str,
        config: Dict[str, Any],
        on_command: Optional[Callable] = None,
        on_result: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.module_name = module_name
        self.config = config
        self.on_command = on_command
        self.on_result = on_result
        self.on_error = on_error
        self._patched = False
        self._original_methods = {}

    def patch(self) -> bool:
        """应用 Redis 插桩"""
        if self._patched:
            logger.warning("Redis 已经处于插桩状态")
            return True

        try:
            import redis
        except ImportError:
            logger.warning("redis 未安装，跳过插桩")
            return False

        logger.info(f"检测到 redis 版本：{redis.__version__}")

        # 拦截 Redis.execute_command
        self._patch_redis_class()

        # 拦截 Pipeline.execute
        self._patch_pipeline()

        self._patched = True
        logger.info("Redis 插桩成功")
        return True

    def unpatch(self) -> bool:
        """移除 Redis 插桩"""
        if not self._patched:
            return True

        try:
            import redis

            # 恢复原始方法
            if 'Redis.execute_command' in self._original_methods:
                redis.Redis.execute_command = self._original_methods['Redis.execute_command']

            if 'Pipeline.execute' in self._original_methods:
                redis.client.Pipeline.execute = self._original_methods['Pipeline.execute']

            self._original_methods.clear()
            self._patched = False
            logger.info("Redis 插桩已移除")
            return True

        except Exception as e:
            logger.exception(f"Redis 插桩移除异常：{e}")
            return False

    def _patch_redis_class(self) -> None:
        """拦截 Redis 类"""
        import redis

        # 保存原始方法
        self._original_methods['Redis.execute_command'] = redis.Redis.execute_command

        @wrapt.decorator
        def execute_command_wrapper(wrapped, instance, args, kwargs):
            if not args:
                return wrapped(*args, **kwargs)

            # 获取命令名称
            command_name = args[0].upper() if isinstance(args[0], str) else str(args[0])

            # 检查是否忽略该命令
            ignored_commands = self.config.get('ignored_commands', ['PING', 'SELECT'])
            if command_name in ignored_commands:
                return wrapped(*args, **kwargs)

            start_time = time.time()

            # 前置钩子
            if self.on_command:
                self.on_command(
                    command=command_name,
                    args=args[1:],
                    kwargs=kwargs,
                    start_time=start_time,
                    instance=instance
                )

            try:
                result = wrapped(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                # 后置钩子
                if self.on_result:
                    self.on_result(
                        command=command_name,
                        args=args[1:],
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
                        command=command_name,
                        args=args[1:],
                        exception=e,
                        elapsed_ms=elapsed_ms,
                        instance=instance
                    )

                raise

        # 应用包装
        redis.Redis.execute_command = execute_command_wrapper(redis.Redis.execute_command)

    def _patch_pipeline(self) -> None:
        """拦截 Pipeline"""
        try:
            import redis.client
        except ImportError:
            try:
                import redis
            except ImportError:
                return

        pipeline_class = getattr(redis.client, 'Pipeline', None)
        if not pipeline_class:
            return

        self._original_methods['Pipeline.execute'] = pipeline_class.execute

        @wrapt.decorator
        def pipeline_execute_wrapper(wrapped, instance, args, kwargs):
            start_time = time.time()

            try:
                result = wrapped(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                # 获取 pipeline 中的命令数量
                command_count = len(getattr(instance, 'command_stack', []))

                if self.on_result:
                    self.on_result(
                        command='PIPELINE',
                        args=[],
                        result=result,
                        elapsed_ms=elapsed_ms,
                        command_count=command_count,
                        instance=instance
                    )

                return result

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000

                if self.on_error:
                    self.on_error(
                        command='PIPELINE',
                        args=[],
                        exception=e,
                        elapsed_ms=elapsed_ms,
                        instance=instance
                    )

                raise

        pipeline_class.execute = pipeline_execute_wrapper(pipeline_class.execute)
