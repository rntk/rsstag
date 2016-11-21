import unittest
from rsstag.wordnet import WordNetLabinform

class TestWordNetLabinform(unittest.TestCase):

    def test_get_hypernyms(self):
        lab = WordNetLabinform('./data/wordnet/labinform.ru')
        hypernyms = lab.get_hypernyms('бамбуковый')
        hyps_expect = ['бамбук']
        self.assertEqual(hyps_expect, hypernyms)



if __name__ == '__main__':
    unittest.main()
