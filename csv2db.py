from rsstag.utils import load_config, geo_csv_to_base
from pymongo import MongoClient

if __name__ == '__main__':
    config = load_config('./rsscloud.conf')
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl.rss
    geo_csv_to_base(db, './csv')
