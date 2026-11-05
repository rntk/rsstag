"""HTTP clients for hosted Jev and Jev-compatible llama.cpp servers."""

import logging
import math
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import requests

from rsstag.decisions.models import Answer, DecisionRequest, DecisionResponse, Question

logger: logging.Logger = logging.getLogger(__name__)


class DecisionsError(RuntimeError):
    """A provider failed to return a valid set of answers."""


class DecisionsClient:
    """Use typed questions with a caller-side ``max_context_tokens`` batch budget.

    Zero means no configured limit. Calls preserve the supplied state and questions;
    callers use the budget to split input with their model's tokenizer.
    """

    def __init__(
        self,
        host: str,
        model: str,
        token: str = "",
        timeout: float = 300.0,
        max_context_tokens: int = 0,
    ) -> None:
        parsed: Any = urlsplit(host)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Decisions host must be an HTTP or HTTPS URL")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError(
                "Decisions host must not contain credentials, query or fragment"
            )
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Decisions timeout must be finite and positive")
        if not model.strip():
            raise ValueError("Decisions model must not be empty")
        if type(max_context_tokens) is not int or max_context_tokens < 0:
            raise ValueError("Decisions max_context_tokens must be a non-negative integer")
        self.host: str = host.rstrip("/")
        self.model: str = model
        self._token: str = token
        self._timeout: float = timeout
        # Caller-side token budget for batching; zero means no configured limit.
        self.max_context_tokens: int = max_context_tokens

    def call(
        self,
        state: Any,
        questions: Mapping[str, Question | dict[str, Any]],
        *,
        assets: dict[str, dict[str, Any]] | None = None,
        long_context: bool = False,
    ) -> DecisionResponse:
        """Bundle questions sharing state into one request, preserving probabilities."""
        request: DecisionRequest = DecisionRequest(
            model=self.model, state=state, questions=dict(questions), assets=assets
        )
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if assets or any(q.type == "box" for q in request.questions.values()):
            headers["TypeSafe-Danger-Zone-Images"] = "true"
        if long_context:
            headers["TypeSafe-Danger-Zone-Long-Context"] = "true"
        result: DecisionResponse = self._post(request, headers)
        self._validate_answers(request, result)
        return result

    def _post(
        self, request: DecisionRequest, headers: dict[str, str]
    ) -> DecisionResponse:
        endpoint: str = (
            f"{self.host}/systemone"
            if self.host.endswith("/v1")
            else f"{self.host}/v1/systemone"
        )
        try:
            with requests.post(
                endpoint,
                json=request.model_dump(exclude_none=True),
                headers=headers,
                timeout=self._timeout,
                allow_redirects=False,
            ) as response:
                if not 200 <= response.status_code < 300:
                    logger.warning(
                        "Decisions API returned HTTP %d", response.status_code
                    )
                    raise DecisionsError(
                        f"Decisions API returned HTTP {response.status_code}"
                    )
                return DecisionResponse.model_validate(response.json())
        except ValueError as exc:
            logger.warning("Decisions API returned an invalid response")
            raise DecisionsError("Decisions API returned an invalid response") from exc
        except requests.RequestException as exc:
            logger.warning("Decisions API transport failed (%s)", type(exc).__name__)
            raise DecisionsError("Could not reach the decisions API") from exc

    @staticmethod
    def _validate_answers(request: DecisionRequest, result: DecisionResponse) -> None:
        if request.questions.keys() != result.answers.keys():
            raise DecisionsError("Decisions API returned mismatched question names")
        for name, question in request.questions.items():
            answer: Answer = result.answers[name]
            if question.type != answer.type:
                raise DecisionsError("Decisions API returned a mismatched answer type")
            if (
                question.type == "choice"
                and answer.type == "choice"
                and (
                    answer.choice not in question.criteria
                    or answer.probabilities.keys() != question.criteria.keys()
                )
            ):
                raise DecisionsError("Decisions API returned unknown choices")
            if question.type == "score" and answer.type == "score":
                levels: set[str] = {str(i) for i in range(len(question.criteria))}
                if (
                    answer.probabilities.keys() != levels
                    or answer.legend.keys() != levels
                    or not 0 <= answer.score <= len(levels) - 1
                ):
                    raise DecisionsError("Decisions API returned invalid score levels")


class Jev(DecisionsClient):
    def __init__(
        self,
        token: str,
        model: str = "jev-latest",
        host: str = "https://api.typesafe.ai",
        timeout: float = 300.0,
        max_context_tokens: int = 0,
    ) -> None:
        if not token.strip():
            raise ValueError("Jev requires an API token")
        super().__init__(host, model, token, timeout, max_context_tokens)


class LLamaCPPDecisions(DecisionsClient):
    def __init__(
        self,
        host: str,
        model: str = "default",
        token: str = "",
        timeout: float = 300.0,
        max_context_tokens: int = 0,
    ) -> None:
        super().__init__(host, model, token, timeout, max_context_tokens)


def create_decisions_client(
    config: Mapping[str, Any],
    provider: str | None = None,
    *,
    user_settings: Mapping[str, Any] | None = None,
    provider_key: str = "realtime_decisions",
) -> DecisionsClient:
    """Resolve the realtime or worker preference, unless provider is explicit."""
    if provider_key not in ("realtime_decisions", "worker_decisions"):
        raise ValueError(f"Unknown decisions provider setting: {provider_key}")
    settings: Mapping[str, Any] = config.get("decisions", {})
    preferences: Mapping[str, Any] = user_settings or {}
    name: str = (
        provider
        or preferences.get(provider_key)
        or settings.get("provider", "llamacpp")
    )
    section: str = {"jev": "jev", "llamacpp": "llamacpp_decisions"}.get(name, "")
    if not section:
        raise ValueError(f"Unknown decisions provider: {name}")
    options: dict[str, Any] = dict(config.get(section, {}))
    options["timeout"] = float(settings.get("timeout", 300.0))
    raw_limit: Any = options.get("max_context_tokens", settings.get("max_context_tokens", 0))
    if isinstance(raw_limit, str):
        try:
            raw_limit = int(raw_limit)
        except ValueError as exc:
            raise ValueError(
                "Decisions max_context_tokens must be a non-negative integer"
            ) from exc
    options["max_context_tokens"] = raw_limit
    if name == "jev":
        return Jev(**options)
    return LLamaCPPDecisions(**options)
