"""Deterministic fakes for anthology pipeline tests (no Mongo, no LLM)."""

import json
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from rsstag.anthology.units import Snippet

TOPIC_WORDS: Dict[str, List[str]] = {
    "space": "rocket launch orbit nasa satellite mission spacex booster".split(),
    "cooking": "recipe pasta tomato sauce garlic oven bake cheese".split(),
    "football": "match goal striker league coach penalty stadium referee".split(),
}


def synthetic_texts(per_topic: int = 12, words: int = 10, seed: int = 1) -> Tuple[List[str], List[str]]:
    """Texts drawn from clearly separate vocabularies, plus their topic names."""
    rng: random.Random = random.Random(seed)
    texts: List[str] = []
    truth: List[str] = []
    for topic, vocab in TOPIC_WORDS.items():
        for _ in range(per_topic):
            texts.append(" ".join(rng.choices(vocab, k=words)))
            truth.append(topic)
    return texts, truth


def synthetic_snippets(per_topic: int = 12) -> Tuple[List[Snippet], List[str]]:
    texts, truth = synthetic_texts(per_topic)
    snippets: List[Snippet] = [
        Snippet(
            id=f"s{i}",
            post_id=str(100 + i),
            sentence_indices=[0, 1],
            topic_path=f"{truth[i].title()} > Details",
            title=f"Post {i}",
            feed_id=f"feed-{truth[i]}",
            date=1_700_000_000.0 + i,
            text=text,
        )
        for i, text in enumerate(texts)
    ]
    return snippets, truth


def _blocks(prompt: str, header: str) -> List[str]:
    parts: List[str] = re.split(rf"(?m)^{header} \d+\s*$", prompt)
    return parts[1:]


def _words(text: str) -> set:
    return set(re.findall(r"[a-z]+", text.lower()))


class FakeRouter:
    """Answers judge prompts deterministically, recording every prompt."""

    def __init__(self, merge_answer: str = "same", label_score: int = 4) -> None:
        self.prompts: List[str] = []
        self.merge_answer: str = merge_answer
        self.label_score: int = label_score

    def call(self, settings: Optional[dict], user_msgs: List[str], **kwargs: Any) -> str:
        prompt: str = user_msgs[0]
        self.prompts.append(prompt)
        if prompt.startswith("TASK: MERGE"):
            count: int = len(_blocks(prompt, "Pair"))
            return "\n".join(f"{n}: {self.merge_answer}" for n in range(1, count + 1))
        if prompt.startswith("TASK: LABEL"):
            return "```json\n" + "\n".join(self._label(n, b) for n, b in enumerate(_blocks(prompt, "Cluster"), 1)) + "\n```"
        if prompt.startswith("TASK: INTRUDER"):
            return "\n".join(f"{n}: {self._intruder(b)}" for n, b in enumerate(_blocks(prompt, "Set"), 1))
        if prompt.startswith("TASK: THEMES"):
            count = len(_blocks(prompt, "Group"))
            return json.dumps([{"id": n, "label": f"Theme {n}"} for n in range(1, count + 1)])
        return ""

    def _label(self, number: int, block: str) -> str:
        match = re.search(r"keywords: ([^\n,]*)", block)
        keyword: str = (match.group(1).strip() if match else "") or "misc"
        return json.dumps({"id": number, "score": self.label_score, "label": f"{keyword} story", "kind": "event"})

    @staticmethod
    def _intruder(block: str) -> int:
        items: List[str] = re.findall(r"(?m)^\d+\. (.*)$", block)
        overlaps: List[int] = [
            sum(len(_words(item) & _words(other)) for j, other in enumerate(items) if j != i)
            for i, item in enumerate(items)
        ]
        return overlaps.index(min(overlaps)) + 1


class FakeCollection:
    """Tiny dict-backed stand-in for the judgment cache collection."""

    def __init__(self) -> None:
        self.docs: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def find_one(self, query: Dict[str, Any], projection: Any = None) -> Optional[Dict[str, Any]]:
        return self.docs.get((query["owner"], query["prompt_hash"]))

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> None:
        self.docs[(query["owner"], query["prompt_hash"])] = dict(update["$set"])

    def create_index(self, *args: Any, **kwargs: Any) -> None:
        return None


class FakeDB:
    def __init__(self) -> None:
        self.collections: Dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())
