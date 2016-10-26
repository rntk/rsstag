import sys
import logging
from werkzeug.serving import run_simple
from rsstag.web import RSSTagApplication

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    app = RSSTagApplication(config_path)
    if app:
        static_files = {
            '/static': 'static',
            '/favicon.ico': 'static/favicon.ico'
        }
        try:
            run_simple(
                app.config['settings']['host'],
                int(app.config['settings']['port']),
                app.setResponse,
                static_files=static_files,
                threaded=True
            )
        except Exception as e:
            logging.error(e)
            app.close()
    else:
        logging.critical('Can`t start server')
