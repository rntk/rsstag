"""Anthology pipeline orchestration: units → candidates → judge stages → result."""

import logging
import time
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from rsstag.anthologies import STATUS_FAILED, RssTagAnthologies
from rsstag.anthology import stages
from rsstag.anthology.candidates import Cluster, Vectors, build_candidates, vectorize
from rsstag.anthology.judge import Judge, JudgeUnavailableError, prepare_judgments
from rsstag.anthology.result import RunCounters, build_result
from rsstag.anthology.units import UnitsResult, load_units

_log: logging.Logger = logging.getLogger("anthology.pipeline")


class AnthologyPipelineError(RuntimeError):
    """Expected pipeline failure with a user-facing message."""


class AnthologyPipeline:
    """Build one anthology result and persist it."""

    def __init__(
        self,
        db: Database,
        llm_router: Any,
        owner: str,
        settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._db: Database = db
        self._owner: str = owner
        self._store: RssTagAnthologies = RssTagAnthologies(db)
        self._judge: Judge = Judge(db, llm_router, owner, settings)

    def run(self, anthology_id: str) -> bool:
        """Run all stages; on failure mark the anthology failed and return False."""
        started: float = time.time()
        try:
            doc: Dict[str, Any] = self._load_doc(anthology_id)
            result: Dict[str, Any] = self._build(anthology_id, doc, started)
        except (AnthologyPipelineError, JudgeUnavailableError) as exc:
            _log.warning("Anthology %s failed for %s: %s", anthology_id, self._owner, exc)
            return self._fail(anthology_id, str(exc))
        except Exception as exc:
            _log.exception("Anthology %s crashed for %s", anthology_id, self._owner)
            return self._fail(anthology_id, f"Anthology pipeline error: {exc or exc.__class__.__name__}")
        if not self._store.save_result(anthology_id, result):
            return self._fail(anthology_id, "Can't save anthology result")
        _log.info("Anthology %s done for %s: %s", anthology_id, self._owner, result["metrics"])
        return True

    def _fail(self, anthology_id: str, message: str) -> bool:
        self._store.update_status(anthology_id, STATUS_FAILED, error=message[:500])
        return False

    def _load_doc(self, anthology_id: str) -> Dict[str, Any]:
        doc: Optional[Dict[str, Any]] = self._store.get_by_id(self._owner, anthology_id)
        if not doc:
            raise AnthologyPipelineError(f"Anthology {anthology_id} not found")
        if not str(doc.get("seed_value") or "").strip():
            raise AnthologyPipelineError("Anthology has an empty seed")
        return doc

    def _build(self, anthology_id: str, doc: Dict[str, Any], started: float) -> Dict[str, Any]:
        seed: str = str(doc["seed_value"]).strip()
        counters: RunCounters = RunCounters()
        self._stage(anthology_id, "units")
        units: UnitsResult = load_units(self._db, self._owner, seed, doc.get("scope"))
        counters.ungrouped_posts = units.ungrouped_posts
        if not units.snippets:
            raise AnthologyPipelineError(self._no_snippets_message(units))
        snippets = units.snippets

        self._stage(anthology_id, "candidates")
        vectors: Vectors = vectorize([s.vector_text for s in snippets])
        clusters, _unsorted = build_candidates(vectors)
        counters.clusters_candidate = len(clusters)
        prepare_judgments(self._db)

        self._stage(anthology_id, "merge")
        clusters, counters.merges = stages.merge_stage(clusters, vectors, snippets, self._judge)

        self._stage(anthology_id, "label")
        clusters = self._apply(stages.label_stage(clusters, snippets, self._judge, seed), counters)

        self._stage(anthology_id, "intruder")
        filtered, counters.intruder_accuracy = stages.intruder_stage(clusters, snippets, self._judge)
        clusters = self._apply(filtered, counters)

        self._stage(anthology_id, "themes")
        themes: List[stages.Theme] = stages.themes_stage(clusters, vectors, self._judge, seed)
        self._judge.ensure_available()

        counters.llm_calls, counters.llm_cached = self._judge.calls, self._judge.cached
        counters.duration_sec = time.time() - started
        return build_result(snippets, themes, counters)

    @staticmethod
    def _apply(filtered: stages.Filtered, counters: RunCounters) -> List[Cluster]:
        counters.clusters_dissolved += filtered.dissolved
        return filtered.kept

    def _stage(self, anthology_id: str, stage: str) -> None:
        _log.info("Anthology %s (%s): stage %s", anthology_id, self._owner, stage)
        self._store.set_stage(anthology_id, stage)

    @staticmethod
    def _no_snippets_message(units: UnitsResult) -> str:
        if units.posts_in_scope == 0:
            return "No posts found for this seed and scope"
        return (
            f"None of the {units.posts_in_scope} matching posts has topic grouping yet; "
            "run post grouping first"
        )
