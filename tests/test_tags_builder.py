import unittest
from rsstag.tags_builder import TagsBuilder


class TestTagsBuilder(unittest.TestCase):
    _text = ""

    def setUp(self) -> None:
        self._text = (
            "тестировали? тестировала тестировал testing, tested оно 2016 Pokémon   "
        )

    def test_builder(self) -> None:
        builder: TagsBuilder = TagsBuilder(r"[^\w\d ]")
        builder.build_tags(self._text)
        tags: dict[str, int] = builder.get_tags()
        expected: dict[str, int] = {"тестирова": 3, "test": 2, "он": 1, "2016": 1, "pokémon": 1}
        self.assertEqual(tags, expected)
        words: dict[str, set[str]] = builder.get_words()
        self.assertEqual(
            words,
            {
                "тестирова": set(["тестировали", "тестировала", "тестировал"]),
                "test": set(["testing", "tested"]),
                "он": set(["оно"]),
                "2016": set(["2016"]),
                "pokémon": set(["pokémon"]),
            },
        )
        builder.purge()
        tags = builder.get_tags()
        self.assertEqual(tags, {})
        words = builder.get_words()
        self.assertEqual(words, {})

    def test_build_tags_preserves_lemma_order_and_resets_state(self) -> None:
        builder: TagsBuilder = TagsBuilder()
        builder.build_tags(self._text)
        self.assertEqual(
            builder.get_prepared_text(),
            "тестирова тестирова тестирова test test он 2016 pokémon",
        )
        builder.purge()
        self.assertEqual(builder.get_prepared_text(), "")
        builder.build_tags("")
        self.assertEqual(builder.get_prepared_text(), "")
        self.assertEqual(builder.get_tags(), {})

    def test_text2words(self):
        builder: TagsBuilder = TagsBuilder(r"[^\w\d ]")
        words = [
            "тестировали",
            "тестировала",
            "тестировал",
            "testing",
            "tested",
            "оно",
            "2016",
            "pokémon",
        ]
        self.assertEqual(builder.text2words(self._text), words)

    def test_process_word(self):
        builder: TagsBuilder = TagsBuilder(r"[^\w\d ]")
        words = ["тестировали", "testing", "оно", "2016", "Pokémon"]
        expect = ["тестирова", "test", "он", "2016", "pokémon"]
        for i, word in enumerate(words):
            self.assertEqual(builder.process_word(word), expect[i])


if __name__ == "__main__":
    unittest.main()
