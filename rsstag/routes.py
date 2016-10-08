'''Routes for rsstag'''
from typing import List, Optional
from werkzeug.routing import Map, Rule

class RSSTagRoutes:
    '''Routes list and mapping for rsstag'''
    def __init__(self, host: str) -> None:
        self._host = host
        self._routes = [
            {'url': '/', 'endpoint': 'on_root_get', 'methods': ['GET', 'HEAD']},
            {'url': '/login', 'endpoint': 'on_login_get', 'methods': ['GET', 'HEAD']},
            {'url': '/login', 'endpoint': 'on_login_post', 'methods': ['POST']},
            {'url': '/provider', 'endpoint': 'on_select_provider_get', 'methods': ['GET', 'HEAD']},
            {'url': '/provider', 'endpoint': 'on_select_provider_post', 'methods': ['POST']},
            {'url': '/group/tag/<int:page_number>', 'endpoint': 'on_group_by_tags_get', 'methods': ['GET', 'HEAD']},
            {
                'url': '/group/tag/startwith/<string(length: 1):letter>',
                'endpoint': 'on_group_by_tags_startwith_get',
                'methods': ['GET', 'HEAD']
            },
            {'url': '/group/category', 'endpoint': 'on_group_by_category_get', 'methods': ['GET', 'HEAD']},
            {'url': '/refresh', 'endpoint': 'on_refresh_get_post', 'methods': ['GET', 'HEAD', 'POST']},

            {'url': '/tag/<string:quoted_tag>', 'endpoint': 'on_tag_get', 'methods': ['GET', 'HEAD']},
            {'url': '/category/<string:quoted_category>', 'endpoint': 'on_category_get', 'methods': ['GET', 'HEAD']},
            {'url': '/feed/<string:quoted_feed>', 'endpoint': 'on_feed_get', 'methods': ['GET', 'HEAD']},
            {'url': '/read/posts', 'endpoint': 'on_read_posts_post', 'methods': ['POST']},
            {'url': '/posts-content', 'endpoint': 'on_posts_content_post', 'methods': ['POST']},
            {'url': '/post-content', 'endpoint': 'on_post_content_post', 'methods': ['POST']},
            {'url': '/post-links', 'endpoint': 'on_post_links', 'methods': ['POST']},
            {'url': '/ready', 'endpoint': 'on_ready_get', 'methods': ['GET', 'HEAD']},
            {'url': '/settings', 'endpoint': 'on_settings_post', 'methods': ['POST']},
            {'url': '/all-tags', 'endpoint': 'on_get_all_tags', 'methods': ['GET', 'HEAD']},
            {
                'url': '/posts/with/tags/<string:s_tags>',
                'endpoint': 'on_get_posts_with_tags',
                'methods': ['GET', 'HEAD']
            },
            {'url': '/tag-siblings/<string:tag>', 'endpoint': 'on_get_tag_siblings', 'methods': ['GET', 'HEAD']},
            {'url': '/tags-search', 'endpoint': 'on_post_tags_search', 'methods': ['POST']},
            {'url': '/speech', 'endpoint': 'on_post_speech', 'methods': ['POST']}
        ]

        self._rules = []
        for route in self._routes:
            self._rules.append(Rule(route['url'], endpoint=route['endpoint'], methods=route['methods']))
        self._werkzeug_routes = Map(self._rules)

    def get_routes(self) -> List[dict]:
        '''Get routes list'''
        return self._routes

    def get_werkzeug_routes(self) -> object:
        '''Get werkzeug generated routes'''
        return self._werkzeug_routes;

    '''def getUrlByEndpoint(self, endpoint=None, params=None, full_url=False):
        url = None
        if endpoint:
            if not params:
                params = {}
            if full_url or params:
                all_urls = self.routes.bind(self.request.environ['HTTP_HOST'], '/')
                url = all_urls.build(endpoint, params, force_external=full_url)
            else:
                url = next(self.routes.iter_rules(endpoint=endpoint))
        return url'''

    def getUrlByEndpoint(self, endpoint: str, params: dict = None, full_url: bool = False) -> Optional[str]:
        '''Return url by endpoint'''
        url = None
        if endpoint:
            url = next(self._werkzeug_routes.iter_rules(endpoint=endpoint))
            if params:
                all_urls = self._werkzeug_routes.bind(self._host, '/')
                url = all_urls.build(endpoint, params, force_external=full_url)

        return url

    def bind_to_environ(self, environ: dict):
        return self._werkzeug_routes.bind_to_environ(environ)