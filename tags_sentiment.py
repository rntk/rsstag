import logging
from rsstag.utils import load_config
from rsstag.sentiment import RuSentiLex
from pymongo import MongoClient

def make_tags_sentiment(db) -> int:
    ru_sent = RuSentiLex('./data/rusentilex.txt')
    all_tags = db.tags.find({}, {'tag': True})
    i = 0
    for tag in all_tags:
        sentiment = ru_sent.sentiment_by_lemma(tag['tag'])
        if sentiment:
            i += 1
            sentiment = sorted(sentiment)
            db.tags.update_many({'tag': tag['tag']}, {'$set': {'sentiment': sentiment}})

    return i

if __name__ == '__main__':
    config = load_config('./rsscloud.conf')
    logging.basicConfig(
        filename=config['settings']['log_file'],
        filemode='a',
        level=getattr(logging, config['settings']['log_level'].upper())
    )
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl.rss
    logging.info('Sentiment was found for %s tags', make_tags_sentiment(db))
