import unittest
from rsstag.sentiment import RuSentiLex

class TestRuSentiLex(unittest.TestCase):
    def test_sentiment_by_lemma(self):
        strings = [
            'абортивный, Adj, абортивный, negative, fact',
            'административное воздействие, NG, административный воздействие, negative, fact',
            'атака, Noun, атака, negative, fact, "АТАКА, ВОЕННЫЙ УДАР"',
            'атака, Noun, атака, positive, fact, "АТАКА (ИГРОВОЕ ДЕЙСТВИЕ)"',
            'взволнованность, Noun, взволнованность, positive/negative, feeling',
            'балдеть, Verb, балдеть/балдей, positive, opinion'
        ]
        ru_sent = RuSentiLex(strings)
        sent = ru_sent.get_sentiment('абортивный')
        self.assertEqual(['negative'], sent)

        sent = ru_sent.get_sentiment('административный воздействие')
        self.assertEqual(['negative'], sent)

        sent = ru_sent.get_sentiment('атака')
        sent_exp = sorted(['negative', 'positive'])
        sent = sorted(sent)
        self.assertEqual(sent_exp, sent)

        sent = ru_sent.get_sentiment('взволнованность')
        self.assertEqual(['positive/negative'], sent)

        sent = ru_sent.get_sentiment('балдеть')
        self.assertEqual(['positive'], sent)

        sent = ru_sent.get_sentiment('балдей')
        self.assertEqual(['positive'], sent)

if __name__ == '__main__':
    unittest.main()
