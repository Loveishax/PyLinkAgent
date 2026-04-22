"""
HTTP 客户端影子路由拦截器

包装 requests 和 httpx，在压测流量时:
- 注入 X-Pradar-Cluster-Test 标头以传递压测标记
"""

import logging

try:
    import wrapt
    WRAPT_AVAILABLE = True
except ImportError:
    WRAPT_AVAILABLE = False

logger = logging.getLogger(__name__)

# 压测标头
CLUSTER_TEST_HEADER = "X-Pradar-Cluster-Test"
CLUSTER_TEST_VALUE = "1"


class HTTPShadowInterceptor:
    """
    HTTP 客户端影子路由拦截器

    在压测流量请求中注入 Cluster-Test 标头，
    使下游服务也能识别压测流量并路由到影子。
    """

    def __init__(self, router):
        """
        Args:
            router: ShadowRouter 实例
        """
        self.router = router
        self._patched = False

    def patch(self) -> bool:
        """启用 HTTP 拦截"""
        if self._patched:
            return True
        if not WRAPT_AVAILABLE:
            logger.warning("wrapt 不可用，无法启用 HTTP 拦截")
            return False

        success = False

        # 拦截 requests
        try:
            self._patch_requests()
            success = True
        except Exception as e:
            logger.debug(f"拦截 requests 失败: {e}")

        # 拦截 httpx
        try:
            self._patch_httpx()
            success = True
        except Exception as e:
            logger.debug(f"拦截 httpx 失败: {e}")

        if success:
            self._patched = True
            logger.info("HTTP 影子拦截已启用")

        return success

    def unpatch(self) -> None:
        """恢复 HTTP 客户端"""
        if self._patched:
            self._patched = False
            logger.info("HTTP 影子拦截已恢复")

    def _patch_requests(self) -> None:
        """包装 requests 库"""
        import functools
        import requests

        original_request = requests.Session.request

        @functools.wraps(original_request)
        def wrapped_request(self_obj, method, url, *args, **kwargs):
            headers = kwargs.get('headers', {})
            if self._router.should_route():
                headers[CLUSTER_TEST_HEADER] = CLUSTER_TEST_VALUE
                kwargs['headers'] = headers
                logger.debug(f"requests 注入压测标头: {url}")
            return original_request(self_obj, method, url, *args, **kwargs)

        requests.Session.request = wrapped_request

    def _patch_httpx(self) -> None:
        """包装 httpx 库"""
        import functools
        import httpx

        original_send = httpx.Client.send

        @functools.wraps(original_send)
        def wrapped_send(self_obj, request, *args, **kwargs):
            if self._router.should_route():
                request.headers[CLUSTER_TEST_HEADER] = CLUSTER_TEST_VALUE
                logger.debug(f"httpx 注入压测标头: {request.url}")
            return original_send(self_obj, request, *args, **kwargs)

        httpx.Client.send = wrapped_send

        # 也包装异步客户端
        original_async_send = httpx.AsyncClient.send

        @functools.wraps(original_async_send)
        async def wrapped_async_send(self_obj, request, *args, **kwargs):
            if self._router.should_route():
                request.headers[CLUSTER_TEST_HEADER] = CLUSTER_TEST_VALUE
            return await original_async_send(self_obj, request, *args, **kwargs)

        httpx.AsyncClient.send = wrapped_async_send
