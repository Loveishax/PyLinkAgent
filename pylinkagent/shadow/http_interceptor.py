"""
HTTP client shadow routing interceptor.
"""

import logging

try:
    import wrapt

    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False


logger = logging.getLogger(__name__)

CLUSTER_TEST_HEADER = "X-Pradar-Cluster-Test"
CLUSTER_TEST_VALUE = "1"


class HTTPShadowInterceptor:
    """Inject pressure headers into outbound HTTP traffic."""

    def __init__(self, router):
        self.router = router
        self._patched = False
        self._original_requests_request = None
        self._original_httpx_send = None
        self._original_httpx_async_send = None

    def patch(self) -> bool:
        if self._patched:
            return True
        if not WRAPT_AVAILABLE:
            logger.warning("wrapt unavailable, skip HTTP shadow interceptor")
            return False

        success = False
        try:
            self._patch_requests()
            success = True
        except Exception as exc:
            logger.debug("Patch requests failed: %s", exc)

        try:
            self._patch_httpx()
            success = True
        except Exception as exc:
            logger.debug("Patch httpx failed: %s", exc)

        if success:
            self._patched = True
            logger.info("HTTP shadow interceptor enabled")
        return success

    def unpatch(self) -> None:
        if not self._patched:
            return

        try:
            if self._original_requests_request:
                import requests

                requests.Session.request = self._original_requests_request
            if self._original_httpx_send or self._original_httpx_async_send:
                import httpx

                if self._original_httpx_send:
                    httpx.Client.send = self._original_httpx_send
                if self._original_httpx_async_send:
                    httpx.AsyncClient.send = self._original_httpx_async_send
        except Exception as exc:
            logger.debug("Restore HTTP shadow interceptor failed: %s", exc)

        self._patched = False
        logger.info("HTTP shadow interceptor disabled")

    def _patch_requests(self) -> None:
        import functools
        import requests

        self._original_requests_request = requests.Session.request

        @functools.wraps(self._original_requests_request)
        def wrapped_request(session, method, url, *args, **kwargs):
            headers = dict(kwargs.get("headers") or {})
            if self.router.should_route():
                headers[CLUSTER_TEST_HEADER] = CLUSTER_TEST_VALUE
                kwargs["headers"] = headers
                logger.debug("Injected pressure header into requests: %s", url)
            return self._original_requests_request(session, method, url, *args, **kwargs)

        requests.Session.request = wrapped_request

    def _patch_httpx(self) -> None:
        import functools
        import httpx

        self._original_httpx_send = httpx.Client.send
        self._original_httpx_async_send = httpx.AsyncClient.send

        @functools.wraps(self._original_httpx_send)
        def wrapped_send(client, request, *args, **kwargs):
            if self.router.should_route():
                request.headers[CLUSTER_TEST_HEADER] = CLUSTER_TEST_VALUE
                logger.debug("Injected pressure header into httpx: %s", request.url)
            return self._original_httpx_send(client, request, *args, **kwargs)

        @functools.wraps(self._original_httpx_async_send)
        async def wrapped_async_send(client, request, *args, **kwargs):
            if self.router.should_route():
                request.headers[CLUSTER_TEST_HEADER] = CLUSTER_TEST_VALUE
            return await self._original_httpx_async_send(client, request, *args, **kwargs)

        httpx.Client.send = wrapped_send
        httpx.AsyncClient.send = wrapped_async_send
