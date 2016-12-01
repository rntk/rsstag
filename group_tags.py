import sys
from collections import defaultdict
from rsstag.w2v import W2VLearn
from rsstag.utils import load_config
from rsstag.tags import RssTagTags
from pymongo import MongoClient

def make_groups(db, config):
    learn = W2VLearn(db, config)
    koef = 0.6
    top_n = 10
    groups = learn.make_groups(top_n, koef)
    tag_groups = defaultdict(list)
    for group, tags in groups.items():
        if len(tags) > 3:
            for tag in tags:
                tag_groups[tag].append(group)
    if tag_groups:
        tags_h = RssTagTags(db)
        user = db.users.find_one({})
        tags_h.add_groups(user['sid'], tag_groups)

    #reduced = learn.reduce_groups(groups, top_n, koef) TODO: debug

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    config = load_config(config_path)
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl[config['settings']['db_name']]
    make_groups(db, config)

    '''f = open('gr.txt', 'w')
    for key, value in groups.items():
        if len(value) > 3:
            f.write('{} - {}\n'.format(key, value))
    f.close()'''
