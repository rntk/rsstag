"""Typed results returned by worker task handlers.

Handlers historically returned ``bool``: ``True`` meant "run the finish path"
and ``False`` meant "failure". That conflated healthy "not done yet" states
(e.g. a remote LLM batch still running) with real failures, so long-running
tasks burned their retry budget and were dead-lettered.

Handlers may now return one of the outcome types below. Legacy ``bool``
handlers keep working through :func:`normalize_outcome`.
"""

from dataclasses import dataclass
from typing import Literal, Optional, Union

RetryCounter = Literal["attempts", "poll_attempts"]

# Delay before a ``Continue`` task becomes claimable again. Small, so the next
# step runs promptly, but non-zero so a worker does not spin on one task.
CONTINUE_DELAY_SECONDS: float = 2.0
GENERIC_FAILURE_MESSAGE: str = "Task handler returned false"


@dataclass(frozen=True)
class Completed:
    """The handler step finished; run the regular finish path."""


@dataclass(frozen=True)
class Continue:
    """More work remains; re-queue soon without consuming an attempt."""

    # Set only after a successful remote poll, never on submission or throttle.
    reset_poll_attempts: bool = False


@dataclass(frozen=True)
class Deferred:
    """Nothing to do until ``next_run_at`` (epoch seconds); no attempt consumed."""

    next_run_at: float
    reset_poll_attempts: bool = False


@dataclass(frozen=True)
class RetryableFailure:
    """A transient failure; retry with backoff, dead-letter at max attempts."""

    error: str
    # Poll recovery must not erase the budget for failed remote executions.
    attempt_field: RetryCounter = "attempts"


@dataclass(frozen=True)
class PermanentFailure:
    """A failure retries cannot fix; dead-letter the task immediately."""

    error: str


TaskOutcome = Union[Completed, Continue, Deferred, RetryableFailure, PermanentFailure]
HandlerResult = Union[bool, TaskOutcome, None]

_OUTCOME_TYPES = (Completed, Continue, Deferred, RetryableFailure, PermanentFailure)
_FAILURE_TYPES = (RetryableFailure, PermanentFailure)


def normalize_outcome(
    result: HandlerResult, failure_message: Optional[str] = None
) -> TaskOutcome:
    """Map a handler result (legacy bool or outcome) onto a ``TaskOutcome``.

    Truthy legacy results become ``Completed``; ``False``/``None`` become a
    ``RetryableFailure`` carrying ``failure_message`` (or a generic message).
    """
    if isinstance(result, _OUTCOME_TYPES):
        return result
    if result:
        return Completed()
    return RetryableFailure(failure_message or GENERIC_FAILURE_MESSAGE)


def is_failure(result: HandlerResult) -> bool:
    """Return True when a raw handler result represents a failure."""
    return result is False or isinstance(result, _FAILURE_TYPES)
