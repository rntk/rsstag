import gzip
from collections import defaultdict
from rsstag.utils import load_config
from rsstag.html_cleaner import HTMLCleaner
from rsstag.tags_builder import TagsBuilder
from pymongo import MongoClient
from nltk.corpus import stopwords

def rss2vw(db):
    clnr = HTMLCleaner()
    cur = db.posts.find({})
    bldr = TagsBuilder('[^\w\d ]')
    f = open('rss_features.txt', 'w')
    ft = open('rss_texts.txt', 'w')
    for post in cur:
        freqs = defaultdict(lambda: 0)
        clnr.purge()
        bldr.purge()
        text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
        bldr.prepare_text(text)
        text = bldr.get_prepared_text()
        ft.write('post_{} |rss:1 {}\n'.format(post['pid'], text))
        label = 'post_{}'.format(post['pid'])
        for word in text.split():
            freqs[word] += 1
        if freqs:
            features = ' '.join('{}:{}'.format(word, freq) for word, freq in freqs.items())
            vw_str = '{} |rss:1 {}\n'.format(label, features)
            f.write(vw_str)
    f.close()
    ft.close()

def rss2vw1(db):
    clnr = HTMLCleaner()
    cur = db.posts.find({})
    bldr = TagsBuilder('[^\w\d ]')
    f = open('rss_features.txt', 'w')
    ft = open('rss_texts.txt', 'w')
    stops = set(stopwords.words('english') + stopwords.words('russian'))
    for post in cur:
        """clnr.purge()
        bldr.purge()
        text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
        clnr.feed(text)
        text = ' '.join(clnr.get_content())
        bldr.prepare_text(text)
        text = bldr.get_prepared_text()
        ft.write('post_{0} post{0}|rss {1}\n'.format(post['pid'], text))"""
        features = ' '.join(tag for tag in post['tags'] if tag not in stops)
        vw_str = '{0} 1 0 \'post_{0}|rss {1}\n'.format(post['pid'], features)
        f.write(vw_str)
    f.close()
    ft.close()

if __name__ == '__main__':
    config = load_config('./rsscloud.conf')
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl.rss
    rss2vw1(db)

