"""
MySQL 影子路由拦截器

使用 wrapt 包装 pymysql.connect()，在压测流量时自动路由到影子库。
"""

import logging
from typing import Optional

try:
    import wrapt
    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False

logger = logging.getLogger(__name__)


class MySQLShadowInterceptor:
    """
    MySQL 影子路由拦截器

    包装 pymysql.connect()，压测流量时替换为影子库连接参数。
    """

    def __init__(self, router):
        """
        Args:
            router: ShadowRouter 实例
        """
        self.router = router
        self._original_connect = None
        self._patched = False

    def patch(self) -> bool:
        """启用 pymysql.connect() 拦截"""
        if self._patched:
            return True
        if not WRAPT_AVAILABLE:
            logger.warning("wrapt 不可用，无法启用 MySQL 拦截")
            return False

        try:
            import pymysql
            self._original_connect = pymysql.connect
            pymysql.connect = self._wrapped_connect(self._original_connect)
            self._patched = True
            logger.info("MySQL 影子拦截已启用")
            return True
        except ImportError:
            logger.warning("pymysql 未安装，跳过 MySQL 拦截")
            return False
        except Exception as e:
            logger.error(f"启用 MySQL 拦截失败: {e}")
            return False

    def unpatch(self) -> None:
        """恢复 pymysql.connect() 原始实现"""
        if self._patched and self._original_connect:
            try:
                import pymysql
                pymysql.connect = self._original_connect
                self._patched = False
                logger.info("MySQL 影子拦截已恢复")
            except ImportError:
                pass

    def _wrapped_connect(self, original):
        """包装 pymysql.connect"""
        import functools

        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            # 提取连接参数
            host = kwargs.get('host', kwargs.get('host', 'localhost'))
            port = kwargs.get('port', 3306)
            user = kwargs.get('user', kwargs.get('user', ''))
            password = kwargs.get('password', kwargs.get('password', ''))
            database = kwargs.get('database', kwargs.get('db', ''))

            # 构建原始 URL
            original_url = f"jdbc:mysql://{host}:{port}/{database}"

            # 查询影子路由
            shadow_params = self.router.route_mysql(
                original_url, user, password
            )

            if shadow_params:
                mode = shadow_params.get("mode")
                if mode == "same_db":
                    # 模式 1: 同库影子表 - 保持原连接
                    logger.debug("MySQL 路由: 同库影子表模式")
                else:
                    # 模式 0/2: 替换为影子库
                    kwargs['host'] = shadow_params.get('host', host)
                    kwargs['port'] = shadow_params.get('port', port)
                    kwargs['database'] = shadow_params.get('database', database)
                    kwargs['user'] = shadow_params.get('user', user)
                    kwargs['password'] = shadow_params.get('password', password)
                    logger.info(
                        f"MySQL 路由到影子库: "
                        f"{shadow_params.get('host')}:{shadow_params.get('port')}/{shadow_params.get('database')}"
                    )

            return original(*args, **kwargs)

        return wrapper
