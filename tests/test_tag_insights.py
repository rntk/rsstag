"""Tag insight calculations: collocates, trends, duplicates and novelty."""

import gzip
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch
from urllib.parse import quote_plus

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from rsstag.posts import RssTagPosts
from rsstag.web.tag_insights import (
    DAY, SAMPLE_LIMIT, _aggregate, _changes, _collocates, _post_windows, _timeline,
    aggregate_insights, mark_duplicates, unusual_rows, wall_insights,
)
from tests.db_utils import DBHelper


def _post(text: str, date: float, pid: int = 0) -> dict[str, Any]:
    return {"pid": pid, "unix_date": date, "lemmas": gzip.compress(text.encode("utf-8"))}


def _row(before: str, after: str, key: str, match: str = "Root") -> dict[str, Any]:
    return {"before": before, "match": match, "after": after, "detail_key": key, "title": key}


class TestTagInsights(unittest.TestCase):
    def test_windows_split_sides_skip_stopwords_and_count_once(self) -> None:
        lemmas: list[str] = "far a the shares root fell sharply 12 later root fell".split()
        self.assertEqual(_post_windows(lemmas, ["root"]), ({"far", "shares", "fell", "sharply", "later"},
                                                          {"fell", "sharply", "later"}))
        self.assertIsNone(_post_windows(["other"], ["root"]))
        self.assertEqual(_post_windows("big artifici intellig boom".split(), ["artifici", "intellig"]),
                         ({"big"}, {"boom"}))

    def test_aggregate_counts_documents_not_repeats(self) -> None:
        posts: list[dict[str, Any]] = [
            _post("shares root fell shares root fell", 1.0), _post("shares root", 2.0), _post("unrelated", 3.0),
        ]
        aggregate: dict[str, Any] = _aggregate(posts, ["root"])
        self.assertEqual((aggregate["sampled"], aggregate["matched"]), (3, 2))
        self.assertEqual(aggregate["left"]["shares"], 2)
        self.assertEqual(aggregate["right"]["fell"], 1)

    def test_collocates_prefer_tag_specific_words(self) -> None:
        counter: Counter[str] = Counter({"said": 10, "recal": 6, "once": 1})
        vocabulary: dict[str, dict[str, Any]] = {
            "said": {"posts_count": 1000, "words": ["said"]},
            "recal": {"posts_count": 8, "words": ["recalls", "recall"]},
        }
        terms: list[dict[str, Any]] = _collocates(counter, vocabulary, 1000)
        self.assertEqual([term["label"] for term in terms], ["recall", "said"])
        self.assertEqual(terms[0]["words"], ["recall", "recalls"])
        self.assertEqual(terms[0]["count"], 6)

    def test_timeline_is_daily_and_marks_peak(self) -> None:
        days: list[dict[str, Any]] = _timeline([100 * DAY + 5, 100 * DAY + 9, 98 * DAY])
        self.assertEqual(len(days), 30)
        self.assertEqual([(day["count"], day["level"], day["peak"]) for day in days[-3:]],
                         [(1, 5, False), (0, 0, False), (2, 10, True)])
        self.assertEqual(days[-1]["date"], "1970-04-11")
        self.assertEqual(_timeline([]), [])

    def test_changes_compare_latest_week_with_earlier_posts(self) -> None:
        dated: list[tuple[float, set[str]]] = (
            [(100.0 * DAY, {"tariff", "sales"}) for _ in range(3)]
            + [(80.0 * DAY, {"launch", "sales"}) for _ in range(4)]
        )
        changes: dict[str, list[tuple[str, int, int]]] = _changes(dated)
        self.assertEqual(changes["rising"], [("tariff", 3, 0)])
        self.assertEqual(changes["fading"], [("launch", 0, 4)])
        self.assertEqual(_changes(dated[:3]), {"rising": [], "fading": []})

    def test_duplicates_fold_into_first_row_but_not_same_sentence(self) -> None:
        text: str = "company shares fell sharply after the regulator announced a broad"
        rows: list[dict[str, Any]] = [
            _row(text, "recall of cars today", "a:0"),
            _row(text, "recall of cars today.", "b:0"),
            _row(text, "recall of cars today", "a:0"),
            _row("completely different words", "appear here", "c:0"),
        ]
        self.assertEqual(mark_duplicates(rows), 1)
        self.assertEqual([row["duplicate_of"] for row in rows], [None, 0, None, None])
        self.assertEqual(rows[0]["duplicates"], 1)
        self.assertEqual(mark_duplicates([_row("", "", "x"), _row("", "", "y")]), 0)

    def test_unusual_rows_rank_rare_context_and_skip_duplicates(self) -> None:
        aggregate: dict[str, Any] = {"matched": 20, "context_counts": Counter({
            "share": 15, "fell": 15, "market": 12, "compani": 10,
        })}
        rows: list[dict[str, Any]] = [
            _row("company shares fell", "market", "common"),
            _row("volcano penguins", "orbit", "rare"),
            _row("volcano penguins", "orbit", "dup"),
        ]
        rows[2]["duplicate_of"] = 1
        unusual: list[dict[str, Any]] = unusual_rows(rows, "root", aggregate)
        self.assertEqual([item["detail_key"] for item in unusual], ["rare"])
        self.assertEqual(unusual[0]["rare"], ["volcano", "penguins", "orbit"])
        self.assertEqual(unusual_rows(rows, "root", {**aggregate, "matched": 3}), [])

    def test_aggregate_insights_uses_scoped_newest_sample(self) -> None:
        posts: Mock = Mock()
        posts.get_recent_by_tags.return_value = [_post("big shares root fell", 100.0 * DAY),
                                                 _post("big shares root", 99.0 * DAY)]
        posts.count.return_value = 50
        tags: Mock = Mock()
        tags.get_by_tags.return_value = [{"tag": "shares", "posts_count": 3, "words": ["shares"]}]
        user: dict[str, Any] = {"sid": "owner", "settings": {"only_unread": True}}
        with patch("rsstag.web.tag_insights._get_context_tags", return_value=["ctx"]):
            insights: dict[str, Any] = aggregate_insights(SimpleNamespace(posts=posts, tags=tags), user, "root")
        self.assertEqual(posts.get_recent_by_tags.call_args.args[:4], ("owner", ["root"], SAMPLE_LIMIT, True))
        self.assertEqual(posts.get_recent_by_tags.call_args.kwargs["context_tags"], ["ctx"])
        self.assertEqual(insights["matched"], 2)
        self.assertFalse(insights["limited"])
        self.assertEqual([term["label"] for term in insights["left"]], ["big", "shares"])
        self.assertEqual(tags.get_by_tags.call_args.args[0], "owner")

    def test_wall_insights_failure_is_logged_not_raised(self) -> None:
        posts: Mock = Mock()
        posts.get_recent_by_tags.side_effect = RuntimeError("private")
        user: dict[str, Any] = {"sid": "owner", "settings": {}}
        with patch("rsstag.web.tag_insights._get_context_tags", return_value=[]), \
                self.assertLogs("rsstag.web.tag_insights", level="ERROR"):
            self.assertIsNone(wall_insights(SimpleNamespace(posts=posts), user, "root", []))


