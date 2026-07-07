"""Tests for the deterministic normalization pre-pass in the topic-merge flow.

Pure-logic tests run everywhere. Mocked-LLM agent-level tests exercise
``TopicMergeAgent._resolve_bucket`` without a database. DB-backed tests follow
the same SkipTest pattern as tests/test_worker_task_dispatch.py (they require
MongoDB on port 8765 and skip otherwise).
"""

import re
import socket
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from rsstag.topic_aliases import RssTagTopicAliases, normalize_label
from rsstag.topic_merge import TopicMergeAgent, find_fuzzy_canonical
from tests.db_utils import DBHelper

_NEW_ENTRY_RE = re.compile(r"^\d+\.\s*\[N\]", re.MULTILINE)


def _count_new_entries(prompt_text: str) -> int:
    """Count actual [N] entry lines, ignoring [N] mentions in static prose."""
    return len(_NEW_ENTRY_RE.findall(prompt_text))


class TestNormalizeLabel(unittest.TestCase):
    def test_case_insensitive(self) -> None:
        self.assertEqual(normalize_label("LLMs"), normalize_label("llms"))

    def test_punctuation_variants_match(self) -> None:
        self.assertEqual(
            normalize_label("LLM-Training"), normalize_label("LLM Training")
        )

    def test_word_order_variants_match(self) -> None:
        self.assertEqual(
            normalize_label("LLM Training"), normalize_label("Training LLM")
        )

    def test_distinct_concepts_differ(self) -> None:
        self.assertNotEqual(normalize_label("cats"), normalize_label("dogs"))

    def test_unicode_nfkc_variants_match(self) -> None:
        # "ﬁ" is the "fi" ligature; NFKC decomposes it to "fi".
        self.assertEqual(normalize_label("ﬁle"), normalize_label("file"))

    def test_empty_string(self) -> None:
        self.assertEqual(normalize_label(""), "")

    def test_cyrillic_case_and_order(self) -> None:
        self.assertEqual(
            normalize_label("Машинное обучение"),
            normalize_label("обучение машинное"),
        )


class TestFindFuzzyCanonical(unittest.TestCase):
    def test_hit_above_threshold_and_min_length(self) -> None:
        canonicals = [("id1", "Training Models", "models training")]
        # One character different from "models training" (11 vs 16 chars
        # normal form), long enough to clear both the length guard and the
        # 0.95 ratio threshold.
        result = find_fuzzy_canonical("models trainingx", canonicals)
        self.assertIsNotNone(result)
        assert result is not None
        canonical_id, canonical_label, ratio = result
        self.assertEqual(canonical_id, "id1")
        self.assertEqual(canonical_label, "Training Models")
        self.assertGreaterEqual(ratio, 0.95)

    def test_miss_below_threshold(self) -> None:
        canonicals = [("id1", "Machine Learning", "learning machine")]
        result = find_fuzzy_canonical("deep neural networks", canonicals)
        self.assertIsNone(result)

    def test_miss_on_short_strings(self) -> None:
        # "cat" vs "car": high ratio possible on short strings, but the
        # explicit length guard (<6 chars) must reject it regardless.
        canonicals = [("id1", "car", "car")]
        result = find_fuzzy_canonical("cat", canonicals)
        self.assertIsNone(result)

    def test_no_candidates_returns_none(self) -> None:
        self.assertIsNone(find_fuzzy_canonical("anything long enough", []))

    def test_best_of_multiple_candidates(self) -> None:
        canonicals = [
            ("id1", "Something Else Entirely", "else entirely something"),
            ("id2", "Training Models", "models training"),
        ]
        result = find_fuzzy_canonical("models trainingx", canonicals)
        assert result is not None
        self.assertEqual(result[0], "id2")


def _make_agent(llm_responses: List[str]) -> TopicMergeAgent:
    llm_router = MagicMock()
    llm_router.call.side_effect = llm_responses
    agent = TopicMergeAgent(MagicMock(), llm_router, "owner-1")
    aliases = MagicMock()
    aliases.make_canonical_id.side_effect = RssTagTopicAliases.make_canonical_id
    agent._aliases = aliases
    return agent


class TestPrepassNormalFormCacheHit(unittest.TestCase):
    """A label whose normal form matches an existing alias skips the LLM."""

    def test_resolves_without_llm_call(self) -> None:
        agent = _make_agent([])
        aliases = agent._aliases
        aliases.get_alias.return_value = None
        aliases.get_existing_canonicals.return_value = []

        def fake_by_normal_form(
            _owner: str, _level: int, _parent: str, normal_form: str
        ) -> Optional[Dict[str, str]]:
            if normal_form == normalize_label("LLMs"):
                return {"canonical_id": "p/llms", "canonical_label": "LLMs"}
            return None

        aliases.get_alias_by_normal_form.side_effect = fake_by_normal_form

        resolved = agent._resolve_bucket(0, "p", "Parent", ["llms"], False)

        agent._llm_router.call.assert_not_called()
        self.assertEqual(
            resolved["llms"],
            {"canonical_id": "p/llms", "canonical_label": "LLMs"},
        )
        aliases.upsert_alias.assert_called_once_with(
            "owner-1", 0, "p", "llms", "p/llms", "LLMs"
        )


