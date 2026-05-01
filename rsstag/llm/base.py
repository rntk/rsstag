"""Provider-neutral types for tool calling support."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    """Provider-neutral function/tool schema."""

    name: str
    description: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    strict: bool | None = None


@dataclass(frozen=True)
class ToolCall:
    """Provider-neutral tool invocation emitted by an LLM."""

    name: str
    arguments: Mapping[str, Any]
    id: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Provider-neutral response that may include text content and/or tool calls."""

    content: str | None = None
    tool_calls: Sequence[ToolCall] = field(default_factory=tuple)
    reasoning: str | None = None
    raw: Any | None = None



def parse_arguments(arguments: Any) -> Mapping[str, Any]:
    """Parse tool-call arguments into a mapping."""

    if arguments is None:
        return {}
    if isinstance(arguments, str):
        decoded = json.loads(arguments or "{}")
        if not isinstance(decoded, dict):
            raise ValueError("Tool-call arguments must decode to a JSON object.")
        return decoded
    if isinstance(arguments, Mapping):
        return arguments
    raise ValueError("Tool-call arguments must be a JSON object string or mapping.")
