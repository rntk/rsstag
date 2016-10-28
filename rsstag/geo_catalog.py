from typing import Optional
import logging
from html import unescape
import csv
import os
from pymongo import MongoClient

class RssTagGeoCatalog:
    def __init__(self, db: MongoClient) -> None:
        self.db = db
        self.log = logging.getLogger('geo_catalog')
        self.langs = ('ru', 'ua', 'be', 'en', 'es', 'pt', 'de', 'fr', 'it', 'pl', 'ja', 'lt', 'lv', 'cz')
        self.bulk_size = 500

    def load_countries_csv_to_base(self, csv_path: str, lang: str = 'ru', delimiter: str = ';', quote_char: str = '"'):
        """
        Load countries from csv files from https://github.com/x88/i18nGeoNamesDB
        """
        self.log.info('Start countries loading')
        try:
            pos = self.langs.index(lang) + 1
        except:
            raise Exception('Not supported language: {}'.format(lang))
        f = open(os.path.abspath(csv_path), 'r')
        csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quote_char)
        collection = self.db.countries
        counter = 0
        inserts = []
        next(csv_reader)
        was_inserted = 0
        rows_number = 0
        for row in csv_reader:
            rows_number += 1
            if counter > self.bulk_size:
                res = collection.insert_many(inserts)
                was_inserted += len(res.inserted_ids)
                inserts = []
                counter = 0
            inserts.append({
                'id': row[0].strip(),
                't': unescape(row[pos].strip())
            })
            counter += 1
        f.close()
        if inserts:
            res = collection.insert_many(inserts)
            was_inserted += len(res.inserted_ids)
        self.log.info('Countries - %s. Saved - %s', rows_number, was_inserted)

    def load_regions_csv_to_base(self, csv_path: str, lang: str = 'ru', delimiter: str = ';', quote_char: str = '"'):
        """
        Load regions from csv files from https://github.com/x88/i18nGeoNamesDB
        """
        self.log.info('Start regions loading')
        try:
            pos = self.langs.index(lang) + 2
        except:
            raise Exception('Not supported language: {}'.format(lang))
        f = open(os.path.abspath(csv_path), 'r')
        csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quote_char)
        collection = self.db.regions
        counter = 0
        inserts = []
        next(csv_reader)
        was_inserted = 0
        rows_number = 0
        for row in csv_reader:
            rows_number += 1
            if counter > self.bulk_size:
                res = collection.insert_many(inserts)
                was_inserted += len(res.inserted_ids)
                inserts = []
                counter = 0
            inserts.append({
                'id': row[0].strip(),
                'c_id': row[1].strip(),
                't': unescape(row[pos].strip())
            })
            counter += 1
        f.close()
        if inserts:
            res = collection.insert_many(inserts)
            was_inserted += len(res.inserted_ids)
            self.log.info('Regions - %s. Saved - %s', rows_number, was_inserted)

    def load_cities_csv_to_base(self, csv_path: str, lang: str = 'ru', delimiter: str = ';', quote_char: str = '"'):
        """
        Load cities from csv files from https://github.com/x88/i18nGeoNamesDB
        """
        self.log.info('Start cities loading')
        try:
            title_pos = self.langs.index(lang) + 4
            area_pos = title_pos + 1
            region_pos = title_pos + 2
        except:
            raise Exception('Not supported language: {}'.format(lang))
        f = open(os.path.abspath(csv_path), 'r')
        csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quote_char)
        collection = self.db.cities
        counter = 0
        inserts = []
        next(csv_reader)
        was_inserted = 0
        rows_number = 0
        for row in csv_reader:
            rows_number += 1
            if counter > self.bulk_size:
                res = collection.insert_many(inserts)
                was_inserted += len(res.inserted_ids)
                inserts = []
                counter = 0
            inserts.append({
                'id': row[0].strip(),
                't': unescape(row[title_pos].strip()),
                'i': True if row[2].strip() == 't' else False,
                'a': unescape(row[area_pos].strip()),
                'r_id': row[3].strip(),
                'r_n': unescape(row[region_pos].strip())
            })
            counter += 1
        f.close()
        if inserts:
            res = collection.insert_many(inserts)
            was_inserted += len(res.inserted_ids)
        self.log.info('Cities - %s. Saved - %s', rows_number, was_inserted)

    '''def get_country(self, country_name: str) -> Optional[list]:
        try:
            result = self.db.cities.find_one({
                'c.t': country_name.capitalize()
            })
        except Exception as e:
            result = None
            self.log.error('Can`t get country info for %s. Info: %s', country_name, e)

        return result


    def get_city(self, country_name: str) -> Optional[list]:
        try:
            city = self.db.cities.find_one({
                'c.t': country_name.capitalize()
            })
            result = city['c']
        except Exception as e:
            result = None
            self.log.error('Can`t get country info for %s. Info: %s', country_name, e)

        return result'''
