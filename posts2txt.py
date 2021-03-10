import sys
import gzip
from typing import List
from rsstag.utils import load_config
from pymongo import MongoClient


def fetch_texts(db: MongoClient, ignore_stopwords: bool=False) -> List[str]:
    cursor = db.posts.find({})
    texts = []
    for post in cursor:
        text = gzip.decompress(post["lemmas"]).decode('utf-8', 'replace')
        texts.append(text)

    return texts

if __name__ == '__main__':
    config_path = './rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    config = load_config(config_path)
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl[config['settings']['db_name']]
    texts = fetch_texts(db)
    f = open('all_posts.txt', 'w')
    f.write('\n'.join(texts))
    f.close()