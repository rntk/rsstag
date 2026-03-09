import unittest

from rsstag.context_filter import (
    CategoryContextFilter,
    ContextFilterManager,
    FeedContextFilter,
    SubtopicContextFilter,
    TagContextFilter,
    TopicContextFilter,
)


class TestConcreteContextFilters(unittest.TestCase):
    def test_feed_filter_supports_single_and_multi_values(self):
        self.assertEqual({"feed_id": "12"}, FeedContextFilter([12]).get_filter_query("owner"))
        self.assertEqual(
            {"feed_id": {"$in": ["12", "13"]}},
            FeedContextFilter([12, "13", "13"]).get_filter_query("owner"),
        )

    def test_category_filter_supports_single_and_multi_values(self):
        self.assertEqual(
            {"category_id": "news"},
            CategoryContextFilter(["news"]).get_filter_query("owner"),
        )
        self.assertEqual(
            {"category_id": {"$in": ["news", "tech"]}},
            CategoryContextFilter(["news", "tech"]).get_filter_query("owner"),
        )

    def test_topic_filter_uses_hierarchical_prefix_matching(self):
        query = TopicContextFilter("Science > AI").get_filter_query("owner")
        self.assertEqual(
            {"topic": {"$regex": r"^Science\s*>\s*AI(?:\s*>\s*.*)?$"}},
            query,
        )

    def test_subtopic_filter_supports_explicit_node_or_direct_topic(self):
        from_parent = SubtopicContextFilter(parent_topic_path="Science", node="AI")
        self.assertEqual("Science > AI", from_parent.topic_path)
        self.assertEqual(
            {"topic": {"$regex": r"^Science\s*>\s*AI(?:\s*>\s*.*)?$"}},
            from_parent.get_filter_query("owner"),
        )

        direct = SubtopicContextFilter(topic_path="Science > AI > Agents")
        self.assertEqual(
            {"topic": {"$regex": r"^Science\s*>\s*AI\s*>\s*Agents(?:\s*>\s*.*)?$"}},
            direct.get_filter_query("owner"),
        )


class TestContextFilterManager(unittest.TestCase):
    def test_convenience_getters_create_typed_filters(self):
        manager = ContextFilterManager()
        self.assertIsInstance(manager.get_tag_filter(), TagContextFilter)
        self.assertIsInstance(manager.get_feed_filter(), FeedContextFilter)
        self.assertIsInstance(manager.get_category_filter(), CategoryContextFilter)
        self.assertIsInstance(manager.get_topic_filter(), TopicContextFilter)
        self.assertIsInstance(manager.get_subtopic_filter(), SubtopicContextFilter)

    def test_combined_query_uses_and_and_merges_tag_clauses(self):
        manager = ContextFilterManager(
            {
                "tags": TagContextFilter(["python", "ai"]),
                "feeds": FeedContextFilter(["f1", "f2"]),
                "categories": CategoryContextFilter(["c1"]),
                "topic": TopicContextFilter("Science > AI"),
            }
        )

        combined = manager.get_combined_query("alice")
        self.assertEqual(
            {
                "$and": [
                    {"owner": "alice"},
                    {"feed_id": {"$in": ["f1", "f2"]}},
                    {"category_id": "c1"},
                    {"topic": {"$regex": r"^Science\s*>\s*AI(?:\s*>\s*.*)?$"}},
                    {"tags": {"$all": ["python", "ai"]}},
                ]
            },
            combined,
        )


    def test_from_dict_accepts_canonical_shapes(self):
        restored = ContextFilterManager.from_dict(
            {
                "tags": {"type": "tags", "tags": ["python"]},
                "feeds": {"type": "feeds", "feed_ids": ["feed-1"]},
                "categories": {"type": "categories", "category_ids": ["cat-1"]},
                "topic": {"type": "topic", "topic_path": "Root > Child"},
                "subtopic": {"type": "subtopic", "topic_path": "Root > Child > Node"},
            }
        )

        self.assertEqual(["python"], restored.get_tag_filter().tags)
        self.assertEqual(["feed-1"], restored.get_feed_filter().feed_ids)
        self.assertEqual(["cat-1"], restored.get_category_filter().category_ids)
        self.assertEqual("Root > Child", restored.get_topic_filter().topic_path)
        self.assertEqual("Root > Child > Node", restored.get_subtopic_filter().topic_path)
    def test_serialization_roundtrip_supports_all_filter_types(self):
        manager = ContextFilterManager(
            {
                "tags": TagContextFilter(["python"]),
                "feeds": FeedContextFilter(["feed-1"]),
                "categories": CategoryContextFilter(["cat-1"]),
                "topic": TopicContextFilter("Root > Child"),
                "subtopic": SubtopicContextFilter(parent_topic_path="Root", node="Child"),
            }
        )

        restored = ContextFilterManager.from_dict(manager.to_dict())

        self.assertEqual(["python"], restored.get_tag_filter().tags)
        self.assertEqual(["feed-1"], restored.get_feed_filter().feed_ids)
        self.assertEqual(["cat-1"], restored.get_category_filter().category_ids)
        self.assertEqual("Root > Child", restored.get_topic_filter().topic_path)
        self.assertEqual("Root > Child", restored.get_subtopic_filter().topic_path)


if __name__ == "__main__":
    unittest.main()
