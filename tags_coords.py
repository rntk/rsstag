import logging
from rsstag.utils import get_coords_yandex, load_config
from rsstag.tags import RssTagTags
from rsstag.geo_catalog import RssTagGeoCatalog
from pymongo import MongoClient


def make_tags_geo(db: MongoClient, key: str):
    tags = RssTagTags(db)
    users_cur = db.users.find({})
    langs_map = {"ru": "ru_RU", "en": "en_US"}
    for user in users_cur:
        owner = user["sid"]
        tags_cities = tags.get_city_tags(owner)
        if tags_cities:
            tag_coord = []
            for tag in tags_cities:
                try:
                    tag_coord = get_coords_yandex(
                        tag["city"]["c"]["t"],
                        tag["city"]["t"],
                        key=key,
                        lang=langs_map[tag["city"]["l"]],
                    )
                    if tag_coord and len(tag_coord) > 1:
                        db.tags.update_one(
                            {"tag": tag["tag"], "owner": owner},
                            {"$set": {"city.co": tag_coord}},
                        )
                    else:
                        logging.error(
                            "Wrong city %s coords. User: %s. Info: %s",
                            tag["tag"],
                            owner,
                            tag_coord,
                        )
                except Exception as e:
                    logging.error(
                        "Can`t get coords for city %s. User: %s. Coords %s. Info: %s",
                        tag["tag"],
                        owner,
                        tag_coord,
                        e,
                    )
        else:
            logging.error(
                "Cities coords not maked. User: %s. Cities: %s", owner, tags_cities
            )

        del tags_cities
        tags_countries = tags.get_country_tags(owner)
        if tags_countries:
            tag_coord = []
            for tag in tags_countries:
                try:
                    tag_coord = get_coords_yandex(
                        tag["country"]["t"],
                        key=key,
                        lang=langs_map[tag["country"]["l"]],
                    )
                    if tag_coord and len(tag_coord) > 1:
                        db.tags.update_one(
                            {"tag": tag["tag"], "owner": owner},
                            {"$set": {"country.co": tag_coord}},
                        )
                    else:
                        logging.error(
                            "Wrong country %s coords. User: %s. Info: %s",
                            tag["tag"],
                            owner,
                            tag_coord,
                        )
                except Exception as e:
                    logging.error(
                        "Can`t get coords for country %s. User: %s. Info: %s",
                        tag["tag"],
                        owner,
                        e,
                    )
        else:
            logging.error(
                "Country coords not maked. User: %s. Cities: %s", owner, tags_cities
            )


def match_tag_to_geo(db: MongoClient):
    geo_cat = RssTagGeoCatalog(db)
    for tag in db.tags.find({}):
        tag_name = tag["tag"].capitalize()
        country = geo_cat.get_country_by_name(tag_name)
        geo_info = {}
        geo_type = ""
        countries_number = 0
        cities_number = 0
        if country:
            del country["_id"]
            geo_info = country
            geo_type = "country"
            countries_number += 1
        else:
            city = geo_cat.get_city_by_name(tag_name, important=True)
            if city:
                city = city[0]
                del city["_id"]
                if ("c" in city) and city["c"]:
                    city["c"] = city["c"][0]
                    if "_id" in city["c"]:
                        del city["c"]["_id"]
                geo_info = city
                geo_type = "city"
                cities_number += 1
        if geo_info:
            try:
                db.tags.update_one(
                    {"tag": tag["tag"], "owner": tag["owner"]},
                    {"$set": {geo_type: geo_info}},
                )
            except Exception as e:
                logging.error(
                    "Can`t update geo info for tag %s. User: %s. Info: %s",
                    tag["tag"],
                    tag["owner"],
                    e,
                )
    logging.info(
        "Was found %s countries and %s cities", countries_number, cities_number
    )


if __name__ == "__main__":
    config = load_config("./rsscloud.conf")
    logging.basicConfig(
        filename=config["settings"]["log_file"],
        filemode="a",
        level=getattr(logging, config["settings"]["log_level"].upper()),
    )
    cl = MongoClient(config["settings"]["db_host"], int(config["settings"]["db_port"]))
    db = cl[config["settings"]["db_name"]]
    match_tag_to_geo(db)
    make_tags_geo(db, config["yandex"]["geocode_key"])
