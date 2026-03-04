"""OTel SDK setup: TracerProvider, MeterProvider, LoggerProvider with OTLP export."""

import logging
import os

_initialized = False


def reset_for_child_process() -> None:
    """Reset the initialization flag so a forked child process can re-initialize
    OTel with its own service name and fresh providers.

    Call this at the very start of the child process entry-point, before
    calling init_observability().
    """
    global _initialized
    _initialized = False


def init_observability(service_name: str, auto_instrument: bool = True) -> None:
    """Initialize OpenTelemetry SDK for the given service.

    Reads OTEL_EXPORTER_OTLP_ENDPOINT from the environment. If unset,
    providers are configured with no exporters (effectively no-op).
    Safe to call multiple times; only the first call takes effect.

    Set auto_instrument=False in forked child processes to avoid
    double-patching libraries that were already instrumented by the parent.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    try:
        _setup(service_name, auto_instrument=auto_instrument)
    except Exception as exc:
        logging.warning("OTel init failed, observability disabled: %s", exc)


def _setup(service_name: str, auto_instrument: bool = True) -> None:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    # Logs SDK
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    # OTel logging bridge
    from opentelemetry.instrumentation.logging import LoggingInstrumentor

    resource = Resource.create({SERVICE_NAME: service_name})
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()

    # --- Traces ---
    tracer_provider = TracerProvider(resource=resource)
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            tracer_provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
            )
        except ImportError:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
                tracer_provider.add_span_processor(
                    BatchSpanProcessor(OTLPSpanExporter())
                )
            except ImportError:
                logging.warning("No OTLP trace exporter available; traces not exported")
    trace.set_tracer_provider(tracer_provider)

    # --- Metrics ---
    metric_readers = []
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )
            metric_readers.append(
                PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
            )
        except ImportError:
            try:
                from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                    OTLPMetricExporter,
                )
                metric_readers.append(
                    PeriodicExportingMetricReader(OTLPMetricExporter())
                )
            except ImportError:
                logging.warning("No OTLP metric exporter available; metrics not exported")
    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)

    # --- Logs ---
    logger_provider = LoggerProvider(resource=resource)
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
                OTLPLogExporter,
            )
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint))
            )
        except ImportError:
            try:
                from opentelemetry.exporter.otlp.proto.http._log_exporter import (
                    OTLPLogExporter,
                )
                logger_provider.add_log_record_processor(
                    BatchLogRecordProcessor(OTLPLogExporter())
                )
            except ImportError:
                logging.warning("No OTLP log exporter available; logs not exported")
    set_logger_provider(logger_provider)

    # Bridge existing Python logging calls → OTel log records
    try:
        LoggingInstrumentor().instrument(set_logging_format=False)
    except Exception as exc:
        logging.warning("OTel logging bridge failed: %s", exc)

    # Activate library auto-instrumentation (skip in forked children to avoid
    # double-patching libraries that were already instrumented by the parent)
    if auto_instrument:
        from rsstag.observability.auto_instrument import activate_auto_instrumentation
        activate_auto_instrumentation()

    logging.info("OTel observability initialised for service '%s'", service_name)