class TestTagInsightsTemplate(unittest.TestCase):
    def setUp(self) -> None:
        directory: Path = Path(__file__).resolve().parents[1] / "rsstag/web/templates/default"
        self.environment: Environment = Environment(loader=ChoiceLoader([
            DictLoader({"head-data.html": "", "site-header.html": "{% macro site_header(active, show_context_filter) %}{% endmacro %}"}),
            FileSystemLoader(str(directory)),
        ]))
        self.environment.filters["url_encode"] = quote_plus

    def _render(self, **context: Any) -> str:
        return self.environment.get_template("tag-context-wall.html").render(
            tag="root", rows=[], article_count=0, user_settings={}, page_number=1, has_more=False, **context,
        )

    def test_insights_render_escaped_terms_trends_and_unusual_rows(self) -> None:
        payload: str = '<img src=x onerror="alert(1)">'
        term: dict[str, Any] = {"label": payload, "words": [payload, "recall"], "count": 3}
        change: dict[str, Any] = {"label": "tariff", "words": ["tariff"], "recent": 3, "earlier": 0}
        html: str = self._render(duplicate_count=2, insights={
            "sampled": 12, "matched": 12, "limited": False, "recent_days": 7,
            "timeline": [{"date": "2026-09-29", "count": 0, "level": 0, "peak": False},
                         {"date": "2026-09-30", "count": 4, "level": 10, "peak": True}],
            "left": [term], "right": [], "rising": [change], "fading": [],
            "unusual": [{"detail_key": "p:1", "title": payload, "before": payload, "match": "Root",
                         "after": "orbit", "rare": ["orbit"], "score": 3.2}],
        })
        self.assertNotIn("<img", html)
        self.assertIn('data-filter-words="&lt;img', html)
        self.assertIn("tag-insights__level-10 is-peak", html)
        self.assertIn("0 → 3", html)
        self.assertIn('data-detail-key="p:1"', html)
        self.assertIn("Show 2 near-duplicate rows", html)
        self.assertIn("Nothing stands out", html)

    def test_missing_or_empty_insights_keep_the_wall_usable(self) -> None:
        self.assertIn("Insights are unavailable", self._render(insights=None))
        self.assertIn("Insights are unavailable", self._render())
        self.assertIn("Not enough mentions", self._render(insights={"sampled": 0}))

    def test_duplicate_rows_are_marked_and_counted(self) -> None:
        rows: list[dict[str, Any]] = [
            {**_row("same words here", "and there", "a"), "pid": "a", "number": 1, "read": False,
             "before_words": [], "after_words": [], "duplicates": 1, "duplicate_of": None},
            {**_row("same words here", "and there", "b"), "pid": "b", "number": 1, "read": False,
             "before_words": [], "after_words": [], "duplicates": 0, "duplicate_of": 0},
        ]
        html: str = self.environment.get_template("tag-context-wall.html").render(
            tag="root", rows=rows, article_count=2, user_settings={}, page_number=1, has_more=False,
            duplicate_count=1, insights=None,
        )
        self.assertEqual(html.count("is-duplicate"), 1)
        self.assertIn("×2", html)
        self.assertIn("Show 1 near-duplicate row<", html)


