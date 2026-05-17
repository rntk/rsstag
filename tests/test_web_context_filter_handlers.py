import json
import unittest

from tests.web_test_utils import MongoWebTestCase

from rsstag.web.context_filter_handlers import (
    _normalize_context_filter_data,
    _get_unified_filters,
    _format_count_label,
    _parse_item_payload,
    on_context_filter_suggestions,
    on_context_filter_add_tag,
    on_context_filter_remove_tag,
    on_context_filter_add_item,
    on_context_filter_remove_item,
    on_context_filter_get,
    on_context_filter_clear,
)


class TestNormalizeContextFilterData(unittest.TestCase):
    def test_empty_dict_returns_empty(self):
        self.assertEqual(_normalize_context_filter_data({}), {})

    def test_none_returns_empty(self):
        self.assertEqual(_normalize_context_filter_data(None), {})

    def test_legacy_feed_list_shape(self):
        result = _normalize_context_filter_data({"feeds": ["feed-1", "feed-2"]})
        self.assertEqual(
            result["feeds"],
            {"type": "feeds", "feed_ids": ["feed-1", "feed-2"]},
        )

    def test_legacy_tag_list_shape(self):
        result = _normalize_context_filter_data({"tags": ["tag1", "tag2"]})
        self.assertEqual(
            result["tags"],
            {"type": "tags", "tags": ["tag1", "tag2"]},
        )

    def test_legacy_category_list_shape(self):
        result = _normalize_context_filter_data({"categories": ["cat-1"]})
        self.assertEqual(
            result["categories"],
            {"type": "categories", "category_ids": ["cat-1"]},
        )

    def test_legacy_topics_list_shape(self):
        result = _normalize_context_filter_data({"topics": ["Technology > AI"]})
        self.assertEqual(
            result["topic"],
            {"type": "topic", "topic_path": "Technology > AI"},
        )

    def test_legacy_subtopics_list_shape(self):
        result = _normalize_context_filter_data({"subtopics": ["Technology > AI > Agents"]})
        self.assertEqual(
            result["subtopic"],
            {"type": "subtopic", "topic_path": "Technology > AI > Agents", "parent_topic_path": "", "node": ""},
        )

    def test_new_canonical_shapes_preserved(self):
        data = {
            "tags": {"type": "tags", "tags": ["t1"]},
            "feeds": {"type": "feeds", "feed_ids": ["f1"]},
            "categories": {"type": "categories", "category_ids": ["c1"]},
            "topic": {"type": "topic", "topic_path": "A > B"},
            "subtopic": {
                "type": "subtopic",
                "topic_path": "A > B > C",
                "parent_topic_path": "A > B",
                "node": "C",
            },
        }
        result = _normalize_context_filter_data(data)
        self.assertEqual(result["tags"], data["tags"])
        self.assertEqual(result["feeds"], data["feeds"])
        self.assertEqual(result["categories"], data["categories"])
        self.assertEqual(result["topic"], data["topic"])
        self.assertEqual(result["subtopic"], data["subtopic"])

    def test_mixed_old_and_new_shapes(self):
        data = {
            "feeds": ["feed-old"],
            "categories": {"type": "categories", "category_ids": ["cat-new"]},
            "tags": {"type": "tags", "tags": ["tag-new"]},
            "topics": ["T1 > T2"],
            "subtopic": {"type": "subtopic", "topic_path": "A > B", "parent_topic_path": "", "node": ""},
        }
        result = _normalize_context_filter_data(data)
        self.assertEqual(result["feeds"]["feed_ids"], ["feed-old"])
        self.assertEqual(result["categories"]["category_ids"], ["cat-new"])
        self.assertEqual(result["tags"]["tags"], ["tag-new"])
        self.assertEqual(result["topic"]["topic_path"], "T1 > T2")
        self.assertEqual(result["subtopic"]["topic_path"], "A > B")

    def test_topic_path_normalization(self):
        result = _normalize_context_filter_data({"topics": ["  A  >  B  "]})
        self.assertEqual(result["topic"]["topic_path"], "A > B")

    def test_duplicate_values_deduplicated(self):
        result = _normalize_context_filter_data({"feeds": ["f1", "f1", "f2"]})
        self.assertEqual(result["feeds"]["feed_ids"], ["f1", "f2"])

    def test_empty_values_omitted(self):
        result = _normalize_context_filter_data({"feeds": [], "tags": {}, "topics": [""]})
        self.assertNotIn("feeds", result)
        self.assertNotIn("tags", result)
        self.assertNotIn("topic", result)


