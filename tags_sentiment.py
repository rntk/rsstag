import logging
from rsstag.utils import load_config
from rsstag.sentiment import RuSentiLex, WordNetAffectRuRom, SentimentConverter
from pymongo import MongoClient

def make_tags_sentiment(db) -> int:
    f = open('./data/rusentilex.txt', 'r', encoding='utf-8')
    strings = f.read().splitlines()
    ru_sent = RuSentiLex()
    wrong = ru_sent.sentiment_validation(strings, ',', '!')
    i = 0
    if not wrong:
        ru_sent.load(strings, ',', '!')
        all_tags = db.tags.find({}, {'tag': True})
        wna_dir = './data/wordnet/lilu.fcim.utm.md'
        wn_en = WordNetAffectRuRom('en', 4)
        wn_en.load_dicts_from_dir(wna_dir)
        wn_ru = WordNetAffectRuRom('ru', 4)
        wn_ru.load_dicts_from_dir(wna_dir)
        conv = SentimentConverter()
        for tag in all_tags:
            sentiment = ru_sent.get_sentiment(tag['tag'])
            if not sentiment:
                affects = wn_en.get_affects_by_word(tag['tag'])
                '''if not affects:
                    affects = wn_en.search_affects_by_word(tag['tag'])'''
                if not affects:
                    affects = wn_ru.get_affects_by_word(tag['tag'])
                '''if not affects:
                    affects = wn_ru.search_affects_by_word(tag['tag'])'''
                if affects:
                    sentiment = conv.convert_sentiment(affects)

            if sentiment:
                i += 1
                sentiment = sorted(sentiment)
                db.tags.update_many({'tag': tag['tag']}, {'$set': {'sentiment': sentiment}})

    return (i, wrong)

if __name__ == '__main__':
    config = load_config('./rsscloud.conf')
    logging.basicConfig(
        filename=config['settings']['log_file'],
        filemode='a',
        level=getattr(logging, config['settings']['log_level'].upper())
    )
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl.rss
    i, wrong = make_tags_sentiment(db)
    logging.info('Sentiment was found for %s tags.\nWrong: \n%s', i, '\n'.join(wrong))
