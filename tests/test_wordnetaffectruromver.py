import unittest
from rsstag.sentiment import WordNetAffectRuRom
"""
TODO: pass tests without files (inject part of data in tests)
"""
class TestWordNet(unittest.TestCase):

    def setUp(self):
        self._dir = './data/wordnet/lilu.fcim.utm.md'

    def test_wna_en(self):
        wna = WordNetAffectRuRom('en', 4)
        wna.load_dicts_from_dir(self._dir)
        words_affects = {
            'avaricious': ['anger'],
            'envy': ['anger'],
            'horror': ['disgust', 'fear'],
            'disgust': ['disgust'],
            'afraid': ['fear'],
            'heartless': ['fear'],
            'sanctioned': ['joy'],
            'caring': ['joy'],
            'suffering': ['sadness'],
            'remorsefully': ['sadness'],
            'surprise': ['surprise'],
            'awe': ['surprise']
        }
        for word in words_affects:
            words_affects[word].sort()
            for_test = wna.get_affects_by_word(word)
            for_test.sort()
            self.assertEqual(words_affects[word], for_test, msg='Fail on word: {}'.format(word))

    def test_wna_ru(self):
        wna = WordNetAffectRuRom('ru')
        wna.load_dicts_from_dir(self._dir)
        words_affects = {
            'алчный': ['anger'],
            'ожесточённый': ['anger'],
            'отталкивать': ['disgust'],
            'отвратительный': ['disgust', 'fear', 'sadness'],
            'напуганный': ['fear'],
            'суровый': ['fear'],
            'гармоничный': ['joy'],
            'благоприятный': ['joy'],
            'мрачный': ['sadness', 'anger'],
            'горе': ['sadness'],
            'удивительно': ['surprise'],
            'изумление': ['surprise']
        }
        for word in words_affects:
            words_affects[word].sort()
            for_test = wna.get_affects_by_word(word)
            for_test.sort()
            self.assertEqual(words_affects[word], for_test, msg='Fail on word: {}'.format(word))

    def test_wna_rom(self):
        wna = WordNetAffectRuRom('rom')
        wna.load_dicts_from_dir(self._dir)
        words_affects = {
            'avar': ['anger'],
            'mînios': ['anger'],
            'dezgust': ['disgust'],
            'îngreţoşat': ['disgust'],
            'temător': ['fear'],
            'îngrozi': ['fear', 'surprise'],
            'recunoscut': ['joy'],
            'plăcere': ['joy'],
            'vinovat': ['sadness'],
            'melancolic': ['sadness'],
            'minunare': ['surprise'],
            'surprinzător': ['surprise']
        }
        for word in words_affects:
            words_affects[word].sort()
            for_test = wna.get_affects_by_word(word)
            for_test.sort()
            self.assertEqual(words_affects[word], for_test, msg='Fail on word: {}'.format(word))

    def test_add_word(self):
        wna = WordNetAffectRuRom('en', 2)
        wna._add_word_in_index('envy', 'id_1')
        expect = {
            'en': {
                '_': set(['id_1']),
                'vy': {
                    '_': set(['id_1'])
                }
            }
        }
        self.assertEqual(wna._search_index, expect)
        wna._add_word_in_index('angry', 'id_2')
        expect['an'] = {
            '_': set(['id_2']),
            'gr': {
                '_': set(['id_2']),
                'y': {
                    '_': set(['id_2']),
                }
            }
        }
        self.assertEqual(wna._search_index, expect)

    def test_search(self):
        wna = WordNetAffectRuRom('en', 2)
        data = [
            "v#01221816	cause to feel resentment or indignation	 pique offend	уязвлять задевать раздражать распалять	atinge leza	A cauza indignare sau resentiment",
            "v#01229968	treat cruelly	 torment rag tantalize bedevil crucify dun frustrate	мучить издеваться досаждать донимать допекать изводить терзать изнурять	chinui tortura	A produce sau a îndura suferinţe fizice sau morale intense.",
            "v#01231478	be in a huff; be silent or sullen	sulk grizzle brood stew	дуться сердиться тяготиться томиться	se_îmbufna fierbe",
            "v#01239708	give displeasure to	 displease	раздражать	nemulţumi	A produce cuiva o nemulţumire.",
            "v#01242326	exasperate or irritate	 exacerbate exasperate aggravate	возмущать раздражать сердить озлоблять изводить бесить отягчать усугублять ухудшать обострять	exacerba exaspera agrava",
            "v#01246666	be envious of; set one's heart on	envy begrudge	завидовать	invidia pizmui	A fi stăpânit de invidie faţă de cineva, a privi cu invidie pe cineva sau reuşita, bunăstarea, calităţile altuia",
            "v#01246798	wish, long, or crave for something, especially the property of another person 	covet	жаждать домогаться	râvni rîvni invidia	a dori, a râvni, a pofti ceva ce aparţine ",
            "v#01246968	feel envious towards; admire enviously 	envy	завидовать	invidia",
            "v#01762305	cause to suffer	 persecute oppress harass	донимать преследовать надоедать допекать подавлять притеснять угнетать беспокоить волновать изводить тревожить утомлять изнурять	hărţui sâcâi sîcîi persecuta urmări oprima subjuga împila apăsa strivi",
            "v#01857366	be in a huff and display one's displeasure	sulk pout brood	раздражаться обижаться оскорбляться дуться	se_îmbufna se_busumfla mârâi mîrîi bodogăni	A fi morocănos, supărat şi a arăta acest lucru."
        ]
        affect = 'anger'
        wna.build_vocab(affect, data)
        self.assertEqual(wna.search_affects_by_word(wna._ids_key), [])
        self.assertEqual(wna.search_affects_by_word('envy'), [affect])
        self.assertEqual(wna.search_affects_by_word('brood'), [affect])
        self.assertEqual(wna.search_affects_by_word('har'), [affect])
        self.assertEqual(wna.search_affects_by_word('joy'), [])

if __name__ == '__main__':
    unittest.main()