class TestRecentPostsByTags(unittest.TestCase):
    def setUp(self) -> None:
        self.db_helper: DBHelper = DBHelper(port=8765)
        self.db: Any = self.db_helper.create_test_db()
        self.posts: RssTagPosts = RssTagPosts(self.db)

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def test_newest_first_scoped_and_limited(self) -> None:
        self.db_helper.init_db_from_dict(self.db, {"posts": [
            {"owner": "owner", "pid": 1, "tags": ["root", "ctx"], "unix_date": 10, "read": False},
            {"owner": "owner", "pid": 2, "tags": ["root", "ctx"], "unix_date": 30, "read": False},
            {"owner": "owner", "pid": 3, "tags": ["root", "ctx"], "unix_date": 20, "read": True},
            {"owner": "owner", "pid": 4, "tags": ["root"], "unix_date": 40, "read": False},
            {"owner": "other", "pid": 5, "tags": ["root", "ctx"], "unix_date": 50, "read": False},
        ]})
        found: list[dict[str, Any]] = list(self.posts.get_recent_by_tags(
            "owner", ["root"], 2, projection={"_id": 0, "pid": 1}, context_tags=["ctx"],
        ))
        self.assertEqual([post["pid"] for post in found], [2, 3])
        unread: list[dict[str, Any]] = list(self.posts.get_recent_by_tags(
            "owner", ["root"], 10, True, {"_id": 0, "pid": 1}, ["ctx"],
        ))
        self.assertEqual([post["pid"] for post in unread], [2, 1])


if __name__ == "__main__":
    unittest.main()
