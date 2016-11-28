import sys
import gzip
from typing import List
from rsstag.utils import load_config
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from pymongo import MongoClient


def fetch_texts(db: MongoClient, config: dict, ignore_stopwords: bool=False) -> List[str]:
    cursor = db.posts.find({})
    builder = TagsBuilder(config['settings']['replacement'])
    cleaner = HTMLCleaner()
    texts = []
    for post in cursor:
        text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
        cleaner.purge()
        cleaner.feed(text)
        strings = cleaner.get_content()
        text = ' '.join(strings)
        builder.purge()
        builder.prepare_text(text, ignore_stopwords=ignore_stopwords)
        texts.append(builder.get_prepared_text())

    return texts

if __name__ == '__main__':
    config_path = './rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    config = load_config(config_path)
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl[config['settings']['db_name']]
    texts = fetch_texts(db, config)
    f = open('all_posts.txt', 'w')
    f.write('\n'.join(texts))
    f.close()