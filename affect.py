import os
import gzip
from rsstag.utils import load_config
from pymongo import MongoClient
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from rsstag.WordNetAffectRuRomVer2 import WordNetAffectRuRomVer2

class TagAffects:
    def __init__(self, config_path: str) -> None:
        self.dir = './data/'
        self._config = load_config(config_path)
        cl = MongoClient(self._config['settings']['db_host'], int(self._config['settings']['db_port']))
        self.db = cl.rss

    def fetch_texts(self) -> None:
        cursor = self.db.posts.find({})
        builder = TagsBuilder(self._config['settings']['replacement'])
        cleaner = HTMLCleaner()
        for post in cursor:
            text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
            cleaner.purge()
            cleaner.feed(text)
            strings = cleaner.get_content()
            text = ' '.join(strings)
            builder.purge()
            builder.prepare_text(text)
            text = builder.get_prepared_text()
            if text:
                self.make_topics(text, post['pid'])

    def make_affects(self):
        f_name = self.dir + 'affects.txt'
        wn_en = WordNetAffectRuRomVer2('en', 4)
        wn_en.load_dicts_from_dir('./wna')
        wn_ru = WordNetAffectRuRomVer2('ru', 4)
        wn_ru.load_dicts_from_dir('./wna')
        cur = self.db.tags.find({})
        f = open(f_name, 'w')
        for tag in cur:
            affects = wn_en.get_affects_by_word(tag['tag'])
            if not affects:
                affects = wn_en.search_affects_by_word(tag['tag'])
            if not affects:
                affects = wn_ru.get_affects_by_word(tag['tag'])
            if not affects:
                affects = wn_ru.search_affects_by_word(tag['tag'])
            if affects:
                f.write('{} - {}\n'.format(tag['tag'], affects))
        f.close()

if __name__ == '__main__':
    ta = TagAffects('rsscloud.conf')
    ta.make_affects()
