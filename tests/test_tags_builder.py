import unittest
from tags_builder import TagsBuilder

class TestTagsBuilder(unittest.TestCase):

    def test_builder(self):
        builder = TagsBuilder('[^a-zA-Zа-яА-ЯёЁ0-9 ]')
        text = 'тестировали тестировала тестировал testing tested оно 2016'
        builder.build_tags(text)
        tags = builder.get_tags()
        expect_tags = ['тестировать', 'test', 'оно', '2016']
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
            '2016': set(['2016'])
        })
        builder.purge()
        tags = builder.get_tags()
        self.assertEqual(tags, [])
        words = builder.get_words()
        self.assertEqual(words, {})


if __name__ == '__main__':
    unittest.main()
