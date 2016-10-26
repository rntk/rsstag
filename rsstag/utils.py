"""Utility functions"""
import os
from typing import Optional
from configparser import ConfigParser
from _collections import OrderedDict
from pymongo import MongoClient
import csv

def getSortedDictByAlphabet(dct, sort_type=None):
    """Sort dict"""
    if not sort_type or sort_type == 'k':
        sorted_keys = sorted(dct.keys())
    elif sort_type == 'c':
        sorted_keys = sorted(dct.keys(), key=lambda d: dct[d]['title'])
    temp_dct = dct
    sorted_dct = OrderedDict()
    for key in sorted_keys:
        sorted_dct[key] = temp_dct[key]
    return sorted_dct

def load_config(config_path: str) -> Optional[dict]:
    """Load and parse config file"""
    c = ConfigParser()
    c.read(config_path, encoding='utf-8')
    result = c

    return result

def geo_csv_to_base(db: MongoClient, csv_dir: str, lang: str='ru', delimiter: str=';', quote_char: str='"'):
    """
    Load geodata from csv files from https://github.com/x88/i18nGeoNamesDB in mondogb collections - "cities"
    """
    langs = ('ru', 'ua', 'be', 'en', 'es', 'pt', 'de', 'fr', 'it', 'pl', 'ja', 'lt', 'lv', 'cz')
    bulk_size = 500
    try:
        pos = langs.index(lang) + 1
    except:
        raise Exception('Not supported language: {}'.format(lang))
    f = open('{}{}_countries.csv'.format(os.path.abspath(csv_dir), os.sep), 'r')
    csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quote_char)
    countries = {}
    next(csv_reader)
    for row in csv_reader:
        countries[row[0]] = {
            'id': row[0],
            't': row[pos]
        }
    f.close()
    '''f = open('{}{}_regions.csv'.format(os.path.abspath(csv_dir), os.sep), 'r')
    csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quote_char)
    regions = {}
    pos = langs.index(lang) + 2
    next(csv_reader)
    for row in csv_reader:
        regions[row[0]] = {
            'id': row[0],
            'c_id': row[1],
            't': row[pos]
        }
    f.close()'''
    f = open('{}{}_cities.csv'.format(os.path.abspath(csv_dir), os.sep), 'r')
    csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quote_char)
    counter = 0
    inserts = []
    title_pos = langs.index(lang) + 4
    area_pos = title_pos + 1
    region_pos =title_pos + 2
    next(csv_reader)
    for row in csv_reader:
        if counter > bulk_size:
            db.cities.insert_many(inserts)
            inserts = []
            counter = 0
        inserts.append({
            'id': row[0],
            't': row[title_pos],
            'i': True if row[2] == 't' else False,
            'c': countries[row[1]],
            'a': row[area_pos],
            'r_id': row[3],
            'r_n': row[region_pos]
        })
        counter += 1
    if inserts:
        db.cities.insert_many(inserts)
    f.close()