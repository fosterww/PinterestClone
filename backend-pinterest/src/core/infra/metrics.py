from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

HTTP_REQUESTS_TOTAL = Counter(
    "pinterest_http_requests_total",
    "Total number of HTTP requests handled by the API",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "pinterest_http_request_duration_seconds",
    "Duration of HTTP requests handled by the API",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "pinterest_http_requests_in_progress",
    "Number of HTTP requests currently being processed",
)

NOTIFICATION_EVENTS_TOTAL = Counter(
    "pinterest_notification_events_total",
    "Notification events recorded by the backend",
    ["notification_type", "stage"],
)

_METRICS_EXCLUDED_PATHS = {"/metrics", "/api/v2/metrics"}


def setup_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def prometheus_http_middleware(request: Request, call_next):
        if request.url.path in _METRICS_EXCLUDED_PATHS:
            return await call_next(request)

        method = request.method
        started_at = perf_counter()
        HTTP_REQUESTS_IN_PROGRESS.inc()

        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = perf_counter() - started_at
            status_code = str(response.status_code) if response is not None else "500"
            route_path = _resolve_route_template(request)

            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=route_path,
                status_code=status_code,
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                path=route_path,
            ).observe(duration)
            HTTP_REQUESTS_IN_PROGRESS.dec()


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_notification_event(notification_type: str, stage: str) -> None:
    NOTIFICATION_EVENTS_TOTAL.labels(
        notification_type=notification_type,
        stage=stage,
    ).inc()


def _resolve_route_template(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path or "unmatched"
