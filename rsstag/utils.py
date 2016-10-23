"""Utility functions"""
from typing import Optional
from configparser import ConfigParser
from _collections import OrderedDict

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
