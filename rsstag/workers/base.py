"""Shared worker helpers."""

from rsstag.stopwords import stopwords


class BaseWorker:
    def __init__(self, db, config):
        self._db = db
        self._config = config
        self._stopw = set(stopwords.words("english") + stopwords.words("russian"))
