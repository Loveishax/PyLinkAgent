"""
SQLAlchemy 影子路由拦截器

包装 sqlalchemy.create_engine()，在压测流量时路由到影子库。
支持 ds_type 0/2 (影子库) 和 ds_type 1 (同库影子表 + SQL 重写)。
"""

import logging

try:
    import wrapt
    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False

from .sql_rewriter import ShadowSQLRewriter

logger = logging.getLogger(__name__)


class SQLAlchemyShadowInterceptor:
    """
    SQLAlchemy 影子路由拦截器

    包装 create_engine()，压测时:
    - ds_type 0/2: 重写 engine URL 到影子库
    - ds_type 1: 通过事件系统注入 SQL 重写
    """

    def __init__(self, router):
        """
        Args:
            router: ShadowRouter 实例
        """
        self.router = router
        self._original_create_engine = None
        self._patched = False

    def patch(self) -> bool:
        """启用 SQLAlchemy 拦截"""
        if self._patched:
            return True
        if not WRAPT_AVAILABLE:
            logger.warning("wrapt 不可用，无法启用 SQLAlchemy 拦截")
            return False

        try:
            from sqlalchemy import create_engine as _create_engine
            self._original_create_engine = _create_engine
            import sqlalchemy
            sqlalchemy.create_engine = self._wrapped_create_engine(self._original_create_engine)
            self._patched = True
            logger.info("SQLAlchemy 影子拦截已启用")
            return True
        except ImportError:
            logger.warning("SQLAlchemy 未安装，跳过 SQLAlchemy 拦截")
            return False
        except Exception as e:
            logger.error(f"启用 SQLAlchemy 拦截失败: {e}")
            return False

    def unpatch(self) -> None:
        """恢复原始 create_engine"""
        if self._patched and self._original_create_engine:
            try:
                import sqlalchemy
                sqlalchemy.create_engine = self._original_create_engine
                self._patched = False
                logger.info("SQLAlchemy 影子拦截已恢复")
            except ImportError:
                pass

    def _wrapped_create_engine(self, original):
        """包装 create_engine"""
        import functools

        @functools.wraps(original)
        def wrapper(url, *args, **kwargs):
            url_str = str(url)

            # 检查是否匹配影子配置
            shadow_config = self.router.config_center.get_db_config(url_str)

            if shadow_config and self.router.should_route():
                if shadow_config.ds_type in (0, 2):
                    # 模式 0/2: 影子库 - 替换 URL
                    shadow_url = shadow_config.shadow_pymysql_url()
                    logger.info(f"SQLAlchemy 路由到影子库: {shadow_url}")
                    return original(shadow_url, *args, **kwargs)

                elif shadow_config.ds_type == 1:
                    # 模式 1: 同库影子表 - 注入 SQL 重写
                    logger.debug("SQLAlchemy: 同库影子表模式，注入 SQL 重写")
                    engine = original(url, *args, **kwargs)
                    self._inject_sql_rewrite(engine, shadow_config)
                    return engine

            return original(url, *args, **kwargs)

        return wrapper

    def _inject_sql_rewrite(self, engine, config) -> None:
        """通过 SQLAlchemy 事件系统注入 SQL 重写"""
        try:
            from sqlalchemy import event

            rewriter = ShadowSQLRewriter(config.business_shadow_tables)

            @event.listens_for(engine, "before_cursor_execute")
            def before_execute(conn, clause, multiparams, params, execution_options):
                """在执行前重写 SQL"""
                if self.router.should_route():
                    original_sql = str(clause)
                    rewritten_sql = rewriter.rewrite(original_sql)
                    if rewritten_sql != original_sql:
                        logger.debug(f"SQL 重写: {original_sql[:100]} -> {rewritten_sql[:100]}")
                        # 替换 SQL 语句
                        conn.execute = lambda *a, **kw: self._execute_with_rewrite(
                            conn, rewritten_sql, multiparams, params
                        )

        except Exception as e:
            logger.error(f"注入 SQL 重写失败: {e}")

    @staticmethod
    def _execute_with_rewrite(conn, sql, multiparams, params):
        """执行重写后的 SQL"""
        cursor = conn.connection.cursor()
        cursor.execute(sql, params if params else (multiparams[0] if multiparams else {}))
        return cursor
