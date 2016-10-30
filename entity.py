import gzip
from rsstag.utils import load_config
from rsstag.entity_extractor import EntityExtractor
from pymongo import MongoClient

if __name__ == '__main__':
    config = load_config('./rsscloud.conf')
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl.rss
    ent_ex = EntityExtractor()
    cur = db.posts.find({})
    for post in cur:
        text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
        entities = ent_ex.extract_entities(text)
        if entities:
            print(entities)
