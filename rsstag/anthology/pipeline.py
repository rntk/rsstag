"""Anthology pipeline orchestration: units → candidates → judge stages → result."""

import logging
import time
from contextlib import contextmanager
from threading import Event, Thread
from typing import Any, Dict, Iterator, List, Optional

from pymongo.database import Database

from rsstag.anthologies import STATUS_FAILED, STATUS_PROCESSING, RssTagAnthologies
from rsstag.anthology import stages
from rsstag.anthology.candidates import Cluster, Vectors, build_candidates, vectorize
from rsstag.anthology.judge import Judge, JudgeUnavailableError, prepare_judgments
from rsstag.anthology.loose import label_leftovers, loose_theme
from rsstag.anthology.result import RunCounters, build_result
from rsstag.anthology.recovery import recover_unsorted
from rsstag.anthology.units import Snippet, UnitsResult, load_units

_log: logging.Logger = logging.getLogger("anthology.pipeline")
HEARTBEAT_INTERVAL_SECONDS: float = 30.0


class AnthologyPipelineError(RuntimeError):
    """Expected pipeline failure with a user-facing message."""


class AnthologyRunSupersededError(RuntimeError):
    """This worker can no longer publish or update the claimed run."""


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
        self._run_id: Optional[str] = None
        self._superseded: Event = Event()

    def run(self, anthology_id: str, run_id: Optional[str] = None) -> bool:
        """Run all stages; on failure mark the anthology failed and return False."""
        started: float = time.time()
        self._run_id = run_id
        try:
            doc: Dict[str, Any] = self._load_doc(anthology_id)
            if not self._claim(anthology_id, doc, run_id):
                return False
            with self._keep_alive(anthology_id):
                result: Dict[str, Any] = self._build(anthology_id, doc, started)
                self._check_run(anthology_id)
                if not self._store.save_result(
                    anthology_id, result, run_id=self._run_id, owner=self._owner
                ):
                    return self._fail(anthology_id, "Can't save anthology result")
        except AnthologyRunSupersededError:
            _log.info("Anthology %s run superseded or unavailable; stopping worker", anthology_id)
            return False
        except (AnthologyPipelineError, JudgeUnavailableError) as exc:
            _log.warning("Anthology %s failed for %s: %s", anthology_id, self._owner, exc)
            return self._fail(anthology_id, str(exc))
        except Exception as exc:
            _log.exception("Anthology %s crashed for %s", anthology_id, self._owner)
            return self._fail(anthology_id, f"Anthology pipeline error: {exc or exc.__class__.__name__}")
        _log.info("Anthology %s done for %s: %s", anthology_id, self._owner, result["metrics"])
        return True

    def _fail(self, anthology_id: str, message: str) -> bool:
        self._store.update_status(
            anthology_id, STATUS_FAILED, error=message[:500],
            run_id=self._run_id, owner=self._owner,
        )
        return False

    def _claim(self, anthology_id: str, doc: Dict[str, Any], run_id: Optional[str]) -> bool:
        if run_id is not None:
            return doc.get("run_id") == run_id and doc.get("status") == STATUS_PROCESSING
        self._run_id = self._store.claim_run(self._owner, anthology_id)
        return self._run_id is not None

    @contextmanager
    def _keep_alive(self, anthology_id: str) -> Iterator[None]:
        """Refresh ownership even while a single slow model call is in flight."""
        stop: Event = Event()
        self._superseded.clear()
        worker: Thread = Thread(
            target=self._heartbeat_loop, args=(anthology_id, self._run_id, stop), daemon=True
        )
        self._judge.on_progress = lambda: self._check_run(anthology_id)
        worker.start()
        try:
            yield
        finally:
            self._judge.on_progress = None
            stop.set()
            worker.join(timeout=1.0)

    def _heartbeat_loop(self, anthology_id: str, run_id: Optional[str], stop: Event) -> None:
        while not stop.wait(HEARTBEAT_INTERVAL_SECONDS):
            if run_id is None or not self._store.heartbeat(anthology_id, self._owner, run_id):
                self._superseded.set()
                return

    def _check_run(self, anthology_id: str) -> None:
        if self._superseded.is_set() or self._run_id is None or not self._store.heartbeat(
            anthology_id, self._owner, self._run_id
        ):
            raise AnthologyRunSupersededError()

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
        snippets: List[Snippet] = units.snippets

        self._stage(anthology_id, "candidates")
        vectors: Vectors = vectorize([s.vector_text for s in snippets])
        clusters: List[Cluster]
        unsorted: List[int]
        clusters, unsorted = build_candidates(vectors)
        counters.clusters_candidate = len(clusters)
        counters.first_pass_unsorted["singleton"] = len(unsorted)
        prepare_judgments(self._db)

        self._stage(anthology_id, "merge")
        clusters, counters.merges = stages.merge_stage(clusters, vectors, snippets, self._judge)

        self._stage(anthology_id, "label")
        labeled: stages.Filtered = stages.label_stage(clusters, snippets, self._judge, seed)
        counters.first_pass_unsorted["label_rejected"] = len(labeled.released)
        clusters = self._apply(labeled, counters)

        self._stage(anthology_id, "intruder")
        filtered: stages.Filtered
        filtered, counters.intruder_accuracy = stages.intruder_stage(clusters, snippets, self._judge)
        counters.first_pass_unsorted["intruder_rejected"] = len(filtered.released)
        clusters = self._apply(filtered, counters)

        self._stage(anthology_id, "recovery")
        first_pass_clusters: List[Cluster] = clusters
        clusters = recover_unsorted(clusters, vectors, snippets, self._judge, seed, counters)

        self._stage(anthology_id, "loose")
        loose: List[Cluster] = label_leftovers(clusters, vectors, snippets, self._judge, seed, counters)

        self._stage(anthology_id, "themes")
        themes: List[stages.Theme] = self._themes(
            first_pass_clusters, clusters[len(first_pass_clusters):], loose, vectors, seed
        )
        self._judge.ensure_available()

        counters.llm_calls, counters.llm_cached = self._judge.calls, self._judge.cached
        counters.duration_sec = time.time() - started
        return build_result(snippets, themes, counters)

    def _themes(
        self,
        first_pass: List[Cluster],
        recovered: List[Cluster],
        loose: List[Cluster],
        vectors: Vectors,
        seed: str,
    ) -> List[stages.Theme]:
        """First-pass themes plus one theme per recovered cluster, loose topics last."""
        themes: List[stages.Theme] = stages.themes_stage(first_pass, vectors, self._judge, seed)
        themes.extend(
            stages.Theme(clusters=[cluster], label=cluster.label, keywords=list(cluster.keywords))
            for cluster in recovered
        )
        themes.sort(key=lambda theme: (-theme.size, theme.clusters[0].id))
        if loose:
            themes.append(loose_theme(loose, vectors))
        return themes

    @staticmethod
    def _apply(filtered: stages.Filtered, counters: RunCounters) -> List[Cluster]:
        counters.clusters_dissolved += filtered.dissolved
        return filtered.kept

    def _stage(self, anthology_id: str, stage: str) -> None:
        _log.info("Anthology %s (%s): stage %s", anthology_id, self._owner, stage)
        if not self._store.set_stage(
            anthology_id, stage, run_id=self._run_id, owner=self._owner
        ):
            raise AnthologyRunSupersededError()

    @staticmethod
    def _no_snippets_message(units: UnitsResult) -> str:
        if units.posts_in_scope == 0:
            return "No posts found for this seed and scope"
        return (
            f"None of the {units.posts_in_scope} matching posts has topic grouping yet; "
            "run post grouping first"
        )
