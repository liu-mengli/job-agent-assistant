import time
from uuid import uuid4

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求注入 request_id，同请求链路上的所有日志自动携带"""

    async def dispatch(self, request, call_next):
        request_id = uuid4().hex[:8]
        start = time.time()

        # contextualize 利用 contextvars 让 logger 在整个请求链路上自动带 request_id
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)
            elapsed = (time.time() - start) * 1000
            logger.info(f"{request.method} {request.url.path} {response.status_code} {elapsed:.1f}ms")
            return response
