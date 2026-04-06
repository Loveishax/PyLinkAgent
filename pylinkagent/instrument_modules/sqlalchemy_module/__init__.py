"""
PyLinkAgent SQLAlchemy Instrumentation Module

SQLAlchemy 数据库插桩模块，支持:
- SQL 执行拦截
- 影子库路由
- 压测流量识别
"""

from typing import Any, Dict, Optional
import logging
from importlib import import_module

from ..instrument import InstrumentModule

logger = logging.getLogger(__name__)


class SQLAlchemyInstrumentModule(InstrumentModule):
    """
    SQLAlchemy 插桩模块

    拦截 SQLAlchemy 的数据库操作，支持影子库路由
    """

    name = "sqlalchemy"
    version = "1.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._shadow_interceptor = None
        self._original_session = None
        self._original_engine = None

    def patch(self) -> bool:
        """
        执行插桩

        拦截 SQLAlchemy 的 Session 和 Engine
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker, Session

            # 保存原始类
            self._original_engine = create_engine
            self._original_session = sessionmaker

            # 包装 create_engine
            import sqlalchemy
            sqlalchemy.create_engine = self._wrapped_create_engine

            # 包装 Session
            self._patch_session()

            logger.info(f"[{self.name}] SQLAlchemy instrumentation installed")
            return True

        except ImportError as e:
            logger.warning(f"[{self.name}] SQLAlchemy not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"[{self.name}] Failed to instrument: {e}")
            return False

    def _wrapped_create_engine(self, *args, **kwargs):
        """包装的 create_engine 函数"""
        from .shadow import get_router, is_pressure_test

        # 创建原始引擎
        engine = self._original_engine(*args, **kwargs)

        # 附加影子拦截器
        if is_pressure_test():
            router = get_router()
            shadow_config = router.get_shadow_config(str(engine.url))

            if shadow_config:
                logger.info(f"[{self.name}] Shadow config found for engine: {engine.url}")

        return engine

    def _patch_session(self):
        """修补 Session"""
        from sqlalchemy.orm import Session, sessionmaker
        from .shadow import is_pressure_test, get_router

        original_execute = Session.execute

        def wrapped_execute(self, *args, **kwargs):
            if not is_pressure_test():
                return original_execute(self, *args, **kwargs)

            # 获取 SQL
            statement = args[0] if args else kwargs.get('statement')
            if statement:
                sql_str = str(statement)
                # 重写 SQL 表名
                router = get_router()
                # 这里需要获取 engine URL 来匹配配置
                if hasattr(self, 'bind') and self.bind:
                    url = str(self.bind.url)
                    rewritten_sql = router.rewrite_sql(sql_str, url)
                    if rewritten_sql != sql_str:
                        logger.debug(f"[{self.name}] SQL rewritten: {sql_str[:50]}... -> {rewritten_sql[:50]}...")
                        if args:
                            args = (rewritten_sql,) + args[1:]
                        else:
                            kwargs['statement'] = rewritten_sql

            return original_execute(self, *args, **kwargs)

        Session.execute = wrapped_execute
        logger.debug(f"[{self.name}] Session.execute patched")

    def unpatch(self) -> bool:
        """
        移除插桩

        恢复原始的 SQLAlchemy 类
        """
        try:
            if self._original_engine:
                import sqlalchemy
                sqlalchemy.create_engine = self._original_engine

            if self._original_session:
                from sqlalchemy.orm import sessionmaker
                # sessionmaker 是工厂函数，恢复较复杂

            logger.info(f"[{self.name}] SQLAlchemy instrumentation removed")
            return True

        except Exception as e:
            logger.error(f"[{self.name}] Failed to remove instrumentation: {e}")
            return False

    def is_active(self) -> bool:
        """检查模块是否激活"""
        try:
            import sqlalchemy
            return sqlalchemy.create_engine != self._original_engine
        except:
            return False


# 模块导出
def create_module(config: Optional[Dict[str, Any]] = None) -> SQLAlchemyInstrumentModule:
    """创建 SQLAlchemy 插桩模块实例"""
    return SQLAlchemyInstrumentModule(config)


__all__ = ["SQLAlchemyInstrumentModule", "create_module"]
