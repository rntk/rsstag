import sys
from rsstag.utils import load_config
from rsstag.w2v import W2VLearn
from pymongo import MongoClient

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    config = load_config(config_path)
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl[config['settings']['db_name']]
    learn = W2VLearn(db, config)
    learn.fetch_texts()
    learn.learn()
