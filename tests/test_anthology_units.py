"""Input completeness regressions without a database server."""

import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from rsstag.anthology.units import UnitsResult, load_units
from rsstag.post_grouping import RssTagPostGrouping


class TestAnthologyUnits(unittest.TestCase):
    def test_large_grouping_is_not_truncated(self) -> None:
        post: Dict[str, Any] = {"pid": "1"}
        doc: Dict[str, Any] = {
            "_id": "grouping-1",
            "sentences": [{"number": i, "text": f"Text {i}"} for i in range(3001)],
            "groups": {f"Topic {i}": [i] for i in range(3001)},
        }
        with patch("rsstag.anthology.units._load_posts", return_value=[post]), patch(
            "rsstag.anthology.units._load_groupings", return_value={"1": [doc]}
        ):
            units: UnitsResult = load_units(MagicMock(), "owner", "news", None)
        self.assertEqual(len(units.snippets), 3001)
        self.assertEqual(units.snippets[-1].sentence_indices, [3000])
        self.assertEqual(len({s.id for s in units.snippets}), 3001)

    def test_later_grouping_read_failure_aborts_loading(self) -> None:
        posts: List[Dict[str, Any]] = [{"pid": i} for i in range(501)]
        db: MagicMock = MagicMock()
        db.post_grouping.find.side_effect = [
            [{"_id": "first", "post_ids": [0]}], RuntimeError("read failed"),
        ]
        with patch("rsstag.anthology.units._load_posts", return_value=posts):
            with self.assertRaisesRegex(RuntimeError, "Could not load grouped topics"):
                load_units(db, "owner", "news", None)
        self.assertEqual(db.post_grouping.find.call_count, 2)

    def test_all_grouping_batches_and_snippets_are_loaded(self) -> None:
        posts: List[Dict[str, Any]] = [{"pid": i} for i in range(501)]
        docs: List[Dict[str, Any]] = [
            {
                "_id": f"doc-{i}", "post_ids": [i],
                "sentences": [{"number": j, "text": f"Text {i} {j}"} for j in range(7)],
                "groups": {f"Topic {j}": [j] for j in range(7)},
            }
            for i in range(501)
        ]
        db: MagicMock = MagicMock()
        db.post_grouping.find.side_effect = [docs[:500], docs[500:]]
        with patch("rsstag.anthology.units._load_posts", return_value=posts):
            units: UnitsResult = load_units(db, "owner", "news", None)
        self.assertEqual(db.post_grouping.find.call_count, 2)
        self.assertEqual(len(units.snippets), 3507)
        self.assertEqual(
            {(s.post_id, s.topic_path) for s in units.snippets},
            {(str(i), f"Topic {j}") for i in range(501) for j in range(7)},
        )
        self.assertEqual(units.ungrouped_posts, 0)

    def test_other_grouping_callers_keep_default_error_behavior(self) -> None:
        db: MagicMock = MagicMock()
        db.post_grouping.find.side_effect = RuntimeError("read failed")
        self.assertEqual(RssTagPostGrouping(db).get_by_post_ids("owner", [1]), [])
