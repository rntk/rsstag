import unittest
from html_cleaner import HTMLCleaner

class TestHTMLCleaner(unittest.TestCase):

    def test_cleaner(self):
        cleaner = HTMLCleaner()
        txt = 'test text'
        html = '<body><span>{}</span></body>'.format(txt)
        cleaner.feed(html)
        self.assertEqual(cleaner.get_content(), [txt])
        txt1 = 'test text1'
        html = '<body><span>{}<a href="#">{}</a></span></body>'.format(txt, txt1)
        cleaner.feed(html)
        self.assertEqual(cleaner.get_content(), [txt, txt, txt1])
        cleaner.purge();
        self.assertEqual(cleaner.get_content(), [])
        self.assertNotEqual(cleaner.get_content(), [txt, txt, txt1])


if __name__ == '__main__':
    unittest.main()
