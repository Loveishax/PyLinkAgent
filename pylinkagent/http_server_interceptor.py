"""
HTTP server ingress tracing and pressure-header detection.
"""

import logging
import os
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .pradar import Pradar, PradarSwitcher

try:
    from wrapt.importer import when_imported

    WRAPT_IMPORT_HOOK_AVAILABLE = True
except ImportError:
    WRAPT_IMPORT_HOOK_AVAILABLE = False


logger = logging.getLogger(__name__)

HeaderList = List[Tuple[str, str]]


class PressureTrafficDetector:
    """Detect pressure traffic from inbound HTTP headers."""

    CLUSTER_TEST_HEADERS = (
        "x-pradar-cluster-test",
        "pradar-cluster-test",
        "p-pradar-cluster-test",
        "x-pylinkagent-cluster-test",
    )

    TRUE_VALUES = {"1", "true", "yes", "on"}

    @classmethod
    def is_cluster_test(cls, headers: Dict[str, str]) -> bool:
        for header_name in cls.CLUSTER_TEST_HEADERS:
            value = headers.get(header_name)
            if value and str(value).strip().lower() in cls.TRUE_VALUES:
                return True
        return False

    @staticmethod
    def from_wsgi_environ(environ: Dict[str, Any]) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for key, value in environ.items():
            if not key.startswith("HTTP_"):
                continue
            header_name = key[5:].replace("_", "-").lower()
            headers[header_name] = str(value)
        if "CONTENT_TYPE" in environ:
            headers["content-type"] = str(environ["CONTENT_TYPE"])
        if "CONTENT_LENGTH" in environ:
            headers["content-length"] = str(environ["CONTENT_LENGTH"])
        return headers

    @staticmethod
    def from_asgi_scope(scope: Dict[str, Any]) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for item in scope.get("headers", []):
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            key, value = item
            if isinstance(key, bytes):
                key = key.decode("latin-1")
            if isinstance(value, bytes):
                value = value.decode("latin-1")
            headers[str(key).lower()] = str(value)
        return headers


class _WSGIResponseWrapper:
    """Keep tracing context alive until the WSGI iterable is exhausted or closed."""

    def __init__(self, iterable: Iterable[Any], finalizer: Callable[[], None]):
        self._iterable = iterable
        self._iterator = iter(iterable)
        self._finalizer = finalizer
        self._finished = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            self._finish()
            raise
        except Exception:
            self._finish()
            raise

    def close(self):
        try:
            close_method = getattr(self._iterable, "close", None)
            if close_method:
                close_method()
        finally:
            self._finish()

    def _finish(self):
        if not self._finished:
            self._finished = True
            self._finalizer()


