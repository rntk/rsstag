import sys
from rsstag.workers import RSSTagWorker

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    worker = RSSTagWorker(config_path)
    worker.start()
