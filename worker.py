import sys
from rsstag.workers import RSSTagWorkerDispatcher

if __name__ == "__main__":
    config_path = "rsscloud.conf"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    worker = RSSTagWorkerDispatcher(config_path)
    worker.start()
