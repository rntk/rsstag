"""Activate OTel auto-instrumentation for third-party libraries."""

import logging


def activate_auto_instrumentation() -> None:
    """Instrument pymongo, requests, httpx, and aiohttp-client."""
    _try_instrument("PymongoInstrumentor", _instrument_pymongo)
    _try_instrument("RequestsInstrumentor", _instrument_requests)
    _try_instrument("HTTPXClientInstrumentor", _instrument_httpx)
    _try_instrument("AioHttpClientInstrumentor", _instrument_aiohttp)


def _try_instrument(name: str, fn) -> None:
    try:
        fn()
    except ImportError:
        logging.debug("OTel auto-instrumentation skipped (package not installed): %s", name)
    except Exception as exc:
        logging.warning("OTel auto-instrumentation failed for %s: %s", name, exc)


def _instrument_pymongo() -> None:
    from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
    PymongoInstrumentor().instrument()


def _instrument_requests() -> None:
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    RequestsInstrumentor().instrument()


def _instrument_httpx() -> None:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    HTTPXClientInstrumentor().instrument()


def _instrument_aiohttp() -> None:
    from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
    AioHttpClientInstrumentor().instrument()
