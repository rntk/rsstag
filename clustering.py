import sys
import gzip
from collections import defaultdict
from typing import List
from rsstag.utils import load_config
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from rsstag.posts import RssTagPosts
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from pymongo import MongoClient

def get_texts(all_posts: List[dict], config) -> None:
    texts_for_vec = []
    post_pids = []
    if all_posts:
        builder = TagsBuilder(config['settings']['replacement'])
        cleaner = HTMLCleaner()
        for post in all_posts:
            post_pids.append(post['pid'])
            text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'ignore')
            cleaner.purge()
            cleaner.feed(text)
            strings = cleaner.get_content()
            text = ' '.join(strings)
            builder.purge()
            builder.prepare_text(text, ignore_stopwords=True)
            texts_for_vec.append(builder.get_prepared_text())

    return (texts_for_vec, post_pids)

def get_dbscan_clusters(texts: List[str], post_pids: List[int], skip_noise: bool=True) -> dict:
    vectorizer = TfidfVectorizer()
    dbs = DBSCAN(eps=0.9, min_samples=2, n_jobs=1)
    dbs.fit(vectorizer.fit_transform(texts))
    clusters = defaultdict(set)
    for i, cluster in enumerate(dbs.labels_):
        clusters[int(cluster)].add(post_pids[i])

    if skip_noise and clusters and -1 in clusters:
        del clusters[-1]

    return clusters

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    config = load_config(config_path)
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl[config['settings']['db_name']]
    posts = RssTagPosts(db)
    user = db.users.find_one({})
    all_posts = posts.get_all(user['sid'], projection={'content': True, 'pid': True})
    #texts, post_pids = get_texts(all_posts, config)
    f = open('all_posts.txt', 'r', encoding='utf-8')
    texts = f.read().splitlines()
    post_pids = list(range(len(texts)))
    print('Text fetched: ', len(all_posts))
    clusters = get_dbscan_clusters(texts, post_pids)
    print('Clustered: ', len(clusters))
    posts.set_clusters(user['sid'], clusters)
