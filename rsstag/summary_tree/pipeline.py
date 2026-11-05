"""Progressive-disclosure summary tree over post evidence.

1. posts: brief, focused, passage-cited summary per post (the grounding layer);
2. topics: recursive split of those digests into distinct sub-topics;
3. summaries: bottom-up, level-specific summaries citing child claims —
   detailed just above the posts, more abstract towards the focus.

With a decisions judge (``[decisions] summary_tree = on``) typed questions take
over the judgments: posts and passages are screened for relevance before any
generation, sub-topic membership is a Choice per post, and concrete claims are
checked against their citations. Any judge failure falls back to the LLM path.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from pymongo.database import Database

from rsstag.summary_tree.generation import SummaryGenerationError, SummaryGenerator
from rsstag.summary_tree.filters import DEFAULT_LIMIT, MAX_LIMIT
from rsstag.summary_tree.judge import SummaryJudge
from rsstag.summary_tree.model import TOPIC, Nodes, build_post_nodes, evidence_rows
from rsstag.summary_tree.screening import IRRELEVANT, PostScreen, screen_posts
from rsstag.summary_tree.results import snapshot
from rsstag.summary_tree.topics import TopicBuilder, topic_ids
from rsstag.summary_tree.llm import SummaryLLM, SummaryLLMUnavailableError, prepare_cache
from rsstag.summary_tree.sources import SourcePost, load_posts
from rsstag.summary_tree.verify import ClaimVerifier
from rsstag.summary_trees import RssTagSummaryTrees

CANDIDATE_FACTOR: int = 3  # with a judge, screen up to this many posts per wanted post
MIN_WAVE: int = 8

_log: logging.Logger = logging.getLogger("summary_tree.pipeline")


class SummaryTreeError(RuntimeError):
    """Expected failure with a user-facing message."""


class SummaryTreeSuperseded(RuntimeError):
    """The claimed run was reset, deleted or taken over."""


class SummaryTreePipeline:
    """Build and persist the result of one claimed summary tree."""

    def __init__(
        self, db: Database, llm_router: Any, owner: str, settings: Optional[Dict[str, Any]] = None,
        judge: Optional[SummaryJudge] = None,
    ) -> None:
        self._db: Database = db
        self._owner: str = owner
        self._store: RssTagSummaryTrees = RssTagSummaryTrees(db)
        self._llm: SummaryLLM = SummaryLLM(db, llm_router, owner, settings)
        self._tree_id: str = ""
        self._run_id: str = ""
        self._stage_name: str = ""
        self._posts: List[SourcePost] = []
        self._nodes: Nodes = {}
        self._evidence: Dict[str, List[str]] = {}
        self._root: Optional[str] = None
        self._judge: Optional[SummaryJudge] = judge
        self._verifier: Optional[ClaimVerifier] = None
        self._screens: Dict[str, PostScreen] = {}

    def run(self, doc: Dict[str, Any]) -> bool:
        self._tree_id, self._run_id = str(doc.get("_id", "")), str(doc.get("run_id") or "")
        started: float = time.time()
        try:
            result: Dict[str, Any] = self._build(doc)
            result["metrics"]["duration_sec"] = round(time.time() - started, 1)
            if not self._store.save_result(self._tree_id, self._owner, self._run_id, result):
                raise SummaryTreeSuperseded()
        except SummaryTreeSuperseded:
            _log.info("Summary tree %s run superseded; stopping", self._tree_id)
            return False
        except (SummaryTreeError, SummaryGenerationError, SummaryLLMUnavailableError) as exc:
            _log.warning("Summary tree %s failed for %s: %s", self._tree_id, self._owner, exc)
            return self._fail(str(exc))
        except Exception as exc:
            _log.exception("Summary tree %s crashed for %s", self._tree_id, self._owner)
            return self._fail(f"Summary tree pipeline error: {exc or exc.__class__.__name__}")
        _log.info("Summary tree %s done for %s: %s", self._tree_id, self._owner, result["metrics"])
        return True

    def _fail(self, message: str) -> bool:
        self._store.fail(self._tree_id, self._owner, self._run_id, message)
        return False

    def _build(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        filters: Dict[str, Any] = doc.get("filters") or {}
        focus: str = str(filters.get("entity") or "").strip()
        if not focus:
            raise SummaryTreeError("Summary tree needs an entity to focus on")
        prepare_cache(self._db)
        self._stage("sources")
        options: Dict[str, Any] = doc.get("options") or {}
        limit: int = int(options.get("limit") or DEFAULT_LIMIT)
        candidates: List[SourcePost] = load_posts(
            self._db, self._owner, filters, {**options, "limit": self._candidate_limit(limit)})
        if not candidates:
            raise SummaryTreeError("No posts match these filters")
        self._posts, self._screens = self._select(focus, candidates, limit)
        keep: Dict[str, List[int]] = {pid: screen.rows for pid, screen in self._screens.items()}
        post_nodes, self._nodes, self._evidence = build_post_nodes(self._posts, keep)
        for pid, screen in self._screens.items():
            if screen.verdict == IRRELEVANT and pid in post_nodes:
                self._nodes[post_nodes[pid]].segments = []
        if self._judge is not None:
            self._verifier = ClaimVerifier(self._judge, focus, self._nodes, self._evidence)
        relevant: List[str] = self._summarize_posts(focus, post_nodes)
        self._stage("topics")
        self._root = TopicBuilder(self._llm, focus, self._nodes, self._save, self._judge).build(relevant)
        targets: List[str] = topic_ids(self._nodes)
        self._stage("summaries", len(targets))
        SummaryGenerator(self._llm, focus, self._nodes, self._evidence, self._save, targets,
                         verifier=self._verifier).run()
        if not self._nodes[self._root].segments:
            raise SummaryTreeError("Could not produce a supported overview. Please retry.")
        return self._snapshot()

    def _summarize_posts(self, focus: str, post_nodes: Dict[str, str]) -> List[str]:
        """Brief cited post summaries; returns the post nodes relevant to the focus."""
        self._stage("posts", len(self._nodes))
        self._save()
        SummaryGenerator(self._llm, focus, self._nodes, self._evidence, self._save,
                         list(self._nodes), tolerate_failures=True, verifier=self._verifier).run()
        relevant: List[str] = [post_nodes[p.pid] for p in self._posts if self._nodes[post_nodes[p.pid]].segments]
        if relevant:
            return relevant
        if all(self._nodes[node_id].failed for node_id in post_nodes.values()):
            raise SummaryTreeError("Could not summarize any post. Please retry; completed summaries are cached.")
        raise SummaryTreeError(f"None of the {len(self._posts)} posts says anything about “{focus}”")

    def _candidate_limit(self, limit: int) -> int:
        if self._judge is None or not self._judge.active:
            return limit
        return max(limit, min(MAX_LIMIT, limit * CANDIDATE_FACTOR))

    def _select(self, focus: str, posts: List[SourcePost],
                limit: int) -> Tuple[List[SourcePost], Dict[str, PostScreen]]:
        """Newest posts until ``limit`` of them are not screened out (in parallel waves)."""
        if self._judge is None or not self._judge.active:
            return posts[:limit], {}
        evidence: Dict[str, List[str]] = {post.pid: evidence_rows(post) for post in posts}
        chosen: List[SourcePost] = []
        screens: Dict[str, PostScreen] = {}
        kept: int = 0
        index: int = 0
        while index < len(posts) and kept < limit:
            wave: List[SourcePost] = posts[index:index + max(MIN_WAVE, limit - kept)]
            index += len(wave)
            screens.update(screen_posts(self._judge, focus, wave, evidence))
            for post in wave:
                if kept >= limit:
                    break
                chosen.append(post)
                kept += screens[post.pid].verdict != IRRELEVANT
            self._heartbeat(len(screens))
        _log.info("Summary tree %s screened %d posts: %d kept of %d chosen", self._tree_id,
                  len(screens), kept, len(chosen))
        return chosen, {post.pid: screens[post.pid] for post in chosen}

    def _heartbeat(self, done: int) -> None:
        if not self._store.set_progress(self._tree_id, self._owner, self._run_id, done):
            raise SummaryTreeSuperseded()

    def _decision_metrics(self) -> Dict[str, Any]:
        if self._judge is None:
            return {}
        verdicts: List[str] = [screen.verdict for screen in self._screens.values()]
        return {
            "decisions_calls": self._judge.calls, "decisions_cached": self._judge.cached,
            "decisions_failures": self._judge.failures, "decisions_active": self._judge.active,
            "screened": len(verdicts), "screened_out": verdicts.count(IRRELEVANT),
            "passages_kept": sum(len(s.rows) for s in self._screens.values()),
            "passages_total": sum(len(self._evidence.get(pid, [])) for pid in self._screens),
            "claims_dropped": self._verifier.dropped if self._verifier else 0,
        }

    def _snapshot(self) -> Dict[str, Any]:
        return snapshot(self._root, self._nodes, self._evidence, self._posts, self._llm,
                        self._decision_metrics())

    def _save(self) -> None:
        result: Dict[str, Any] = self._snapshot()
        if not self._store.save_partial(self._tree_id, self._owner, self._run_id, result):
            raise SummaryTreeSuperseded()
        if not self._store.set_progress(self._tree_id, self._owner, self._run_id, self._progress()):
            raise SummaryTreeSuperseded()

    def _progress(self) -> int:
        if self._stage_name == "posts":
            return sum(node.segments is not None for node in self._nodes.values())
        if self._stage_name == "topics":
            return sum(node.kind == TOPIC for node in self._nodes.values())
        return sum(self._nodes[node_id].segments is not None for node_id in topic_ids(self._nodes))

    def _stage(self, stage: str, total: int = 0) -> None:
        self._stage_name = stage
        _log.info("Summary tree %s (%s): stage %s", self._tree_id, self._owner, stage)
        if not self._store.set_stage(self._tree_id, self._owner, self._run_id, stage, total):
            raise SummaryTreeSuperseded()

