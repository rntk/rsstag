"""Tests for the TASK_TAGS_LLM_RANK handler (rsstag/tag_rank_llm.py)."""

import json
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from pymongo.database import Database

from rsstag import tag_rank_llm
from rsstag.tag_rank_llm import (
    build_prompt,
    candidate_query,
    clamp_score,
    parse_scores,
    rank_with_llm,
    run,
    run_with_llm,
    strip_code_fences,
    surface_words,
)
from tests.db_utils import DBHelper

TEST_MONGO_PORT: int = 8765


class FakeLLM:
    """Scores every term in the prompt with a fixed map; records prompts."""

    def __init__(self, scores: Dict[str, Any], fail_calls: Optional[List[int]] = None) -> None:
        self.scores: Dict[str, Any] = scores
        self.fail_calls: List[int] = fail_calls or []
        self.prompts: List[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if len(self.prompts) in self.fail_calls:
            return "OpenAI error: rate limited"
        terms: List[str] = [
            line[2:].split(" (")[0] for line in prompt.splitlines() if line.startswith("- ")
        ]
        payload: Dict[str, Any] = {t: self.scores.get(t, 3) for t in terms}
        return "```json\n" + json.dumps(payload) + "\n```"


class TestPromptBuilding(unittest.TestCase):
    def test_surface_words_skip_stem_and_dupes_and_cap(self) -> None:
        doc: Dict[str, Any] = {"tag": "run", "words": ["run", "running", "runs", "running", "ran", "runner"]}
        self.assertEqual(["running", "runs", "ran"], surface_words(doc))

    def test_surface_words_missing(self) -> None:
        self.assertEqual([], surface_words({"tag": "x"}))
        self.assertEqual([], surface_words({"tag": "x", "words": "bad"}))

    def test_build_prompt_lists_terms_and_forms(self) -> None:
        prompt: str = build_prompt(
            [{"tag": "python", "words": ["python", "pythons"]}, {"tag": "said"}]
        )
        self.assertIn("- python (pythons)\n", prompt)
        self.assertIn("- said\n", prompt)
        self.assertIn("JSON", prompt)
        self.assertIn('"said"', prompt)


class TestResponseParsing(unittest.TestCase):
    names: List[str] = ["python", "said", "nasa"]

    def test_plain_json(self) -> None:
        self.assertEqual(
            {"python": 5.0, "said": 1.0}, parse_scores('{"python": 5, "said": 1}', self.names)
        )

    def test_code_fences(self) -> None:
        text: str = '```json\n{"nasa": 4}\n```'
        self.assertEqual('{"nasa": 4}', strip_code_fences(text))
        self.assertEqual({"nasa": 4.0}, parse_scores(text, self.names))

    def test_surrounding_text(self) -> None:
        self.assertEqual({"nasa": 5.0}, parse_scores('Here: {"nasa": 5} done', self.names))

    def test_bad_json_returns_none(self) -> None:
        self.assertIsNone(parse_scores("{python: 5", self.names))
        self.assertIsNone(parse_scores("", self.names))
        self.assertIsNone(parse_scores("[1, 2]", self.names))
        self.assertIsNone(parse_scores("OpenAI error boom", self.names))

    def test_out_of_range_clamped_and_rounded(self) -> None:
        scores: Optional[Dict[str, float]] = parse_scores(
            '{"python": 9, "said": -2, "nasa": "3.6"}', self.names
        )
        self.assertEqual({"python": 5.0, "said": 1.0, "nasa": 4.0}, scores)

    def test_unknown_tags_and_non_numbers_ignored(self) -> None:
        scores: Optional[Dict[str, float]] = parse_scores(
            '{"zzz": 4, "python": "high", "said": true, "NASA": 5}', self.names
        )
        self.assertEqual({"nasa": 5.0}, scores)

    def test_clamp_score(self) -> None:
        self.assertIsNone(clamp_score(float("nan")))
        self.assertIsNone(clamp_score(None))
        self.assertEqual(2.0, clamp_score(2))


class TestCandidateQuery(unittest.TestCase):
    def test_query_shape(self) -> None:
        query: Dict[str, Any] = candidate_query("alice", 3)
        self.assertEqual("alice", query["owner"])
        self.assertEqual({"$gte": 3}, query["posts_count"])
        self.assertEqual({"$exists": False}, query["rank.llm_score"])
        self.assertEqual({"$ne": True}, query["rank.shape_junk"])
        self.assertIn("$not", query["rank.df_ratio"])


class TestRunWithoutLLM(unittest.TestCase):
    def test_unconfigured_llm_is_skipped_as_done(self) -> None:
        db: MagicMock = MagicMock()
        db.users.find_one.return_value = {"sid": "alice", "settings": {}}
        with self.assertLogs("tag_rank_llm", level="WARNING"):
            self.assertTrue(run(db, {"settings": {}}, "alice"))
        db.tags.bulk_write.assert_not_called()

    def test_init_error_is_retryable(self) -> None:
        with patch.object(tag_rank_llm, "make_llm_call", side_effect=RuntimeError("x")):
            self.assertFalse(run(MagicMock(), {}, "alice"))

    def test_pending_recomputation_failure_is_retryable(self) -> None:
        db: MagicMock = MagicMock()
        db.tags.find.return_value = [{"tag": "python"}]
        call_llm: MagicMock = MagicMock()
        with patch.object(tag_rank_llm, "recompute_derived", side_effect=RuntimeError("x")):
            self.assertFalse(run_with_llm(db, "alice", call_llm))
        call_llm.assert_not_called()


class MongoTestCase(unittest.TestCase):
    db_helper: DBHelper
    db: Database

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=TEST_MONGO_PORT)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            self.skipTest(f"MongoDB on port {TEST_MONGO_PORT} is required: {exc}")
        self.db = self.db_helper.create_test_db()
        self.owner: str = "alice"

    def tearDown(self) -> None:
        self.db_helper.teardown_all()
        self.db_helper.close()

    def _seed(self, tag: str, posts_count: int, rank: Optional[Dict[str, Any]] = None) -> None:
        doc: Dict[str, Any] = {
            "owner": self.owner,
            "tag": tag,
            "words": [tag, f"{tag}s"],
            "posts_count": posts_count,
            "freq": posts_count,
        }
        if rank is not None:
            doc["rank"] = rank
        self.db.tags.insert_one(doc)

    def _rank(self, tag: str) -> Dict[str, Any]:
        doc: Dict[str, Any] = self.db.tags.find_one({"owner": self.owner, "tag": tag}) or {}
        return doc.get("rank") or {}


