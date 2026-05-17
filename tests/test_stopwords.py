import unittest
from rsstag.stopwords import Stopwords, stopwords


class TestStopwords(unittest.TestCase):
    def test_russian_stopwords(self):
        words = stopwords.words("russian")
        self.assertIn("и", words)
        self.assertIn("в", words)
        self.assertIn("не", words)
        self.assertIn("что", words)

    def test_english_stopwords(self):
        words = stopwords.words("english")
        self.assertIn("the", words)
        self.assertIn("and", words)
        self.assertIn("is", words)
        self.assertIn("in", words)

    def test_invalid_language_raises(self):
        with self.assertRaises(ValueError) as ctx:
            stopwords.words("french")
        self.assertIn("french", str(ctx.exception))

    def test_stopwords_is_singleton(self):
        s1 = Stopwords()
        s2 = Stopwords()
        self.assertEqual(s1.words("russian"), s2.words("russian"))

    def test_russian_stopwords_count(self):
        words = stopwords.words("russian")
        self.assertEqual(len(words), 49)

    def test_english_stopwords_count(self):
        words = stopwords.words("english")
        self.assertEqual(len(words), 31)


if __name__ == "__main__":
    unittest.main()
