from rsstag.web.app import RSSTagApplication

config_path = 'rsscloud.conf'
app = RSSTagApplication(config_path)
print('out appl', __name__)

def application(env, start_response):
    print('in appl', __name__)
    return app.setResponse(env, start_response)

