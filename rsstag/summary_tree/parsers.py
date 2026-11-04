"""Decode JSON objects in model responses, including fenced answers."""

import json
import re
from typing import Any, Dict, Optional

_FENCE_RE: re.Pattern = re.compile(r"```(?:json)?", re.IGNORECASE)


def extract_object(raw: str) -> Optional[Dict[str, Any]]:
    """First JSON object found in an answer (code fences and chatter tolerated)."""
    text: str = _FENCE_RE.sub("", str(raw or ""))
    decoder: json.JSONDecoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None
