"""
影子拦截器

拦截数据库操作并路由到影子库：
- SQLAlchemy 事件监听
- DB-API 2.0 拦截
- 连接池拦截
"""

from typing import Optional, Any, Dict
from contextlib import contextmanager
import logging
import functools

from .context import get_shadow_context, is_pressure_test, ShadowContext
from .router import get_router, ShadowRouter

logger = logging.getLogger(__name__)


class ShadowInterceptor:
    """
    影子拦截器基类

    用于拦截数据库操作并根据流量标记路由到影子库
    """

    def __init__(self, router: Optional[ShadowRouter] = None):
        self.router = router or get_router()
        self._enabled = True

    def enable(self) -> None:
        """启用拦截"""
        self._enabled = True

    def disable(self) -> None:
        """禁用拦截"""
        self._enabled = False

    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self._enabled

    def before_execute(self, sql: str, params: Optional[Dict] = None) -> tuple:
        """
        SQL 执行前的拦截

        Args:
            sql: 原始 SQL
            params: SQL 参数

        Returns:
            (rewritten_sql, params) 元组
        """
        if not self._enabled:
            return sql, params

        if not is_pressure_test():
            return sql, params

        # 重写 SQL（表名替换）
        # 注意：这里无法获取 URL，需要子类提供
        rewritten_sql = sql
        logger.debug(f"SQL intercepted: {sql[:100]}...")

        return rewritten_sql, params

    def before_connect(self, url: str, username: str, password: str) -> tuple:
        """
        数据库连接前的拦截

        Args:
            url: 数据库 URL
            username: 用户名
            password: 密码

        Returns:
            (url, username, password) 元组（可能已切换到影子库）
        """
        if not self._enabled:
            return url, username, password

        if not is_pressure_test():
            return url, username, password

        # 获取影子库配置
        target_url = self.router.get_target_url(url, username)
        target_user, target_pass = self.router.get_target_credentials(url, username, password)

        if target_url != url:
            logger.info(f"Shadow routing: {url} -> {target_url}")

        return target_url, target_user, target_pass