class HTTPServerTracingInterceptor:
    """Patch Flask/FastAPI entrypoints and build inbound Pradar context."""

    DEFAULT_IGNORED_PATHS = ("/health", "/ready", "/metrics", "/favicon.ico")

    def __init__(self, app_name: Optional[str] = None, ignored_paths: Optional[List[str]] = None):
        self.app_name = app_name or os.getenv("APP_NAME", "default-app")
        self.ignored_paths = tuple(ignored_paths or self.DEFAULT_IGNORED_PATHS)
        self._patched_targets: List[Tuple[Any, str, Any]] = []
        self._started = False
        self._flask_patched = False
        self._fastapi_patched = False

    def start(self) -> bool:
        if self._started:
            return True

        if "flask" in sys.modules:
            self._patch_flask_module(sys.modules["flask"])
        if "fastapi" in sys.modules:
            self._patch_fastapi_module(sys.modules["fastapi"])

        if WRAPT_IMPORT_HOOK_AVAILABLE:
            when_imported("flask")(self._patch_flask_module)
            when_imported("fastapi")(self._patch_fastapi_module)
        else:
            logger.warning("wrapt.importer unavailable, deferred HTTP server patching disabled")

        self._started = True
        logger.info("HTTP server tracing interceptor started")
        return True

    def stop(self) -> None:
        for target, attr_name, original in reversed(self._patched_targets):
            try:
                setattr(target, attr_name, original)
            except Exception:
                logger.debug("Restore %s.%s failed", target, attr_name)
        self._patched_targets = []
        self._flask_patched = False
        self._fastapi_patched = False
        self._started = False
        logger.info("HTTP server tracing interceptor stopped")

    def wrap_wsgi_app(self, wrapped: Callable[..., Iterable[Any]]):
        def tracing_wsgi_app(app_instance, environ, start_response):
            path = environ.get("PATH_INFO", "/")
            if self._should_ignore(path):
                return wrapped(app_instance, environ, start_response)

            headers = PressureTrafficDetector.from_wsgi_environ(environ)
            method = environ.get("REQUEST_METHOD", "GET")
            trace_started = self._enter_request(method, path, headers)

            try:
                response_iterable = wrapped(app_instance, environ, start_response)
                return _WSGIResponseWrapper(
                    response_iterable,
                    lambda: self._exit_request(trace_started),
                )
            except Exception as exc:
                self._exit_request(trace_started, exc)
                raise

        return tracing_wsgi_app

    def wrap_asgi_app(self, wrapped):
        async def tracing_asgi_app(app_instance, scope, receive, send):
            if scope.get("type") != "http":
                return await wrapped(app_instance, scope, receive, send)

            path = scope.get("path", "/")
            if self._should_ignore(path):
                return await wrapped(app_instance, scope, receive, send)

            headers = PressureTrafficDetector.from_asgi_scope(scope)
            method = scope.get("method", "GET")
            trace_started = self._enter_request(method, path, headers)

            try:
                return await wrapped(app_instance, scope, receive, send)
            except Exception as exc:
                self._exit_request(trace_started, exc)
                raise
            finally:
                if trace_started and Pradar.has_context():
                    self._exit_request(trace_started)

        return tracing_asgi_app

    def _patch_flask_module(self, module) -> None:
        if self._flask_patched:
            return
        flask_class = getattr(module, "Flask", None)
        if flask_class is None:
            return
        original = flask_class.wsgi_app

        def patched_wsgi_app(app_instance, environ, start_response):
            wrapped = self.wrap_wsgi_app(original)
            return wrapped(app_instance, environ, start_response)

        flask_class.wsgi_app = patched_wsgi_app
        self._patched_targets.append((flask_class, "wsgi_app", original))
        self._flask_patched = True
        logger.info("Flask ingress tracing patched")

    def _patch_fastapi_module(self, module) -> None:
        if self._fastapi_patched:
            return
        fastapi_class = getattr(module, "FastAPI", None)
        if fastapi_class is None:
            return
        original = fastapi_class.__call__

        async def patched_call(app_instance, scope, receive, send):
            wrapped = self.wrap_asgi_app(original)
            return await wrapped(app_instance, scope, receive, send)

        fastapi_class.__call__ = patched_call
        self._patched_targets.append((fastapi_class, "__call__", original))
        self._fastapi_patched = True
        logger.info("FastAPI ingress tracing patched")

    def _enter_request(self, method: str, path: str, headers: Dict[str, str]) -> bool:
        if Pradar.has_context():
            return False

        Pradar.start_trace(self.app_name, path, method)
        is_cluster_test = PressureTrafficDetector.is_cluster_test(headers)
        Pradar.set_cluster_test(is_cluster_test)
        if is_cluster_test:
            PradarSwitcher.set_has_pressure_request(True)
        return True

    @staticmethod
    def _exit_request(trace_started: bool, error: Optional[Exception] = None) -> None:
        if not trace_started:
            return
        if error is not None:
            Pradar.set_error(str(error))
        if Pradar.has_context():
            Pradar.end_trace()
        Pradar.clear()

    def _should_ignore(self, path: str) -> bool:
        return any(path.startswith(ignored) for ignored in self.ignored_paths)
