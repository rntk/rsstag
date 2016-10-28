"""Utility functions"""
import os
from typing import Optional, Tuple
from configparser import ConfigParser
from _collections import OrderedDict
from pymongo import MongoClient
from http.client import HTTPSConnection
import json
import csv
from urllib.parse import quote
from html import unescape

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

def get_coords_yandex(country:str, city: str='', lang: str='ru_RU', key: str='', raw: bool=False) -> list:
    host = 'geocode-maps.yandex.ru'
    con = HTTPSConnection(host)
    req = country
    if city:
        req += ',+{}'.format(city)
    req_url = '/1.x/?format=json&lang=' + lang
    if key:
        req_url += '&key=' + key
    req_url += '&geocode=' + quote(req)
    con.request('GET', req_url)
    resp = con.getresponse()
    if (resp.status == 200):
        raw_json = resp.read()
        if raw:
            result = json.loads(raw_json.decode('utf-8'))
        else:
            data = json.loads(raw_json.decode('utf-8'))
            if len(data['response']['GeoObjectCollection']['featureMember']) > 0:
                result = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos'].split()
            else:
                raise Exception('Not found. Country {}. City {}'.format(country, city))
    else:
        raise Exception('HTTP status {}'.format(resp.status, resp.reason))

    return result