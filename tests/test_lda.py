import unittest
from rsstag.lda import LDA


class TestLDA(unittest.TestCase):
    def test_empty_texts_raises(self):
        lda = LDA()
        with self.assertRaises(ValueError):
            lda.topics([])

    def test_single_text(self):
        lda = LDA()
        result = lda.topics(["hello world test example"], topics_n=2, top_k=3)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_multiple_texts(self):
        lda = LDA()
        texts = [
            "machine learning is amazing",
            "deep learning neural networks",
            "natural language processing",
        ]
        result = lda.topics(texts, topics_n=2, top_k=3)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_topics_count(self):
        lda = LDA()
        texts = ["hello world test example foo bar"] * 10
        result = lda.topics(texts, topics_n=3, top_k=5)
        # Should return at most topics_n * top_k unique words
        self.assertLessEqual(len(result), 15)

    def test_russian_text(self):
        lda = LDA()
        texts = [
            "машинное обучение это интересно",
            "глубокое обучение нейронные сети",
        ]
        result = lda.topics(texts, topics_n=2, top_k=3)
        self.assertIsInstance(result, list)

    def test_all_stopwords_raises(self):
        lda = LDA()
        texts = ["the and is in to of a that it"] * 5
        with self.assertRaises(ValueError):
            lda.topics(texts, topics_n=1, top_k=3)


if __name__ == "__main__":
    unittest.main()
