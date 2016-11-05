"""Utility functions"""
from typing import Optional, List
from configparser import ConfigParser
from collections import OrderedDict, defaultdict
from http.client import HTTPSConnection
import json
from hashlib import md5
from urllib.parse import quote

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

def to_dot_format(tags: List[dict], posts: List[dict]) -> str:
    all_tags = defaultdict(lambda: set())
    for post in posts:
        for tag in post['tags']:
            tag = md5(tag.encode('utf-8')).hexdigest()
            if tag[0].isnumeric():
                tag = '_' + tag
            for t in post['tags']:
                t = md5(t.encode('utf-8')).hexdigest()
                if t[0].isnumeric():
                    t = '_' + t
                all_tags[tag].add(t)
    subgraphs = []
    i = 0
    for tag, edges in all_tags.items():
        edges.remove(tag)
        subgraphs.append('{} -- {{{}}}'.format(tag, ' '.join(edges)))
        i += 1

    result = 'all_tags {{ {} }}'.format(';'.join(subgraphs))
    return result
    #return 'graph dinetwork {1 -- 2 [color=red]; subgraph {2 -- 3; 3 -- 4; 4 -- {1 2}}}'

