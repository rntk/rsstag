import sys
from rsstag.d2v import D2VLearn

if __name__ == "__main__":
    config_path = "rsscloud.conf"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    learn = D2VLearn(config_path)
    learn.fetch_texts()
    learn.learn()
