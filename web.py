import sys
import logging
from werkzeug.serving import run_simple
from rsstag.web.app import RSSTagApplication

try:
    from rsstag.observability import init_observability
    from rsstag.observability.web_middleware import make_otel_wsgi_middleware
except ImportError:
    init_observability = lambda *a, **kw: None  # noqa: E731
    make_otel_wsgi_middleware = lambda app, *a, **kw: app  # noqa: E731

if __name__ == "__main__":
    init_observability("rsstag-web")
    config_path = "rsscloud.conf"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    app = RSSTagApplication(config_path)
    if app:
        static_files = {"/static": "static", "/favicon.ico": "static/favicon.ico"}
        wsgi_app = make_otel_wsgi_middleware(app.set_response, app.routes.get_werkzeug_routes())
        try:
            run_simple(
                app.config["settings"]["host"],
                int(app.config["settings"]["port"]),
                wsgi_app,
                static_files=static_files,
                threaded=True,
            )
        except Exception as e:
            logging.error(e)
            app.close()
    else:
        logging.critical("Can`t start server")
