"""
MySQL shadow routing interceptor.
"""

import logging
from typing import Any, Dict

try:
    import wrapt

    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False


logger = logging.getLogger(__name__)


class MySQLShadowInterceptor:
    """Patch `pymysql.connect()` and reroute pressure traffic to shadow DB."""

    def __init__(self, router):
        self.router = router
        self._original_connect = None
        self._patched = False

    def patch(self) -> bool:
        if self._patched:
            return True
        if not WRAPT_AVAILABLE:
            logger.warning("wrapt unavailable, skip MySQL shadow interceptor")
            return False

        try:
            import pymysql

            self._original_connect = pymysql.connect
            pymysql.connect = self._wrapped_connect(self._original_connect)
            self._patched = True
            logger.info("MySQL shadow interceptor enabled")
            return True
        except ImportError:
            logger.warning("pymysql not installed, skip MySQL shadow interceptor")
            return False
        except Exception as exc:
            logger.error("Enable MySQL shadow interceptor failed: %s", exc)
            return False

    def unpatch(self) -> None:
        if self._patched and self._original_connect:
            try:
                import pymysql

                pymysql.connect = self._original_connect
            except ImportError:
                pass
            self._patched = False
            logger.info("MySQL shadow interceptor disabled")

    def _wrapped_connect(self, original):
        import functools

        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            business_params = self._extract_connect_params(args, kwargs)
            original_url = (
                f"jdbc:mysql://{business_params['host']}:{business_params['port']}/"
                f"{business_params['database']}"
            )

            shadow_params = self.router.route_mysql(
                original_url,
                business_params["user"],
                business_params["password"],
            )
            if shadow_params and shadow_params.get("mode") != "same_db":
                kwargs["host"] = shadow_params.get("host", business_params["host"])
                kwargs["port"] = shadow_params.get("port", business_params["port"])
                shadow_database = shadow_params.get("database", business_params["database"])
                kwargs["database"] = shadow_database
                kwargs["db"] = shadow_database
                kwargs["user"] = shadow_params.get("user", business_params["user"])
                kwargs["password"] = shadow_params.get("password", business_params["password"])
                logger.info(
                    "MySQL rerouted to shadow DB: %s:%s/%s",
                    kwargs["host"],
                    kwargs["port"],
                    shadow_database,
                )
            return original(*args, **kwargs)

        return wrapper

    @staticmethod
    def _extract_connect_params(args: tuple, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract business DB params from positional and keyword arguments."""
        host = kwargs.get("host") or (args[0] if len(args) > 0 else "localhost")
        user = kwargs.get("user") or (args[1] if len(args) > 1 else "")
        password = kwargs.get("password") or (args[2] if len(args) > 2 else "")
        database = (
            kwargs.get("database")
            or kwargs.get("db")
            or (args[3] if len(args) > 3 else "")
        )
        port = kwargs.get("port") or 3306
        return {
            "host": host,
            "port": int(port),
            "user": user,
            "password": password,
            "database": database,
        }
