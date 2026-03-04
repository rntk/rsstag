"""WSGI middleware that emits OTel spans and metrics for every HTTP request."""

import hashlib
import time
from typing import Callable, Optional


def make_otel_wsgi_middleware(wsgi_app: Callable, url_map=None) -> Callable:
    """Wrap a WSGI callable with OTel tracing and metrics.

    Args:
        wsgi_app: The original WSGI callable (e.g. app.set_response).
        url_map: A werkzeug Map object used for low-cardinality route matching.
                 If None, the raw path is used as the route label.

    Returns:
        A WSGI-compatible callable.
    """
    try:
        from opentelemetry import trace, metrics, context as otel_context
        from opentelemetry.propagate import extract
        from opentelemetry.trace import StatusCode
        from opentelemetry.semconv.trace import SpanAttributes

        tracer = trace.get_tracer("rsstag.web")
        meter = metrics.get_meter("rsstag.web")

        request_counter = meter.create_counter(
            "http.server.request.count",
            description="Total HTTP requests received",
        )
        request_duration = meter.create_histogram(
            "http.server.request.duration",
            unit="s",
            description="HTTP request duration in seconds",
        )
        active_requests = meter.create_up_down_counter(
            "http.server.active_requests",
            description="Number of active HTTP requests",
        )
    except Exception:
        # OTel not available – return unwrapped app
        return wsgi_app

    def _get_route(environ: dict) -> str:
        if url_map is not None:
            try:
                adapter = url_map.bind_to_environ(environ)
                rule, _ = adapter.match(return_rule=True)
                return rule.rule  # e.g. "/posts/<string:tag>"
            except Exception:
                pass
        return environ.get("PATH_INFO", "/")

    def middleware(environ: dict, start_response: Callable) -> object:
        method = environ.get("REQUEST_METHOD", "GET")
        route = _get_route(environ)

        ctx = extract(environ)
        token = otel_context.attach(ctx)

        active_requests.add(1, {"http.method": method})
        start_time = time.perf_counter()

        status_code = "500"
        span_name = f"{method} {route}"

        with tracer.start_as_current_span(
            span_name,
            kind=trace.SpanKind.SERVER,
        ) as span:
            span.set_attribute(SpanAttributes.HTTP_METHOD, method)
            span.set_attribute(SpanAttributes.HTTP_TARGET, route)
            span.set_attribute(SpanAttributes.HTTP_SCHEME, environ.get("wsgi.url_scheme", "http"))

            # Record a hashed session ID for correlation without leaking the token.
            cookie_str = environ.get("HTTP_COOKIE", "")
            for part in cookie_str.split(";"):
                part = part.strip()
                if part.startswith("session="):
                    raw = part[8:].encode()
                    hashed = hashlib.sha256(raw).hexdigest()[:16]
                    span.set_attribute("enduser.session_id", hashed)
                    break

            def _start_response_wrapper(status: str, headers, exc_info=None):
                nonlocal status_code
                status_code = status.split(" ", 1)[0]
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, int(status_code))
                if status_code.startswith("5"):
                    span.set_status(StatusCode.ERROR, status)
                else:
                    span.set_status(StatusCode.OK)
                return start_response(status, headers, exc_info)

            try:
                result = wsgi_app(environ, _start_response_wrapper)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                status_code = "500"
                raise
            finally:
                elapsed = time.perf_counter() - start_time
                labels = {
                    "http.method": method,
                    "http.route": route,
                    "http.status_code": status_code,
                }
                request_counter.add(1, labels)
                request_duration.record(elapsed, labels)
                active_requests.add(-1, {"http.method": method})
                otel_context.detach(token)

            return result

    return middleware
