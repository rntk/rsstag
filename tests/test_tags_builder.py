import unittest
from rsstag.tags_builder import TagsBuilder

class TestTagsBuilder(unittest.TestCase):

    def test_builder(self):
        builder = TagsBuilder('[^\w\d ]')
        text = 'тестировали тестировала тестировал testing tested оно 2016 Pokémon'
        builder.build_tags(text)
        tags = builder.get_tags()
        expect_tags = ['тестировать', 'test', 'оно', '2016', 'pokémon']
        self.assertEqual(tags.sort(), expect_tags.sort())
        words = builder.get_words()
        self.assertEqual(words, {
            'тестировать': set(
                ['тестировали', 'тестировала', 'тестировал']
            ),
            'test': set(
                ['testing', 'tested']
            ),
            'оно': set(['оно']),
            '2016': set(['2016']),
            'pokémon': set(['pokémon'])
        })
        builder.purge()
        tags = builder.get_tags()
        self.assertEqual(tags, [])
        words = builder.get_words()
        self.assertEqual(words, {})

    def test_text2words(self):
        builder = TagsBuilder('[^\w\d ]')
        text = 'тестировали? тестировала тестировал testing, tested оно 2016 Pokémon   '
        words = ['тестировали', 'тестировала', 'тестировал', 'testing', 'tested', 'оно', '2016', 'pokémon']
        self.assertEqual(builder.text2words(text), words)

    def test_process_word(self):
        builder = TagsBuilder('[^\w\d ]')
        words = ['тестировали', 'testing', 'оно', '2016', 'Pokémon']
        expect = ['тестировать', 'test', 'оно', '2016', 'pokémon']
        for i, word in enumerate(words):
            self.assertEqual(builder.process_word(word), expect[i])

    def test_build_bi_grams(self):
        builder = TagsBuilder('[^\w\d ]')
        text = 'тестировали тестировала тестировал testing tested оно 2016 Pokémon'
        builder.build_bi_grams(text)
        tags = builder.get_bi_grams()
        expect_tags = {
            'тестировать тестировать': set(['тестировать', 'тестировать']),
            'тестировать test': set(['тестировать', 'test']),
            'test test': set(['test', 'test']),
            'test оно': set(['test', 'оно']),
            'оно 2016': set(['оно', '2016']),
            '2016 pokémon': set(['2016', 'pokémon'])
        }
        self.assertEqual(tags, expect_tags)
        words = builder.get_bi_grams_words()
        self.assertEqual(words, {
            'тестировать тестировать': set(['тестировали', 'тестировала', 'тестировал']),
            'тестировать test': set(['тестировал', 'testing']),
            'test test': set(['testing', 'tested']),
            'test оно': set(['tested', 'оно']),
            'оно 2016': set(['оно', '2016']),
            '2016 pokémon': set(['2016', 'pokémon'])
        })
        builder.purge()
        tags = builder.get_bi_grams()
        self.assertEqual(tags, {})
        words = builder.get_bi_grams_words()
        self.assertEqual(words, {})
if __name__ == '__main__':
    unittest.main()
