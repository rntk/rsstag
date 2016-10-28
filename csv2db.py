from rsstag.utils import load_config
from rsstag.geo_catalog import RssTagGeoCatalog
import logging
from pymongo import MongoClient

if __name__ == '__main__':
    config = load_config('./rsscloud.conf')
    logging.basicConfig(
        filename=config['settings']['log_file'],
        filemode='a',
        level=getattr(logging, config['settings']['log_level'].upper())
    )
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl.rss
    geo_catalog = RssTagGeoCatalog(db)
    logging.info('Start geo data loading')
    geo_catalog.load_countries_csv_to_base('./csv/_countries.csv')
    geo_catalog.load_regions_csv_to_base('./csv/_regions.csv')
    geo_catalog.load_cities_csv_to_base('./csv/_cities.csv')
    logging.info('End geo data loading')
