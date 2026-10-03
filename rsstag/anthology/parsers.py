"""Robust parsers for short judge answers."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rsstag.anthology.prompts import KINDS

_log: logging.Logger = logging.getLogger("anthology.parsers")

_FENCE_RE: re.Pattern = re.compile(r"```(?:json|jsonl)?", re.IGNORECASE)
_OBJECT_RE: re.Pattern = re.compile(r"\{[^{}]*\}", re.DOTALL)
_PAIR_RE: re.Pattern = re.compile(
    r"(?:pair\s*)?(\d+)\s*[:.)\-=]\s*\**\s*(same|different|yes|no|merge|separate)\b",
    re.IGNORECASE,
)
_INDEX_RE: re.Pattern = re.compile(
    r"(?:set\s*)?(\d+)\s*[:.)\-=]\s*\**\s*(?:snippet\s*|#)?(\d+)", re.IGNORECASE
)
_QUOTES_RE: re.Pattern = re.compile(r"[\"`«»“”]")
_POSITIVE: frozenset = frozenset({"same", "yes", "merge"})


@dataclass
class LabelJudgment:
    score: int
    label: str
    kind: str


def clip_words(text: str, max_words: int) -> str:
    """Single-line label of at most max_words words, without wrapping quotes."""
    cleaned: str = _QUOTES_RE.sub(" ", str(text))
    words: List[str] = cleaned.split()
    return " ".join(words[:max_words]).strip(" .,;:'")


def parse_json_objects(raw: str) -> List[Dict[str, Any]]:
    """Extract JSON objects from an answer (array, JSON lines, fences, noise)."""
    text: str = _FENCE_RE.sub("", raw or "").strip()
    whole: Any = _try_json(text)
    if isinstance(whole, list):
        return [item for item in whole if isinstance(item, dict)]
    if isinstance(whole, dict):
        return [whole]
    objects: List[Dict[str, Any]] = []
    for chunk in _OBJECT_RE.findall(text):
        parsed: Any = _try_json(chunk)
        if parsed is None:
            parsed = _try_json(chunk.replace("'", '"'))
        if isinstance(parsed, dict):
            objects.append(parsed)
    return objects


def _try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip().lstrip("#"))
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _object_index(obj: Dict[str, Any], count: int) -> Optional[int]:
    number: Optional[int] = _as_int(obj.get("id", obj.get("cluster", obj.get("group"))))
    return number if number is not None and 1 <= number <= count else None


def parse_pair_answers(raw: str, count: int) -> Dict[int, bool]:
    """'<n>: same|different' lines -> {n: is_same}; first answer per pair wins."""
    answers: Dict[int, bool] = {}
    for number, verdict in _PAIR_RE.findall(raw or ""):
        index: int = int(number)
        if 1 <= index <= count and index not in answers:
            answers[index] = verdict.lower() in _POSITIVE
    return answers


def parse_labels(raw: str, count: int) -> Dict[int, LabelJudgment]:
    """JSON objects -> {cluster number: judgment}; invalid fields get defaults."""
    judgments: Dict[int, LabelJudgment] = {}
    for obj in parse_json_objects(raw):
        index: Optional[int] = _object_index(obj, count)
        if index is None or index in judgments:
            continue
        score: Optional[int] = _as_int(obj.get("score"))
        kind: str = str(obj.get("kind") or "other").strip().lower()
        judgments[index] = LabelJudgment(
            score=min(5, max(1, score)) if score is not None else 3,
            label=clip_words(obj.get("label") or "", 5),
            kind=kind if kind in KINDS else "other",
        )
    return judgments


def parse_intruders(raw: str, count: int, options: int = 5) -> Dict[int, int]:
    """'<set>: <index>' lines (or JSON objects) -> {set number: intruder index}."""
    answers: Dict[int, int] = {}
    for obj in parse_json_objects(raw):
        index: Optional[int] = _object_index(obj, count)
        choice: Optional[int] = _as_int(obj.get("intruder", obj.get("answer")))
        if index is not None and choice is not None and 1 <= choice <= options:
            answers.setdefault(index, choice)
    if answers:
        return answers
    for number, choice_text in _INDEX_RE.findall(raw or ""):
        index_num, choice_num = int(number), int(choice_text)
        if 1 <= index_num <= count and 1 <= choice_num <= options:
            answers.setdefault(index_num, choice_num)
    return answers


def parse_theme_labels(raw: str, count: int) -> Dict[int, str]:
    """JSON objects -> {group number: label ≤4 words}."""
    labels: Dict[int, str] = {}
    for obj in parse_json_objects(raw):
        index: Optional[int] = _object_index(obj, count)
        label: str = clip_words(obj.get("label") or "", 4)
        if index is not None and label and index not in labels:
            labels[index] = label
    return labels
