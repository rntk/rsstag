"""Remove all html tags"""

from html.parser import HTMLParser
from html import unescape


class HTMLCleaner(HTMLParser):
    """Remove all html tags"""

    SKIP_TAGS = {'style', 'script'}

    def __init__(self):
        super().__init__()
        self._strings = []
        self._error = None
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip = True

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self._skip = False

    def handle_data(self, data):
        """Add data to strings"""
        if self._skip:
            return
        repeat = True
        while repeat:
            txt = unescape(data)
            if data == txt:
                repeat = False
            data = txt

        self._strings.append(data)

    def purge(self):
        """Clear state"""
        self._strings = []
        self._skip = False

    def get_content(self):
        """Get clean content"""
        return self._strings

    def error(self, error):
        """Save last error"""
        self._error = error
