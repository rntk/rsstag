"""Assign post digests to proposed sub-topics with typed questions.

Per post: a Choice over the sub-topics and a companion Noul asking whether any
fits. ``fits < NO`` sends the post to "Other"; otherwise the top choice wins.
"""

from typing import Dict, List, Optional, Sequence

from rsstag.summary_tree import questions as q
from rsstag.summary_tree.judge import Answers, Request, SummaryJudge, choice, noul

ASSIGN_POSTS: int = 20  # posts per request (two questions each)


def assignment_requests(focus: str, path: str, topics: Dict[str, str],
                        digests: Sequence[str]) -> List[Request]:
    state: Dict[str, object] = {"focus": focus, "path": path, "topics": dict(topics)}
    requests: List[Request] = []
    for start in range(0, len(digests), ASSIGN_POSTS):
        questions: Dict[str, q.Question] = {}
        for index, digest in enumerate(digests[start:start + ASSIGN_POSTS]):
            questions[f"fits_{index}"] = q.topic_fits(digest)
            questions[f"topic_{index}"] = q.topic_choice(digest, path, topics)
        requests.append((state, questions))
    return requests


def _decide(answers: Answers, index: int) -> Optional[str]:
    fits: Optional[float] = noul(answers, f"fits_{index}")
    if fits is not None and fits < q.NO:
        return None
    return choice(answers, f"topic_{index}")


def assign_topics(judge: SummaryJudge, focus: str, path: str, topics: Dict[str, str],
                  digests: Sequence[str]) -> Optional[List[Optional[str]]]:
    """Topic title per digest (``None`` = fits none), or ``None`` when the judge failed."""
    answers: List[Optional[Answers]] = judge.ask_many(assignment_requests(focus, path, topics, digests))
    if any(item is None for item in answers):
        return None
    titles: List[Optional[str]] = []
    for batch, item in enumerate(answers):
        size: int = min(ASSIGN_POSTS, len(digests) - batch * ASSIGN_POSTS)
        titles.extend(_decide(item or {}, index) for index in range(size))
    return titles
