"""Progressive-disclosure summary tree over post evidence.

1. posts: brief, focused, passage-cited summary per post (the grounding layer);
2. topics: recursive split of those digests into distinct sub-topics;
3. summaries: bottom-up, level-specific summaries citing child claims —
   detailed just above the posts, more abstract towards the focus.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from rsstag.summary_tree.generation import SummaryGenerationError, SummaryGenerator
from rsstag.summary_tree.model import TOPIC, Nodes, build_post_nodes
from rsstag.summary_tree.results import snapshot
from rsstag.summary_tree.topics import TopicBuilder, topic_ids
from rsstag.summary_tree.llm import SummaryLLM, SummaryLLMUnavailableError, prepare_cache
from rsstag.summary_tree.sources import SourcePost, load_posts
from rsstag.summary_trees import RssTagSummaryTrees

_log: logging.Logger = logging.getLogger("summary_tree.pipeline")


class SummaryTreeError(RuntimeError):
    """Expected failure with a user-facing message."""


class SummaryTreeSuperseded(RuntimeError):
    """The claimed run was reset, deleted or taken over."""


class SummaryTreePipeline:
    """Build and persist the result of one claimed summary tree."""

    def __init__(
        self, db: Database, llm_router: Any, owner: str, settings: Optional[Dict[str, Any]] = None
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
        self._posts = load_posts(self._db, self._owner, filters, doc.get("options") or {})
        if not self._posts:
            raise SummaryTreeError("No posts match these filters")
        post_nodes, self._nodes, self._evidence = build_post_nodes(self._posts)
        relevant: List[str] = self._summarize_posts(focus, post_nodes)
        self._stage("topics")
        self._root = TopicBuilder(self._llm, focus, self._nodes, self._save).build(relevant)
        targets: List[str] = topic_ids(self._nodes)
        self._stage("summaries", len(targets))
        SummaryGenerator(self._llm, focus, self._nodes, self._evidence, self._save, targets).run()
        if not self._nodes[self._root].segments:
            raise SummaryTreeError("Could not produce a supported overview. Please retry.")
        return self._snapshot()

    def _summarize_posts(self, focus: str, post_nodes: Dict[str, str]) -> List[str]:
        """Brief cited post summaries; returns the post nodes relevant to the focus."""
        self._stage("posts", len(self._nodes))
        self._save()
        SummaryGenerator(self._llm, focus, self._nodes, self._evidence, self._save,
                         list(self._nodes), tolerate_failures=True).run()
        relevant: List[str] = [post_nodes[p.pid] for p in self._posts if self._nodes[post_nodes[p.pid]].segments]
        if relevant:
            return relevant
        if all(self._nodes[node_id].failed for node_id in post_nodes.values()):
            raise SummaryTreeError("Could not summarize any post. Please retry; completed summaries are cached.")
        raise SummaryTreeError(f"None of the {len(self._posts)} posts says anything about “{focus}”")

    def _snapshot(self) -> Dict[str, Any]:
        return snapshot(self._root, self._nodes, self._evidence, self._posts, self._llm)

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

