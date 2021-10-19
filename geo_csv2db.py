from rsstag.utils import load_config
from rsstag.geo_catalog import RssTagGeoCatalog
import sys
import logging
from pymongo import MongoClient

if __name__ == "__main__":
    config = load_config("./rsscloud.conf")
    logging.basicConfig(
        filename=config["settings"]["log_file"],
        filemode="a",
        level=getattr(logging, config["settings"]["log_level"].upper()),
    )
    cl = MongoClient(config["settings"]["db_host"], int(config["settings"]["db_port"]))
    db = cl.rss
    geo_catalog = RssTagGeoCatalog(db)
    if len(sys.argv) > 1:
        lang = sys.argv[1]
    else:
        langs = geo_catalog.get_languages()
        lang = langs[0]
    geo_catalog.purge()
    logging.info("Start geo data loading")
    geo_catalog.load_countries_csv_to_base("./csv/_countries.csv", lang=lang)
    geo_catalog.load_regions_csv_to_base("./csv/_regions.csv", lang=lang)
    geo_catalog.load_cities_csv_to_base("./csv/_cities.csv", lang=lang)
    geo_catalog.ensure_indexes()
    logging.info("End geo data loading")
