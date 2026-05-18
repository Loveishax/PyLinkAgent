"""
MySQL shadow routing interceptor.
"""

import logging
from typing import Any, Dict

from ..pradar import Pradar

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
            connection = original(*args, **kwargs)
            target = {
                "host": kwargs.get("host", business_params["host"]),
                "port": int(kwargs.get("port", business_params["port"])),
                "database": kwargs.get("database") or kwargs.get("db") or business_params["database"],
            }
            self._wrap_connection_cursor(connection, target)
            return connection

        return wrapper

    def _wrap_connection_cursor(self, connection, target: Dict[str, Any]) -> None:
        cursor_method = getattr(connection, "cursor", None)
        if cursor_method is None or getattr(connection, "_pylinkagent_cursor_wrapped", False):
            return

        import functools

        @functools.wraps(cursor_method)
        def wrapped_cursor(*args, **kwargs):
            cursor = cursor_method(*args, **kwargs)
            self._wrap_cursor_execute(cursor, target)
            return cursor

        connection.cursor = wrapped_cursor
        connection._pylinkagent_cursor_wrapped = True

    def _wrap_cursor_execute(self, cursor, target: Dict[str, Any]) -> None:
        if getattr(cursor, "_pylinkagent_execute_wrapped", False):
            return

        execute = getattr(cursor, "execute", None)
        executemany = getattr(cursor, "executemany", None)

        if execute is not None:
            cursor.execute = self._build_execute_wrapper(execute, target, "execute")
        if executemany is not None:
            cursor.executemany = self._build_execute_wrapper(executemany, target, "executemany")
        cursor._pylinkagent_execute_wrapped = True

    def _build_execute_wrapper(self, original, target: Dict[str, Any], call_name: str):
        import functools

        @functools.wraps(original)
        def wrapper(sql, *args, **kwargs):
            span_ctx = self._start_mysql_span(sql, target, call_name)
            try:
                result = original(sql, *args, **kwargs)
                if span_ctx:
                    Pradar.set_result_code("SUCCESS")
                    Pradar.set_response_summary(f"{call_name}=ok")
                return result
            except Exception as exc:
                if span_ctx:
                    Pradar.set_error(str(exc))
                    Pradar.set_result_code("EXCEPTION")
                raise
            finally:
                if span_ctx and Pradar.get_context() is span_ctx:
                    Pradar.end_trace()

        return wrapper

    @staticmethod
    def _summarize_sql(sql: Any) -> str:
        statement = str(sql or "").strip()
        if not statement:
            return "UNKNOWN"
        compact = " ".join(statement.split())
        return compact[:512]

    def _start_mysql_span(self, sql: Any, target: Dict[str, Any], call_name: str):
        if not Pradar.has_context():
            return None

        database = target.get("database") or ""
        host = target.get("host") or "mysql"
        port = int(target.get("port") or 3306)
        summary = self._summarize_sql(sql)
        operation = summary.split(" ", 1)[0].upper() if summary else call_name.upper()
        span_ctx = Pradar.start_child_span(
            service_name=f"{host}:{port}/{database}" if database else f"{host}:{port}",
            method_name=operation,
            middleware_name="MYSQL",
            invoke_type="DB",
            remote_ip=host,
            port=port,
            up_app_name="mysql",
            is_server=False,
        )
        if span_ctx:
            Pradar.set_request_summary(summary)
            Pradar.set_response_summary(f"{call_name}=pending")
        return span_ctx

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