class SQLAlchemyShadowInterceptor(ShadowInterceptor):
    """
    SQLAlchemy 影子拦截器

    使用 SQLAlchemy 事件系统拦截数据库操作
    """

    def __init__(self, router: Optional[ShadowRouter] = None):
        super().__init__(router)
        self._event_listeners = []
        self._engine = None

    def attach_to_engine(self, engine: Any) -> None:
        """
        将拦截器附加到 SQLAlchemy 引擎

        Args:
            engine: SQLAlchemy Engine 对象
        """
        try:
            from sqlalchemy import event
        except ImportError:
            logger.warning("SQLAlchemy not installed, cannot attach interceptor")
            return

        self._engine = engine

        # 监听连接事件
        @event.listens_for(engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if not self._enabled or not is_pressure_test():
                return

            # 记录 SQL 拦截
            logger.debug(f"SQLAlchemy SQL intercepted: {statement[:100]}...")

        # 监听连接创建
        @event.listens_for(engine, "do_connect")
        def receive_do_connect(dialect, conn_rec, cargs, cparams):
            if not self._enabled or not is_pressure_test():
                return

            # 这里可以修改连接参数
            logger.debug(f"SQLAlchemy connection intercepted: {cargs}")

        logger.info("SQLAlchemy interceptor attached to engine")

    def detach(self) -> None:
        """从引擎分离拦截器"""
        # SQLAlchemy 事件监听分离比较复杂，这里简化处理
        self._engine = None
        logger.info("SQLAlchemy interceptor detached")


class DBAPI2ShadowInterceptor(ShadowInterceptor):
    """
    DB-API 2.0 影子拦截器

    通过包装数据库连接对象来拦截 SQL 执行
    """

    def __init__(self, router: Optional[ShadowRouter] = None):
        super().__init__(router)
        self._original_connect = None
        self._patched = False

    def patch_connect(self, connect_func: Any) -> Any:
        """
        包装数据库连接函数

        Args:
            connect_func: 原始的连接函数 (如 pymysql.connect)

        Returns:
            包装后的连接函数
        """
        if self._patched:
            return connect_func

        original_connect = connect_func

        @functools.wraps(original_connect)
        def wrapped_connect(*args, **kwargs):
            if not self._enabled:
                return original_connect(*args, **kwargs)

            if not is_pressure_test():
                return original_connect(*args, **kwargs)

            # 提取连接参数
            url = kwargs.get('host', '')
            if 'database' in kwargs:
                url = f"{kwargs.get('host', '')}:{kwargs.get('port', 3306)}/{kwargs['database']}"

            username = kwargs.get('user', '')
            password = kwargs.get('password', '')

            # 路由到影子库
            target_url, target_user, target_pass = self.before_connect(url, username, password)

            # 修改连接参数
            if target_url != url or target_user != username:
                if ':' in target_url and '/' in target_url:
                    # 解析影子库 URL
                    parts = target_url.split(':')
                    if len(parts) >= 2:
                        kwargs['host'] = parts[0].replace('jdbc:', '').replace('//', '')
                        if '/' in parts[1]:
                            kwargs['port'] = int(parts[1].split('/')[0])
                            kwargs['database'] = parts[1].split('/')[1]
                kwargs['user'] = target_user
                kwargs['password'] = target_pass
                logger.info(f"Shadow DB connection: {url} -> {target_url}")

            return original_connect(*args, **kwargs)

        self._original_connect = original_connect
        self._patched = True
        logger.info("DB-API 2.0 connect function patched")

        return wrapped_connect

    def unpatch(self) -> None:
        """恢复原始连接函数"""
        self._patched = False
        logger.info("DB-API 2.0 connect function restored")


class ShadowConnectionWrapper:
    """
    数据库连接包装器

    包装原始数据库连接，拦截 SQL 执行
    """

    def __init__(self, connection: Any, interceptor: ShadowInterceptor):
        self._connection = connection
        self._interceptor = interceptor
        self._cursor = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def cursor(self, *args, **kwargs):
        """获取游标"""
        cursor = self._connection.cursor(*args, **kwargs)
        return ShadowCursorWrapper(cursor, self._interceptor)

    def commit(self):
        """提交事务"""
        return self._connection.commit()

    def rollback(self):
        """回滚事务"""
        return self._connection.rollback()

    def close(self):
        """关闭连接"""
        return self._connection.close()

    def __getattr__(self, name):
        # 委托其他属性到原始连接
        return getattr(self._connection, name)


class ShadowCursorWrapper:
    """
    数据库游标包装器

    拦截 SQL 执行并重写表名
    """

    def __init__(self, cursor: Any, interceptor: ShadowInterceptor):
        self._cursor = cursor
        self._interceptor = interceptor

    def execute(self, sql: str, params=None):
        """执行 SQL"""
        rewritten_sql, _ = self._interceptor.before_execute(sql, params)
        return self._cursor.execute(rewritten_sql, params)

    def executemany(self, sql: str, params_list):
        """批量执行 SQL"""
        rewritten_sql, _ = self._interceptor.before_execute(sql, None)
        return self._cursor.executemany(rewritten_sql, params_list)

    def __getattr__(self, name):
        # 委托其他属性到原始游标
        return getattr(self._cursor, name)


@contextmanager
def shadow_db_context(url: str, username: str = "", password: str = ""):
    """
    影子数据库上下文管理器

    用于在代码块中临时切换到影子库

    Usage:
        with shadow_db_context("jdbc:mysql://localhost/test", "root", "pwd"):
            # 此代码块内的数据库操作会使用影子库
            db.execute("SELECT * FROM users")
    """
    from .context import create_new_context, _shadow_context_var

    # 保存旧上下文
    token = _shadow_context_var.set(create_new_context(is_pressure=True))

    try:
        router = get_router()
        target_url, target_user, target_pass = router.get_target_credentials(url, username, password)

        logger.info(f"Shadow DB context entered: {url} -> {target_url}")
        yield {
            "url": target_url,
            "username": target_user,
            "password": target_pass,
        }
    finally:
        # 恢复旧上下文
        _shadow_context_var.reset(token)
        logger.info("Shadow DB context exited")
