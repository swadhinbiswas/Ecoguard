import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.logging import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.perf_counter()

        logger.info(
            f"Request started: {request.method} {request.url.path} - ID: {request_id}"
        )

        try:
            response = await call_next(request)
            process_time = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"Request completed: {request.method} {request.url.path} - "
                f"Status: {response.status_code} - Latency: {process_time:.2f}ms - ID: {request_id}"
            )

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = str(process_time)
            return response

        except Exception as e:
            process_time = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path} - "
                f"Error: {str(e)} - Latency: {process_time:.2f}ms - ID: {request_id}"
            )
            raise
