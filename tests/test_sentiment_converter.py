import unittest
from rsstag.sentiment import SentimentConverter

class TestSentimentConverter(unittest.TestCase):

    def test_convert_sentiment(self):
        conv = SentimentConverter()
        test_data = [
            [['anger'], ['negative']],
            [['disgust'], ['negative']],
            [['fear'], ['negative']],
            [['joy'], ['positive']],
            [['sadness'], ['negative']],
            [['surprise'], ['positive']],
            [['ang'], []],
            [['anger', 'joy'], ['negative', 'positive']],
        ]
        for sents, sents_exp in test_data:
            print(sents, sents_exp)
            conv_sents = sorted(conv.convert_sentiment(sents))
            self.assertEqual(sorted(sents_exp), conv_sents)

if __name__ == '__main__':
    unittest.main()
