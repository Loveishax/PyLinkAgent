"""
RedisModule - Redis 客户端插桩实现

负责管理 Redis 模块的插桩生命周期
"""

from typing import Dict, Any, Optional
import logging
import time

from instrument_modules.base import InstrumentModule
from .patcher import RedisPatcher


logger = logging.getLogger(__name__)


class RedisModule(InstrumentModule):
    """
    Redis 客户端插桩模块

    插桩目标：
    - Redis.execute_command
    - RedisPipeline.execute
    - 连接池管理

    采集数据：
    - Redis 命令名称
    - 命令参数（可选）
    - 命令耗时
    - 命令结果（可选，受大小限制）
    - Trace 上下文注入
    """

    name = "redis"
    version = "1.0.0"
    description = "Redis 客户端插桩模块"

    # 依赖的 redis 版本
    dependencies = {"redis": ">=4.0.0"}

    # 默认配置
    default_config = {
        "capture_command_args": False,
        "capture_value": False,
        "max_value_size": 1024,  # 1KB
        "ignored_commands": ["PING", "SELECT", "DBSIZE"],
        "inject_trace_context": True,
        "sample_rate": 1.0,
    }

    def __init__(self):
        super().__init__()
        self._patcher: Optional[RedisPatcher] = None

    def patch(self) -> bool:
        """
        应用 Redis 插桩

        Returns:
            bool: 插桩成功返回 True
        """
        if self._active:
            logger.warning("Redis 模块已处于活动状态")
            return True

        # 1. 检查依赖
        if not self.check_dependencies():
            logger.error("Redis 依赖检查失败")
            return False

        # 2. 检查是否已安装 Redis
        try:
            import redis
            logger.info(f"检测到 redis 版本：{redis.__version__}")
        except ImportError:
            logger.warning("redis 未安装，跳过插桩")
            return False

        # 3. 合并配置
        config = {**self.default_config, **self._config}
        self.set_config(config)

        # 4. 创建并应用 patcher
        self._patcher = RedisPatcher(
            module_name=self.name,
            config=config,
            on_command=self._on_command,
            on_result=self._on_result,
            on_error=self._on_error,
        )

        # 5. 执行插桩
        try:
            success = self._patcher.patch()
            if success:
                self._active = True
                logger.info("Redis 模块插桩成功")
            else:
                logger.error("Redis 模块插桩失败")
            return success

        except Exception as e:
            logger.exception(f"Redis 模块插桩异常：{e}")
            return False

    def unpatch(self) -> bool:
        """
        移除 Redis 插桩

        Returns:
            bool: 移除成功返回 True
        """
        if not self._active:
            return True

        try:
            if self._patcher:
                success = self._patcher.unpatch()
                if success:
                    self._active = False
                    logger.info("Redis 模块插桩已移除")
                return success
            return True

        except Exception as e:
            logger.exception(f"Redis 模块移除插桩异常：{e}")
            return False

    def _on_command(
        self,
        command: str,
        args: tuple,
        kwargs: dict,
        start_time: float,
        instance: Any
    ) -> None:
        """
        命令执行前的回调

        Args:
            command: Redis 命令名称
            args: 命令参数
            kwargs: 命令关键字参数
            start_time: 开始时间
            instance: Redis 实例
        """
        logger.debug(f"[Redis] {command} {args[:3] if args else ''}")

        # 创建 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            context_manager.start_span(
                name=f"Redis {command}",
                attributes={
                    "db.system": "redis",
                    "db.operation": command,
                    "db.redis.command": command,
                    "start_time": start_time,
                }
            )

    def _on_result(
        self,
        command: str,
        args: tuple,
        result: Any,
        elapsed_ms: float,
        instance: Any,
        **kwargs
    ) -> None:
        """
        命令执行后的回调

        Args:
            command: Redis 命令名称
            args: 命令参数
            result: 命令结果
            elapsed_ms: 耗时（毫秒）
            instance: Redis 实例
        """
        logger.debug(f"[Redis] {command} -> OK ({elapsed_ms:.2f}ms)")

        # 结束 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            span = context_manager.end_span()
            if span:
                span.set_attribute("db.redis.status_code", "OK")
                span.set_attribute("db.response.time", elapsed_ms)

        # 上报数据
        self._report_data(
            command=command,
            args=args if self._config.get('capture_command_args', False) else (),
            elapsed_ms=elapsed_ms,
            has_result=result is not None,
            **kwargs
        )

    def _on_error(
        self,
        command: str,
        args: tuple,
        exception: Exception,
        elapsed_ms: float,
        instance: Any
    ) -> None:
        """
        命令执行错误的回调

        Args:
            command: Redis 命令名称
            args: 命令参数
            exception: 异常对象
            elapsed_ms: 耗时（毫秒）
            instance: Redis 实例
        """
        logger.error(f"[Redis] {command} 错误：{exception}")

        # 记录错误 Span
        from pylinkagent import get_agent
        agent = get_agent()
        if agent:
            context_manager = agent.get_context_manager()
            span = context_manager.end_span()
            if span:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(exception))
                span.set_attribute("error.type", type(exception).__name__)

    def _report_data(
        self,
        command: str,
        elapsed_ms: float,
        **kwargs: Any
    ) -> None:
        """
        上报采集数据

        Args:
            command: Redis 命令
            elapsed_ms: 耗时
            **kwargs: 其他数据
        """
        from pylinkagent import get_agent
        from pylinkagent.core.reporter import DataPoint, DataType

        agent = get_agent()
        if not agent:
            return

        # 采样检查
        sampler = agent.get_sampler()
        if not sampler.should_sample(sample_type="trace"):
            return

        # 构建数据
        data = {
            "module": self.name,
            "type": "redis",
            "command": command,
            "elapsed_ms": round(elapsed_ms, 2),
            **kwargs
        }

        # 上报
        reporter = agent.get_reporter()
        reporter.report(DataPoint(
            data_type=DataType.SPAN,
            data=data
        ))
