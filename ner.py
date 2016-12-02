import sys
import os
import gzip
from typing import List
from collections import defaultdict
from multiprocessing import Pool
from rsstag.utils import load_config
from rsstag.posts import RssTagPosts
from rsstag.html_cleaner import HTMLCleaner
from rsstag.entity_extractor import RssTagEntityExtractor
from rsstag.tags import RssTagTags
from pymongo import MongoClient
from polyglot.text import Text

def get_entities_polyglot(pid_text: str) -> list:
    try:
        txt = Text(pid_text[1])
        entities = [list(entity) for entity in txt.entities]
    except:
        entities = []

    return (pid_text[0], entities)

def all_by_rsstag(texts: List[str]) -> List[list]:
    ent_ex = RssTagEntityExtractor()
    all_entities = []
    for i, text in enumerate(texts):
        entities = ent_ex.extract_entities(text)
        all_entities.append(entities)

    all_entities = ent_ex.treat_entities(all_entities)

    return all_entities

def get_texts(db: MongoClient, owner: str, config: dict) -> List[str]:
    posts = RssTagPosts(db)
    all_posts = posts.get_all(owner, projection={'content': True, 'pid': True})
    pids = []
    texts = []
    if all_posts:
        clnr = HTMLCleaner()
        for post in all_posts:
            pids.append(post['pid'])
            text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'ignore')
            clnr.purge()
            clnr.feed(text)
            text = ' '.join(clnr.get_content())
            '''cleaner.purge()
            cleaner.feed(text)
            strings = cleaner.get_content()
            text = ' '.join(strings)
            builder.purge()
            builder.prepare_text(text, ignore_stopwords=True)'''
            texts.append(text)

    return (pids, texts)

def all_by_polyglot(pids: List[int], texts: List[str]) -> list:
    pool = Pool(os.cpu_count())
    all_entities = []
    for entities in pool.imap(get_entities_polyglot, zip(pids, texts)):
        if entities:
            all_entities.append(entities)

    return all_entities

def count_entities_rsstag(all_entities: List[list]) -> dict:
    result = defaultdict(int)
    for entities in all_entities:
        for entity in entities:
            for word in entity:
                if len(word) > 1:
                    result[word] += 1

    return result

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    config = load_config(config_path)
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl[config['settings']['db_name']]
    user = db.users.find_one({})
    pids, texts = get_texts(db, user['sid'], config)
    '''f = open('all_posts.txt', 'r')
    texts = f.read().splitlines()
    pids = list(range(len(texts)))'''

    #all_entities = all_by_polyglot(pids, texts)

    all_entities = all_by_rsstag(pids, texts)
    count_ent = count_entities_rsstag(all_entities)
    tags = RssTagTags(db)
    tags.add_entities(user['sid'], count_ent, replace=True)
    '''f = open('ent0.txt', 'w')
    f.write('\n'.join('{} {}'.format(pid, '{}'.format(entities)) for pid, entities in all_entities))
    f.close()'''