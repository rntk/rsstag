import sys
from rsstag.w2v import W2VLearn

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    learn = W2VLearn(config_path)
    learn.fetch_texts()
    learn.learn()
