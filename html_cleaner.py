'''Remove all html tags'''
from html.parser import HTMLParser

class HTMLCleaner(HTMLParser):
    '''Remove all html tags'''
    _strings = []
    _error = None

    def handle_data(self, data):
        '''Add data to strings'''
        self._strings.append(data)

    def purge(self):
        '''Clear state'''
        self._strings = []

    def get_content(self):
        '''Get clean content'''
        return self._strings

    def error(self, error):
        '''Save last error'''
        self._error = error
