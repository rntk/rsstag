"""Offline stage ablation: python3 -m tests.anthology_evaluation.

Hand-authored overlapping subjects and synthetic clear subjects use a deterministic
truth oracle, not a live model. This measures routing mechanics, not LLM accuracy.
Initial accepted/rejected groups are controlled, so this is not an end-to-end
comparison of old and new candidate discovery or label sampling.
"""

import copy
import json
import re
from collections import Counter
from typing import Any, Dict, List, Tuple

from rsstag.anthology.assignment import assign_leftovers
from rsstag.anthology.candidates import Cluster, Vectors, make_cluster, vectorize
from rsstag.anthology.judge import Judge
from rsstag.anthology.recovery import recover_unsorted
from rsstag.anthology.repair import repair_rejected
from rsstag.anthology.result import RunCounters
from rsstag.anthology.units import Snippet
from tests.anthology_fakes import FakeDB, FakeRouter, synthetic_snippets


class TruthRouter(FakeRouter):
    """Use hidden topic markers only to evaluate the judgment contract."""

    @staticmethod
    def topics(text: str) -> set[str]:
        return set(re.findall(r"truth_(\w+)", text))

    def call(self, settings: object, user_msgs: List[str], **kwargs: Any) -> str:
        prompt: str = user_msgs[0]
        if prompt.startswith("TASK: ASSIGN"):
            self.prompts.append(prompt)
            payload: Dict[str, Any] = json.loads(prompt.split("\n")[-1])
            return json.dumps([
                {"id": item["id"], "same": self.topics(item["snippet"]) == self.topics(" ".join(item["representatives"]))}
                for item in payload["items"]
            ])
        if prompt.startswith("TASK: LABEL"):
            self.prompts.append(prompt)
            blocks: List[str] = re.split(r"(?m)^Cluster \d+\s*$", prompt)[1:]
            return "\n".join(json.dumps({"id": n, "score": 4 if len(self.topics(block)) == 1 else 2,
                "label": " ".join(sorted(self.topics(block))) or "mixed", "kind": "event"})
                for n, block in enumerate(blocks, 1))
        if prompt.startswith("TASK: INTRUDER"):
            self.prompts.append(prompt)
            blocks = re.split(r"(?m)^Set \d+\s*$", prompt)[1:]
            answers: List[str] = []
            for n, block in enumerate(blocks, 1):
                items: List[str] = re.findall(r"(?m)^\d+\. (.*)$", block)
                counts: Counter[str] = Counter(topic for item in items for topic in self.topics(item))
                position: int = next((i for i, item in enumerate(items, 1)
                    if any(counts[topic] == 1 for topic in self.topics(item))), 1)
                answers.append(f"{n}: {position}")
            return "\n".join(answers)
        return super().call(settings, user_msgs, **kwargs)


def fixtures() -> List[Tuple[str, List[Snippet], List[str]]]:
    snippets: List[Snippet]
    truth: List[str]
    snippets, truth = synthetic_snippets(per_topic=8)
    clear: Tuple[str, List[Snippet], List[str]] = ("clear", snippets, truth)
    subjects: Dict[str, List[str]] = {
        "postgres": ["PostgreSQL query planner index database performance regression", "PostgreSQL query planner index database performance fix", "PostgreSQL query planner index database benchmark", "PostgreSQL query planner index database upgrade"],
        "sqlite": ["SQLite query planner index database performance regression", "SQLite query planner index database performance fix", "SQLite query planner index database benchmark", "SQLite query planner index database upgrade"],
        "solar": ["solar panel battery home electricity installation", "solar panel battery home electricity savings", "solar panel battery home electricity output", "solar panel battery home electricity maintenance"],
    }
    overlapping: List[Snippet] = []
    labels: List[str] = []
    for topic, texts in subjects.items():
        for text in texts:
            row: int = len(overlapping)
            overlapping.append(Snippet(id=f"h{row}", post_id=str(row), sentence_indices=[0],
                topic_path="Technology > Updates", title="Update", feed_id="feed", date=float(row), text=text))
            labels.append(topic)
    return [clear, ("overlapping", overlapping, labels)]


def evaluate(snippets: List[Snippet], truth: List[str], enabled: bool) -> Dict[str, Any]:
    snippets = copy.deepcopy(snippets)
    # Fit without oracle markers: truth is available only to mocked judgments.
    vectors: Vectors = vectorize([snippet.vector_text for snippet in snippets], min_df=1)
    for snippet, topic in zip(snippets, truth):
        snippet.text = re.sub(r" truth_\w+", "", snippet.text) + f" truth_{topic}"
    groups: Dict[str, List[int]] = {}
    for row, topic in enumerate(truth):
        groups.setdefault(topic, []).append(row)
    rows: List[List[int]] = list(groups.values())
    accepted: List[Cluster] = [make_cluster("c0", rows[0][:2], vectors)]
    accepted[0].score = 4
    accepted[0].label = truth[0]
    # One mixed reject plus isolated leftovers stress repair and assignment.
    rejected: List[Cluster] = [make_cluster("c1", rows[1] + rows[2], vectors)]
    counters: RunCounters = RunCounters()
    judge: Judge = Judge(FakeDB(), TruthRouter(merge_answer="different"), "owner")
    if enabled:
        accepted += repair_rejected(rejected, vectors, snippets, judge, "technology", counters)
        accepted = assign_leftovers(accepted, vectors, snippets, judge, "technology", counters)
    clusters: List[Cluster] = recover_unsorted(accepted, vectors, snippets, judge, "technology", counters)
    members: List[int] = [row for cluster in clusters for row in cluster.members]
    assert len(members) == len(set(members)), "duplicate snippet assignment"
    assert all(0 <= row < len(snippets) for row in members)
    correct: int = sum(max(Counter(truth[row] for row in cluster.members).values()) for cluster in clusters)
    fragments: Dict[str, int] = {topic: sum(any(truth[row] == topic for row in c.members) for c in clusters) for topic in groups}
    return {"coverage": round(len(set(members)) / len(snippets), 3), "purity": round(correct / len(members), 3),
        "clusters": len(clusters), "fragments_per_subject": fragments, "judge_calls": judge.calls,
        "recovery_input": counters.recovery_snippets_input, "repair_assigned": counters.repair_snippets_assigned,
        "assignment_assigned": counters.assignment_snippets_assigned}


def main() -> None:
    results: Dict[str, Any] = {}
    for name, snippets, truth in fixtures():
        results[name] = {"baseline": evaluate(snippets, truth, False), "repair_and_assignment": evaluate(snippets, truth, True)}
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
