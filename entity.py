import gzip
from rsstag.utils import load_config
from rsstag.entity_extractor import EntityExtractor
from rsstag.html_cleaner import HTMLCleaner
from pymongo import MongoClient
from polyglot.text import Text

def ent_ex(db):
    ent_ex = EntityExtractor()
    cur = db.posts.find({})
    hc = HTMLCleaner()
    for post in cur:
        hc.purge()
        text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
        hc.feed(text)
        texts = hc.get_content()
        entities = ent_ex.extract_entities(' '.join(texts))
        if entities:
            print(entities)

def ent_ex_polyglot(db):
    cur = db.posts.find({})
    hc = HTMLCleaner()
    for post in cur:
        hc.purge()
        text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
        hc.feed(text)
        texts = hc.get_content()
        txt = Text(' '.join(texts))
        try:
            entities = txt.entities
            print(entities)
        except Exception as e:
            print('Exception: ', e)

if __name__ == '__main__':
    config = load_config('./rsscloud.conf')
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl.rss
    #ent_ex(db)
    ent_ex_polyglot(db)