class TestGetUnifiedFilters(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(
            _get_unified_filters({}),
            {"tags": [], "feeds": [], "categories": [], "topics": [], "subtopics": []},
        )

    def test_legacy_list_shapes(self):
        result = _get_unified_filters(
            {"tags": ["t1"], "feeds": ["f1"], "categories": ["c1"], "topics": ["A > B"], "subtopics": ["A > B > C"]}
        )
        self.assertEqual(result["tags"], ["t1"])
        self.assertEqual(result["feeds"], ["f1"])
        self.assertEqual(result["categories"], ["c1"])
        self.assertEqual(result["topics"], ["A > B"])
        self.assertEqual(result["subtopics"], ["A > B > C"])

    def test_canonical_shapes(self):
        result = _get_unified_filters(
            {
                "tags": {"type": "tags", "tags": ["t1", "t2"]},
                "feeds": {"type": "feeds", "feed_ids": ["f1"]},
                "categories": {"type": "categories", "category_ids": ["c1"]},
                "topic": {"type": "topic", "topic_path": "X > Y"},
                "subtopic": {"type": "subtopic", "topic_path": "X > Y > Z"},
            }
        )
        self.assertEqual(result["tags"], ["t1", "t2"])
        self.assertEqual(result["feeds"], ["f1"])
        self.assertEqual(result["categories"], ["c1"])
        self.assertEqual(result["topics"], ["X > Y"])
        self.assertEqual(result["subtopics"], ["X > Y > Z"])


class TestFormatCountLabel(unittest.TestCase):
    def test_singular(self):
        self.assertEqual(_format_count_label(1, "feed", "feeds"), "1 feed")

    def test_plural(self):
        self.assertEqual(_format_count_label(2, "feed", "feeds"), "2 feeds")

    def test_zero(self):
        self.assertEqual(_format_count_label(0, "sentence", "sentences"), "0 sentences")


class TestParseItemPayload(unittest.TestCase):
    def _make_request(self, data: bytes):
        from werkzeug.wrappers import Request
        from io import BytesIO
        return Request({"REQUEST_METHOD": "POST", "wsgi.input": BytesIO(data), "CONTENT_LENGTH": str(len(data))})

    def test_valid_tag(self):
        req = self._make_request(json.dumps({"type": "tag", "value": "python"}).encode())
        parsed, error = _parse_item_payload(req)
        self.assertIsNone(error)
        self.assertEqual(parsed, ("tag", "python"))

    def test_invalid_json(self):
        req = self._make_request(b"not-json")
        parsed, error = _parse_item_payload(req)
        self.assertIsNone(parsed)
        self.assertEqual(error.status_code, 400)

    def test_non_dict_body(self):
        req = self._make_request(json.dumps([1, 2]).encode())
        parsed, error = _parse_item_payload(req)
        self.assertIsNone(parsed)
        self.assertEqual(error.status_code, 400)

    def test_unknown_type(self):
        req = self._make_request(json.dumps({"type": "emoji", "value": "x"}).encode())
        parsed, error = _parse_item_payload(req)
        self.assertIsNone(parsed)
        self.assertEqual(error.status_code, 400)

    def test_empty_value(self):
        req = self._make_request(json.dumps({"type": "tag", "value": "  "}).encode())
        parsed, error = _parse_item_payload(req)
        self.assertIsNone(parsed)
        self.assertEqual(error.status_code, 400)


class TestWebContextFilterHandlers(MongoWebTestCase):
    def _seed_fixture(self):
        user, sid = self.seed_test_user("ctx-handler")
        self.test_db.feeds.insert_many(
            [
                {
                    "owner": sid,
                    "feed_id": "feed-1",
                    "category_id": "cat-1",
                    "category_title": "Cat One",
                    "category_local_url": "/category/cat-1",
                    "local_url": "/feed/feed-1",
                    "title": "Feed One",
                    "url": "http://example.com/feed-1",
                    "favicon": "",
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "feed_id": "feed-2",
                    "category_id": "cat-2",
                    "category_title": "Cat Two",
                    "category_local_url": "/category/cat-2",
                    "local_url": "/feed/feed-2",
                    "title": "Feed Two",
                    "url": "http://example.com/feed-2",
                    "favicon": "",
                    "processing": 0,
                },
            ]
        )
        self.test_db.tags.insert_many(
            [
                {
                    "owner": sid,
                    "tag": "python",
                    "posts_count": 1,
                    "unread_count": 1,
                    "words": ["python"],
                    "local_url": "/tag/python",
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "tag": "rust",
                    "posts_count": 1,
                    "unread_count": 1,
                    "words": ["rust"],
                    "local_url": "/tag/rust",
                    "processing": 0,
                },
            ]
        )
        self.app.post_grouping.save_grouped_posts(
            sid,
            ["p1"],
            [{"number": 1, "text": "Sentence", "read": False}],
            {
                "Technology": [1],
                "Technology > AI": [1],
                "Technology > AI > Agents": [1],
            },
        )
        return sid

    def test_on_context_filter_get_empty(self):
        user, sid = self.seed_test_user("ctx-get-empty")
        client = self.get_authenticated_client(sid)
        response = client.get("/api/context-filter")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertFalse(data["active"])
        self.assertEqual(data["filters"]["tags"], [])
        self.assertEqual(data["filters"]["feeds"], [])
        self.assertEqual(data["filters"]["categories"], [])
        self.assertEqual(data["filters"]["topics"], [])
        self.assertEqual(data["filters"]["subtopics"], [])
        self.assertEqual(data["tags"], [])

    def test_on_context_filter_get_with_legacy_filter(self):
        user, sid = self.seed_test_user("ctx-get-legacy")
        self.app.users.update_settings(
            sid,
            {
                "context_filter": {
                    "feeds": ["feed-1"],
                    "tags": ["python"],
                    "categories": ["cat-1"],
                    "topics": ["Technology"],
                    "subtopics": ["Technology > AI"],
                }
            },
        )
        client = self.get_authenticated_client(sid)
        response = client.get("/api/context-filter")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertTrue(data["active"])
        self.assertEqual(data["filters"]["tags"], ["python"])
        self.assertEqual(data["filters"]["feeds"], ["feed-1"])
        self.assertEqual(data["filters"]["categories"], ["cat-1"])
        self.assertEqual(data["filters"]["topics"], ["Technology"])
        self.assertEqual(data["filters"]["subtopics"], ["Technology > AI"])

    def test_on_context_filter_add_tag_success(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post(
            "/api/context-filter/tag",
            data=json.dumps({"tag": "python"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tags"], ["python"])

    def test_on_context_filter_add_tag_missing_tag(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post(
            "/api/context-filter/tag",
            data=json.dumps({"tag": "missing"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_on_context_filter_add_tag_empty(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post(
            "/api/context-filter/tag",
            data=json.dumps({"tag": "  "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_on_context_filter_add_tag_bad_json(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post(
            "/api/context-filter/tag",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_on_context_filter_remove_tag_success(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        # add first
        client.post(
            "/api/context-filter/tag",
            data=json.dumps({"tag": "python"}),
            content_type="application/json",
        )
        # then remove
        response = client.delete(
            "/api/context-filter/tag",
            data=json.dumps({"tag": "python"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tags"], [])

    def test_on_context_filter_remove_tag_not_in_filter(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.delete(
            "/api/context-filter/tag",
            data=json.dumps({"tag": "python"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tags"], [])

    def test_on_context_filter_add_item_tag_validates_existence(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        ok = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "tag", "value": "python"}),
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)
        bad = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "tag", "value": "missing"}),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 404)

    def test_on_context_filter_add_item_feed_validates_existence(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        ok = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-1"}),
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)
        bad = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "missing"}),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 404)

    def test_on_context_filter_add_item_category_validates_existence(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        ok = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "category", "value": "cat-1"}),
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)
        bad = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "category", "value": "missing"}),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 404)

    def test_on_context_filter_add_item_topic_validates_existence(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        ok = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "topic", "value": "Technology > AI"}),
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)
        bad = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "topic", "value": "Missing > Topic"}),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 404)

    def test_on_context_filter_add_item_subtopic_validates_existence(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        ok = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "subtopic", "value": "Technology > AI"}),
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)
        bad = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "subtopic", "value": "Technology"}),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 404)

    def test_on_context_filter_add_item_unknown_type(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "emoji", "value": "x"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_on_context_filter_add_item_empty_value(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "tag", "value": "  "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_on_context_filter_add_item_bad_json(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post(
            "/api/context-filter/item",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_on_context_filter_remove_item_feed(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-1"}),
            content_type="application/json",
        )
        response = client.delete(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-1"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        state = response.get_json()["state"]
        self.assertEqual(state["filters"]["feeds"], [])

    def test_on_context_filter_remove_item_category(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "category", "value": "cat-1"}),
            content_type="application/json",
        )
        response = client.delete(
            "/api/context-filter/item",
            data=json.dumps({"type": "category", "value": "cat-1"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        state = response.get_json()["state"]
        self.assertEqual(state["filters"]["categories"], [])

    def test_on_context_filter_remove_item_topic(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "topic", "value": "Technology > AI"}),
            content_type="application/json",
        )
        response = client.delete(
            "/api/context-filter/item",
            data=json.dumps({"type": "topic", "value": "Technology > AI"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        state = response.get_json()["state"]
        self.assertEqual(state["filters"]["topics"], [])

    def test_on_context_filter_remove_item_subtopic(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "subtopic", "value": "Technology > AI"}),
            content_type="application/json",
        )
        response = client.delete(
            "/api/context-filter/item",
            data=json.dumps({"type": "subtopic", "value": "Technology > AI"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        state = response.get_json()["state"]
        self.assertEqual(state["filters"]["subtopics"], [])

    def test_on_context_filter_remove_item_tag(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "tag", "value": "python"}),
            content_type="application/json",
        )
        response = client.delete(
            "/api/context-filter/item",
            data=json.dumps({"type": "tag", "value": "python"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        state = response.get_json()["state"]
        self.assertEqual(state["filters"]["tags"], [])

    def test_on_context_filter_clear(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "tag", "value": "python"}),
            content_type="application/json",
        )
        response = client.post("/api/context-filter/clear")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tags"], [])
        state = client.get("/api/context-filter").get_json()["data"]
        self.assertFalse(state["active"])
        self.assertEqual(state["filters"]["tags"], [])

    def test_on_context_filter_suggestions_feed(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "feed", "req": "one"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual([item["value"] for item in data], ["feed-1"])
        self.assertEqual(data[0]["label"], "Feed One")

    def test_on_context_filter_suggestions_feed_by_id(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "feed", "req": "feed-2"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["value"] for item in response.get_json()["data"]], ["feed-2"])

    def test_on_context_filter_suggestions_category(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "category", "req": "cat-"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        values = [item["value"] for item in data]
        self.assertIn("cat-1", values)
        self.assertIn("cat-2", values)
        self.assertEqual(data[0]["meta"], "1 feed")

    def test_on_context_filter_suggestions_category_match_by_title(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "category", "req": "one"})
        self.assertEqual(response.status_code, 200)
        values = [item["value"] for item in response.get_json()["data"]]
        self.assertIn("cat-1", values)

    def test_on_context_filter_suggestions_topic(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "topic", "req": "technology"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        values = [item["value"] for item in data]
        self.assertIn("Technology", values)
        self.assertIn("Technology > AI", values)
        self.assertTrue(any(item["meta"].endswith("sentence") or item["meta"].endswith("sentences") for item in data))

    def test_on_context_filter_suggestions_subtopic(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "subtopic", "req": "ai"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        values = [item["value"] for item in data]
        self.assertIn("Technology > AI", values)
        self.assertIn("Technology > AI > Agents", values)
        self.assertNotIn("Technology", values)

    def test_on_context_filter_suggestions_rejects_unknown_type(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "unknown", "req": "x"})
        self.assertEqual(response.status_code, 400)

    def test_on_context_filter_suggestions_empty_query(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "feed", "req": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], [])

    def test_on_context_filter_suggestions_limit_to_20(self):
        user, sid = self.seed_test_user("ctx-suggest-limit")
        docs = []
        for i in range(25):
            docs.append(
                {
                    "owner": sid,
                    "feed_id": f"feed-{i}",
                    "category_id": "",
                    "category_title": "",
                    "category_local_url": "",
                    "local_url": f"/feed/feed-{i}",
                    "title": f"Feed {i}",
                    "url": f"http://example.com/feed-{i}",
                    "favicon": "",
                    "processing": 0,
                }
            )
        self.test_db.feeds.insert_many(docs)
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "feed", "req": "feed"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["data"]), 20)

    def test_on_context_filter_add_item_persists_state(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-1"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        state = response.get_json()["state"]
        self.assertTrue(state["active"])
        self.assertEqual(state["filters"]["feeds"], ["feed-1"])

    def test_on_context_filter_add_item_multiple_tags(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "tag", "value": "python"}),
            content_type="application/json",
        )
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "tag", "value": "rust"}),
            content_type="application/json",
        )
        state = client.get("/api/context-filter").get_json()["data"]
        self.assertEqual(sorted(state["filters"]["tags"]), ["python", "rust"])

    def test_on_context_filter_add_item_multiple_feeds(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-1"}),
            content_type="application/json",
        )
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-2"}),
            content_type="application/json",
        )
        state = client.get("/api/context-filter").get_json()["data"]
        self.assertEqual(sorted(state["filters"]["feeds"]), ["feed-1", "feed-2"])

    def test_on_context_filter_remove_item_removes_only_targeted(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-1"}),
            content_type="application/json",
        )
        client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-2"}),
            content_type="application/json",
        )
        client.delete(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-1"}),
            content_type="application/json",
        )
        state = client.get("/api/context-filter").get_json()["data"]
        self.assertEqual(state["filters"]["feeds"], ["feed-2"])

    def test_on_context_filter_add_tag_deduplicates(self):
        sid = self._seed_fixture()
        client = self.get_authenticated_client(sid)
        client.post(
            "/api/context-filter/tag",
            data=json.dumps({"tag": "python"}),
            content_type="application/json",
        )
        response = client.post(
            "/api/context-filter/tag",
            data=json.dumps({"tag": "python"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tags"], ["python"])


if __name__ == "__main__":
    unittest.main()
