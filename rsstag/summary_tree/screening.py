"""Relevance gate and passage selection before post summaries.

Truth table per post (``about`` = whole-post Noul, ``best`` = best passage Noul):

  about >= YES or best >= YES  -> relevant: summarize only the title and passages >= NO
  about <  NO  and best <  NO  -> irrelevant: skip, no LLM call
  otherwise / any failure      -> uncertain: summarize every passage (LLM decides)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from rsstag.summary_tree import questions as q
from rsstag.summary_tree.judge import Answers, Request, SummaryJudge, noul
from rsstag.summary_tree.sources import SourcePost

RELEVANT: str = "relevant"
IRRELEVANT: str = "irrelevant"
UNCERTAIN: str = "uncertain"

SCREEN_CHARS: int = 6000
SCREEN_ROWS: int = 40


@dataclass
class PostScreen:
    verdict: str
    rows: List[int] = field(default_factory=list)


def _row_groups(passages: Sequence[str]) -> List[List[int]]:
    groups: List[List[int]] = []
    size: int = 0
    for row, passage in enumerate(passages, 1):
        if not groups or size + len(passage) > SCREEN_CHARS or len(groups[-1]) >= SCREEN_ROWS:
            groups.append([])
            size = 0
        groups[-1].append(row)
        size += len(passage) + 1
    return groups


def screen_requests(focus: str, post: SourcePost, passages: Sequence[str]) -> List[Request]:
    requests: List[Request] = []
    for rows in _row_groups(passages):
        keys: Dict[str, int] = q.passage_keys(rows)
        state: Dict[str, object] = {"focus": focus, "post": {
            "title": post.title, "passages": {key: passages[row - 1] for key, row in keys.items()}}}
        questions: Dict[str, q.NoulQuestion] = {"about": q.post_about_focus(focus)}
        questions.update({key: q.passage_about_focus(focus, key) for key in keys})
        requests.append((state, dict(questions)))
    return requests


def decide(answers: Sequence[Optional[Answers]], passages: Sequence[str]) -> PostScreen:
    all_rows: List[int] = list(range(1, len(passages) + 1))
    if not answers or any(a is None for a in answers):
        return PostScreen(UNCERTAIN, all_rows)
    about: List[float] = [p for p in (noul(a, "about") for a in answers) if p is not None]
    rows: Dict[int, float] = {}
    for item in answers:
        for name in item or {}:
            if name.startswith("p") and name[1:].isdigit():
                rows[int(name[1:])] = noul(item, name) or 0.0
    best: float = max(rows.values(), default=0.0)
    top: float = max(about, default=0.0)
    if top >= q.YES or best >= q.YES:
        return PostScreen(RELEVANT, sorted({1} | {row for row, p in rows.items() if p >= q.NO}))
    if top < q.NO and best < q.NO:
        return PostScreen(IRRELEVANT, [])
    return PostScreen(UNCERTAIN, all_rows)


def screen_posts(judge: SummaryJudge, focus: str, posts: Sequence[SourcePost],
                 evidence: Dict[str, List[str]]) -> Dict[str, PostScreen]:
    """One verdict per post; requests of all posts run in parallel."""
    plan: List[Tuple[str, int]] = []
    requests: List[Request] = []
    for post in posts:
        own: List[Request] = screen_requests(focus, post, evidence[post.pid])
        plan.append((post.pid, len(own)))
        requests.extend(own)
    answers: List[Optional[Answers]] = judge.ask_many(requests)
    screens: Dict[str, PostScreen] = {}
    start: int = 0
    for pid, count in plan:
        screens[pid] = decide(answers[start:start + count], evidence[pid])
        start += count
    return screens
