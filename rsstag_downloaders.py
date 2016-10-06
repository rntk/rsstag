'''RSSTag downloaders'''
import json
import time
import logging
from http import client
from typing import Tuple

class BazquxDownloader():
    '''rss downloder from bazqux.com'''
    def start(self, data: dict) -> Tuple[dict, str]:
        '''Worker download rss from bazqux.com'''
        try:
            logging.info('Start downloading, %s', data['category'])
        except Exception as e:
            logging.warning('Start downloading, category with strange symbols')
        counter_for_downloads = 0
        result = {'items': []}
        again = True
        url = data['url']
        while again:
            try:
                connection = client.HTTPSConnection(data['host'])
                connection.request('GET', url, '', data['headers'])
                resp = connection.getresponse()
                json_data = resp.read()
                tmp_result = {}
                if json_data:
                    tmp_result = json.loads(json_data.decode('utf-8'))
                else:
                    logging.error('json_data is empty - %s', json_data)
                if tmp_result:
                    if 'continuation' not in tmp_result:
                        again = False
                    else:
                        url = data['url'] + '&c={0}'.format(tmp_result['continuation'])
                    result['items'].extend(tmp_result['items'])
                else:
                    if counter_for_downloads == 5:
                        logging.error('enough downloading')
                        again = False
                    logging.error('tmp_result is empty - %s', tmp_result)
            except Exception as e:
                logging.error('%s: %s %s %s yoyoyo', e, data['category'], counter_for_downloads, url)
                if counter_for_downloads == 5:
                    again = False
                else:
                    counter_for_downloads += 1
                    time.sleep(2)
                result = None
                f = open('log/{0}'.format(data['category']), 'w')
                f.write(json_data.decode('utf-8'))
                f.close()
        try:
            logging.info('Downloaded, %s', data['category'])
        except Exception as e:
            logging.warning('Downloaded, category with strange symbols')

        return (result, data['category'])
