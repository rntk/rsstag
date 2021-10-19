from typing import Optional, Tuple
import logging
from html import unescape
import csv
import os
from pymongo import MongoClient


class RssTagGeoCatalog:
    """
    Work with rsstag geodata collections
    """

    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger("geo_catalog")
        self._langs = (
            "ru",
            "ua",
            "be",
            "en",
            "es",
            "pt",
            "de",
            "fr",
            "it",
            "pl",
            "ja",
            "lt",
            "lv",
            "cz",
        )
        self._bulk_size = 500
        self._collections = ("countries", "regions", "cities")

    def get_languages(self) -> Tuple:
        return self._langs

    def purge(self) -> None:
        """
        Drop all collections with geodata
        """
        for coll_name in self._collections:
            self._db.drop_collection(coll_name)

    def ensure_indexes(self) -> None:
        """
        Create indexes for collection
        """
        indexes = ["t", "id"]
        for coll_name in self._collections:
            for indx in indexes:
                try:
                    self._db[coll_name].create_index(indx)
                except Exception as e:
                    self._log.warning(
                        'Can`t create index "%s" on "%s". May be alredy exists. Info: e',
                        coll_name,
                        indx,
                        e,
                    )

    def load_countries_csv_to_base(
        self,
        csv_path: str,
        lang: str = "ru",
        delimiter: str = ";",
        quote_char: str = '"',
    ):
        """
        Load countries from csv files from https://github.com/x88/i18nGeoNamesDB
        """
        self._log.info("Start countries loading")
        try:
            pos = self._langs.index(lang) + 1
        except:
            raise Exception("Not supported language: {}".format(lang))
        f = open(os.path.abspath(csv_path), "r")
        csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quote_char)
        collection = self._db.countries
        counter = 0
        inserts = []
        next(csv_reader)
        was_inserted = 0
        rows_number = 0
        for row in csv_reader:
            rows_number += 1
            if counter > self._bulk_size:
                res = collection.insert_many(inserts)
                was_inserted += len(res.inserted_ids)
                inserts = []
                counter = 0
            inserts.append(
                {"id": row[0].strip(), "t": unescape(row[pos].strip()), "l": lang}
            )
            counter += 1
        f.close()
        if inserts:
            res = collection.insert_many(inserts)
            was_inserted += len(res.inserted_ids)
        self._log.info("Countries - %s. Saved - %s", rows_number, was_inserted)

    def load_regions_csv_to_base(
        self,
        csv_path: str,
        lang: str = "ru",
        delimiter: str = ";",
        quote_char: str = '"',
    ):
        """
        Load regions from csv files from https://github.com/x88/i18nGeoNamesDB
        """
        self._log.info("Start regions loading")
        try:
            pos = self._langs.index(lang) + 2
        except:
            raise Exception("Not supported language: {}".format(lang))
        f = open(os.path.abspath(csv_path), "r")
        csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quote_char)
        collection = self._db.regions
        counter = 0
        inserts = []
        next(csv_reader)
        was_inserted = 0
        rows_number = 0
        for row in csv_reader:
            rows_number += 1
            if counter > self._bulk_size:
                res = collection.insert_many(inserts)
                was_inserted += len(res.inserted_ids)
                inserts = []
                counter = 0
            inserts.append(
                {
                    "id": row[0].strip(),
                    "c_id": row[1].strip(),
                    "t": unescape(row[pos].strip()),
                    "l": lang,
                }
            )
            counter += 1
        f.close()
        if inserts:
            res = collection.insert_many(inserts)
            was_inserted += len(res.inserted_ids)
            self._log.info("Regions - %s. Saved - %s", rows_number, was_inserted)

    def load_cities_csv_to_base(
        self,
        csv_path: str,
        lang: str = "ru",
        delimiter: str = ";",
        quote_char: str = '"',
    ):
        """
        Load cities from csv files from https://github.com/x88/i18nGeoNamesDB
        """
        self._log.info("Start cities loading")
        try:
            title_pos = self._langs.index(lang) + 4
            area_pos = title_pos + 1
            region_pos = title_pos + 2
        except:
            raise Exception("Not supported language: {}".format(lang))
        f = open(os.path.abspath(csv_path), "r")
        csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quote_char)
        collection = self._db.cities
        counter = 0
        inserts = []
        next(csv_reader)
        was_inserted = 0
        rows_number = 0
        for row in csv_reader:
            rows_number += 1
            if counter > self._bulk_size:
                res = collection.insert_many(inserts)
                was_inserted += len(res.inserted_ids)
                inserts = []
                counter = 0
            inserts.append(
                {
                    "id": row[0].strip(),
                    "t": unescape(row[title_pos].strip()),
                    "i": True if row[2].strip() == "t" else False,
                    "a": unescape(row[area_pos].strip()),
                    "c_id": row[1].strip(),
                    "r_id": row[3].strip(),
                    "r_n": unescape(row[region_pos].strip()),
                    "l": lang,
                }
            )
            counter += 1
        f.close()
        if inserts:
            res = collection.insert_many(inserts)
            was_inserted += len(res.inserted_ids)
        self._log.info("Cities - %s. Saved - %s", rows_number, was_inserted)

    def get_country_by_name(self, country_name: str) -> Optional[dict]:
        try:
            result = self._db.countries.find_one({"t": country_name.capitalize()})
            if result is None:
                result = {}
        except Exception as e:
            result = None
            self._log.error(
                "Can`t get country info by name %s. Info: %s", country_name, e
            )

        return result

    def get_country_by_id(self, country_id: str) -> Optional[dict]:
        try:
            result = self._db.countries.find_one({"id": country_id})
            if result is None:
                result = {}
        except Exception as e:
            result = None
            self._log.error("Can`t get country info  by id %s. Info: %s", country_id, e)

        return result

    def get_city_by_name(
        self, city_name: str, important: Optional[bool] = None
    ) -> Optional[list]:
        query = {"t": city_name.capitalize()}
        if important is not None:
            query["i"] = important
        try:
            cur = self._db.cities.aggregate(
                [
                    {"$match": query},
                    {
                        "$lookup": {
                            "from": "countries",
                            "localField": "c_id",
                            "foreignField": "id",
                            "as": "c",
                        }
                    },
                ]
            )
            result = list(cur)
        except Exception as e:
            result = None
            self._log.error("Can`t get country info for %s. Info: %s", city_name, e)

        return result