class TestPrepassInBucketGrouping(unittest.TestCase):
    """Two in-bucket labels sharing a normal form produce one LLM entry."""

    def test_both_resolve_to_same_canonical(self) -> None:
        agent = _make_agent(["NO_MERGES"])
        aliases = agent._aliases
        aliases.get_alias.return_value = None
        aliases.get_alias_by_normal_form.return_value = None
        aliases.get_existing_canonicals.return_value = []

        resolved = agent._resolve_bucket(
            0, "p", "Parent", ["LLM Training", "training llm"], False
        )

        # Only one distinct normal form -> a single new-label entry sent to
        # the LLM (verify via the prompt built into the call args).
        agent._llm_router.call.assert_called_once()
        prompt_text = agent._llm_router.call.call_args.args[1][0]
        self.assertEqual(_count_new_entries(prompt_text), 1)

        self.assertEqual(
            resolved["LLM Training"], resolved["training llm"]
        )
        self.assertEqual(
            resolved["LLM Training"]["canonical_label"], "LLM Training"
        )


class TestPrepassFuzzyAutoMerge(unittest.TestCase):
    """A near-duplicate label auto-merges onto an existing canonical."""

    def test_skips_llm_call(self) -> None:
        agent = _make_agent([])
        aliases = agent._aliases
        aliases.get_alias.return_value = None
        aliases.get_alias_by_normal_form.return_value = None
        aliases.get_existing_canonicals.return_value = [
            {"canonical_id": "p/training-pipeline", "canonical_label": "Training Pipeline"}
        ]

        resolved = agent._resolve_bucket(
            0, "p", "Parent", ["Training Pipelines"], False
        )

        agent._llm_router.call.assert_not_called()
        self.assertEqual(
            resolved["Training Pipelines"],
            {
                "canonical_id": "p/training-pipeline",
                "canonical_label": "Training Pipeline",
            },
        )
        aliases.upsert_alias.assert_called_once_with(
            "owner-1",
            0,
            "p",
            "Training Pipelines",
            "p/training-pipeline",
            "Training Pipeline",
        )


class TestForceModeBypassesPrepass(unittest.TestCase):
    """force=True sends every label to the LLM, ignoring the pre-pass."""

    def test_all_labels_go_to_llm(self) -> None:
        agent = _make_agent(["NO_MERGES"])
        aliases = agent._aliases
        # Even though these would all pre-pass-resolve to the same thing,
        # get_alias/get_alias_by_normal_form must never be consulted because
        # force bypasses the cache entirely.
        aliases.get_existing_canonicals.return_value = []

        resolved = agent._resolve_bucket(
            0, "p", "Parent", ["LLMs", "llms", "LLM"], True
        )

        aliases.get_alias.assert_not_called()
        aliases.get_alias_by_normal_form.assert_not_called()
        agent._llm_router.call.assert_called_once()
        prompt_text = agent._llm_router.call.call_args.args[1][0]
        self.assertEqual(_count_new_entries(prompt_text), 3)
        # NO_MERGES: each label mints (or would mint) its own canonical.
        self.assertEqual(set(resolved.keys()), {"LLMs", "llms", "LLM"})


class MongoBackedPrepassTestCase(unittest.TestCase):
    db_helper: DBHelper

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for topic merge prepass tests: {exc}"
            )

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=8765)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for topic merge prepass tests: {exc}"
            )
        self.db = self.db_helper.create_test_db()

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()


class TestUpsertAliasStoresNormalForm(MongoBackedPrepassTestCase):
    def test_normal_form_field_is_set(self) -> None:
        aliases = RssTagTopicAliases(self.db)
        aliases.prepare()
        aliases.upsert_alias("u", 0, "", "LLM Training", "p/llm-training", "LLM Training")

        doc = self.db.topic_aliases.find_one({"raw_label": "LLM Training"})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["normal_form"], normalize_label("LLM Training"))


class TestGetAliasByNormalForm(MongoBackedPrepassTestCase):
    def test_finds_matching_alias_by_normal_form(self) -> None:
        aliases = RssTagTopicAliases(self.db)
        aliases.prepare()
        aliases.upsert_alias("u", 0, "", "LLM Training", "p/llm-training", "LLM Training")

        found = aliases.get_alias_by_normal_form(
            "u", 0, "", normalize_label("training-llm")
        )

        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["canonical_id"], "p/llm-training")
        self.assertEqual(found["canonical_label"], "LLM Training")

    def test_returns_none_when_absent(self) -> None:
        aliases = RssTagTopicAliases(self.db)
        aliases.prepare()

        found = aliases.get_alias_by_normal_form("u", 0, "", "no such form")

        self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()
