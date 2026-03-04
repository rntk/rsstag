"""OpenTelemetry observability package for RSSTag."""

from rsstag.observability.setup import init_observability, reset_for_child_process

__all__ = ["init_observability", "reset_for_child_process"]
