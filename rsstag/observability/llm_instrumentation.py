"""OTel instrumentation for LLMRouter: spans and metrics per LLM call."""

import logging
import time
from typing import Any, Optional


def instrument_llm_router(router: Any) -> None:
    """Monkey-patch LLMRouter.call() and call_citation() to emit spans and metrics."""
    if getattr(router, "_otel_instrumented", False):
        return
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.trace import StatusCode

        meter = metrics.get_meter("rsstag.llm")
        tracer = trace.get_tracer("rsstag.llm")

        calls_counter = meter.create_counter(
            "rsstag.llm.calls",
            description="Total LLM calls",
        )
        duration_histogram = meter.create_histogram(
            "rsstag.llm.call.duration",
            unit="s",
            description="LLM call duration in seconds",
        )
        errors_counter = meter.create_counter(
            "rsstag.llm.errors",
            description="LLM call errors",
        )
    except Exception as exc:
        logging.warning("OTel LLM instrumentation init failed: %s", exc)
        return

    _orig_call = router.call
    _orig_call_citation = router.call_citation

    def _get_provider_model(settings: Optional[dict], provider_key: str, default: str):
        # NOTE: This intentionally calls private LLMRouter methods to read routing
        # decisions for span attributes without re-running the full call logic.
        # If LLMRouter internals change, this silently falls back to "unknown".
        try:
            provider = router._select_provider(settings, provider_key, default)
            model = router._select_model(settings, provider_key, provider)
            handler = router._get_handler(provider, model)
            actual_model = model or getattr(handler, "model", "unknown")
            return provider, str(actual_model)
        except Exception:
            return "unknown", "unknown"

    def _call(settings, user_msgs, provider_key="realtime_llm", default="llamacpp", **kwargs):
        provider, model = _get_provider_model(settings, provider_key, default)
        labels = {"llm.provider": provider, "llm.model": model}
        start = time.perf_counter()
        with tracer.start_as_current_span("llm.call") as span:
            span.set_attribute("llm.provider", provider)
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.provider_key", provider_key)
            try:
                result = _orig_call(settings, user_msgs, provider_key=provider_key, default=default, **kwargs)
                calls_counter.add(1, labels)
                duration_histogram.record(time.perf_counter() - start, labels)
                span.set_status(StatusCode.OK)
                return result
            except Exception as exc:
                errors_counter.add(1, {"llm.provider": provider})
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise

    def _call_citation(settings, user_prompt, docs, provider_key="realtime_llm", default="llamacpp"):
        provider, model = _get_provider_model(settings, provider_key, default)
        labels = {"llm.provider": provider, "llm.model": model}
        start = time.perf_counter()
        with tracer.start_as_current_span("llm.call_citation") as span:
            span.set_attribute("llm.provider", provider)
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.provider_key", provider_key)
            try:
                result = _orig_call_citation(settings, user_prompt, docs, provider_key=provider_key, default=default)
                calls_counter.add(1, labels)
                duration_histogram.record(time.perf_counter() - start, labels)
                span.set_status(StatusCode.OK)
                return result
            except Exception as exc:
                errors_counter.add(1, {"llm.provider": provider})
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise

    router.call = _call
    router.call_citation = _call_citation
    router._otel_instrumented = True