class TestCandidatesWithMongo(MongoTestCase):
    def test_selection_filters_and_orders(self) -> None:
        self._seed("python", 10, {"ridf": 1.0})
        self._seed("nasa", 20)
        self._seed("rare", 2)
        self._seed("1234", 50, {"shape_junk": True})
        self._seed("the", 90, {"df_ratio": 0.9})
        self._seed("done", 30, {"llm_score": 4.0})
        self.db.tags.insert_one({"owner": "bob", "tag": "bobtag", "posts_count": 99})
        docs: List[Dict[str, Any]] = tag_rank_llm.select_candidates(self.db, self.owner)
        self.assertEqual(["nasa", "python"], [d["tag"] for d in docs])

    def test_selection_cap(self) -> None:
        for i in range(5):
            self._seed(f"tag{i}", 10 + i)
        docs = tag_rank_llm.select_candidates(self.db, self.owner, limit=2)
        self.assertEqual(["tag4", "tag3"], [d["tag"] for d in docs])


class TestRunWithMongo(MongoTestCase):
    def test_failed_derivation_retries_without_another_llm_call(self) -> None:
        self._seed("python", 10)
        fake: FakeLLM = FakeLLM({"python": 5})
        with patch.object(tag_rank_llm, "recompute_derived", side_effect=RuntimeError("write failed")):
            self.assertFalse(run_with_llm(self.db, self.owner, fake))
        doc: Dict[str, Any] = self.db.tags.find_one({"owner": self.owner, "tag": "python"}) or {}
        self.assertTrue(doc["rank_pending"])
        self.assertEqual(5.0, doc["rank"]["llm_score"])
        self.assertTrue(run_with_llm(self.db, self.owner, fake))
        self.assertEqual(1, len(fake.prompts))
        doc = self.db.tags.find_one({"owner": self.owner, "tag": "python"}) or {}
        self.assertFalse(doc.get("rank_pending", False))
        self.assertIn("score", doc["rank"])

    def test_partial_batch_failure_is_retryable(self) -> None:
        for i in range(101):
            self._seed(f"tag{i}", 10)
        self.assertFalse(run_with_llm(self.db, self.owner, FakeLLM({}, fail_calls=[1])))

    def test_scores_written_and_derived_recomputed(self) -> None:
        self._seed("python", 10, {"ridf": 1.0})
        self._seed("said", 40, {"ridf": 0.5})
        fake: FakeLLM = FakeLLM({"python": 5, "said": 1})
        self.assertTrue(run_with_llm(self.db, self.owner, fake))
        self.assertEqual(5.0, self._rank("python")["llm_score"])
        self.assertFalse(self._rank("python")["noise"])
        self.assertIn("score", self._rank("python"))
        self.assertEqual(1.0, self._rank("said")["llm_score"])
        self.assertTrue(self._rank("said")["noise"])

    def test_failed_batch_skipped_others_written(self) -> None:
        for i in range(5):
            self._seed(f"tag{i}", 10 + i)
        fake: FakeLLM = FakeLLM({}, fail_calls=[1])
        stats = rank_with_llm(self.db, self.owner, fake, batch_size=2)
        self.assertEqual((3, 1, 3), (stats.batches, stats.failed_batches, stats.scored))
        self.assertNotIn("llm_score", self._rank("tag4"))
        self.assertNotIn("llm_score", self._rank("tag3"))
        self.assertEqual(3.0, self._rank("tag0")["llm_score"])

    def test_all_batches_failed_is_retryable(self) -> None:
        self._seed("python", 10)
        fake: FakeLLM = FakeLLM({}, fail_calls=[1])
        self.assertFalse(run_with_llm(self.db, self.owner, fake))

    def test_raising_llm_is_handled(self) -> None:
        self._seed("python", 10)

        def boom(prompt: str) -> str:
            raise TimeoutError("timeout")

        self.assertFalse(run_with_llm(self.db, self.owner, boom))
        self.assertNotIn("llm_score", self._rank("python"))

    def test_no_candidates_is_done(self) -> None:
        self.assertTrue(run_with_llm(self.db, self.owner, FakeLLM({})))

    def test_second_run_skips_scored_tags(self) -> None:
        self._seed("python", 10)
        run_with_llm(self.db, self.owner, FakeLLM({}))
        fake: FakeLLM = FakeLLM({})
        run_with_llm(self.db, self.owner, fake)
        self.assertEqual([], fake.prompts)

    def test_run_uses_router_with_user_settings(self) -> None:
        self._seed("python", 10)
        self.db.users.insert_one({"sid": self.owner, "settings": {"worker_llm": "openai"}})
        router: MagicMock = MagicMock()
        router.call.return_value = '{"python": 4}'
        with patch("rsstag.llm.router.LLMRouter", return_value=router):
            self.assertTrue(run(self.db, {}, self.owner))
        args, kwargs = router.call.call_args
        self.assertEqual({"worker_llm": "openai"}, args[0])
        self.assertEqual("worker_llm", kwargs["provider_key"])
        self.assertEqual(4.0, self._rank("python")["llm_score"])


if __name__ == "__main__":
    unittest.main()
