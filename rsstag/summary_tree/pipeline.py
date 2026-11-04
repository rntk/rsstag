"""Build a bottom-up, citation-linked summary hierarchy over post evidence."""

import logging
import time
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from rsstag.summary_tree.generation import SummaryGenerationError, SummaryGenerator
from rsstag.summary_tree.model import build_hierarchy
from rsstag.summary_tree.results import input_fingerprint, restore, snapshot
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
        posts: List[SourcePost] = load_posts(self._db, self._owner, filters, doc.get("options") or {})
        if not posts:
            raise SummaryTreeError("No posts match these filters")
        root, nodes, evidence = build_hierarchy(posts, focus)
        fingerprint: str = input_fingerprint(focus, nodes, evidence)
        restore(nodes, doc.get("result") or {}, fingerprint)
        self._stage("summaries", len(nodes))

        def save() -> None:
            result: Dict[str, Any] = snapshot(root, nodes, evidence, posts, self._llm, fingerprint)
            if not self._store.save_partial(self._tree_id, self._owner, self._run_id, result):
                raise SummaryTreeSuperseded()
            if not self._store.set_progress(self._tree_id, self._owner, self._run_id,
                                            result["metrics"]["completed_nodes"]):
                raise SummaryTreeSuperseded()

        save()
        SummaryGenerator(self._llm, focus, nodes, evidence, save).run()
        result: Dict[str, Any] = snapshot(root, nodes, evidence, posts, self._llm, fingerprint)
        if not nodes[root].segments and result["metrics"]["summarized"]:
            raise SummaryTreeError("Could not produce a supported overview. Please retry.")
        if not nodes[root].segments:
            raise SummaryTreeError(f"None of the {len(posts)} posts says anything about “{focus}”")
        return result

    def _stage(self, stage: str, total: int = 0) -> None:
        _log.info("Summary tree %s (%s): stage %s", self._tree_id, self._owner, stage)
        if not self._store.set_stage(self._tree_id, self._owner, self._run_id, stage, total):
            raise SummaryTreeSuperseded()

