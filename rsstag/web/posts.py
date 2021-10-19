import json
import html
import gzip
import logging
from collections import defaultdict
from urllib.parse import unquote_plus, unquote

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication
from rsstag.tasks import TASK_MARK, TASK_NOT_IN_PROCESSING

from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import NotFound
from werkzeug.utils import redirect


def on_post_speech(app: "RSSTagApplication", request: Request) -> Response:
    try:
        post_id = int(request.form.get('post_id'))
    except Exception as e:
        post_id = None
    code = 200
    if post_id:
        post = app.posts.get_by_pid(g.user['sid'], post_id)
        if post:
            title = html.unescape(post['content']['title'])
            speech_file = app.getSpeech(title)
            if speech_file:
                result = {'data': '/static/speech/{}'.format(speech_file)}
            else:
                result = {'error': 'Can`t get speech file'}
                code = 503
        else:
            result = {'error': 'Post not found'}
            code = 404
    else:
        result = {'error': 'No post id'}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)

def on_category_get(app: "RSSTagApplication", user: dict, request: Request, quoted_category: str) -> Response:
    cat = unquote_plus(quoted_category)
    db_feeds = app.feeds.get_by_category(user['sid'], cat)
    by_feed = {}
    for f in db_feeds:
        by_feed[f['feed_id']] = f

    if not by_feed:
        return app.on_error(user, request, NotFound())

    projection = {'_id': False, 'content.content': False}
    if user['settings']['only_unread']:
        only_unread = user['settings']['only_unread']
    else:
        only_unread = None
    if cat != app.feeds.all_feeds:
        db_posts_c = app.posts.get_by_category(user['sid'], only_unread, cat, projection)
    else:
        db_posts_c = app.posts.get_all(user['sid'], only_unread, projection)

    db_posts = list(db_posts_c)

    if user['settings']['similar_posts']:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(user['sid'], list(clusters), only_unread, projection)
        for post in cl_posts:
            if post['feed_id'] not in by_feed:
                feed = app.feeds.get_by_feed_id(user['sid'], post['feed_id'])
                if feed:
                    by_feed[post['feed_id']] = feed
        db_posts.extend(cl_posts)
    posts = []
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode('utf-8', 'replace')
        if post['pid'] not in pids:
            pids.add(post['pid'])
            if post['feed_id'] in by_feed:
                posts.append({
                    'post': post,
                    'pos': post['pid'],
                    'category_title': by_feed[post['feed_id']]['category_title'],
                    'feed_title': by_feed[post['feed_id']]['title'],
                    'favicon': by_feed[post['feed_id']]['favicon']
                })
    page = app.template_env.get_template('posts.html')

    return Response(
        page.render(
            posts=posts,
            tag=cat,
            group='category',
            words=[],
            user_settings=user['settings'],
            provider=user['provider']
        ),
        mimetype='text/html'
    )

def on_tag_get(app: "RSSTagApplication", user: dict, request: Request, quoted_tag: str) -> Response:
    tag = unquote(quoted_tag)
    current_tag = app.tags.get_by_tag(user['sid'], tag)
    if not current_tag:
        return app.on_error(user, request, NotFound())

    projection = {'_id': False, 'content.content': False}
    if user['settings']['only_unread']:
        only_unread = user['settings']['only_unread']
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_tags(user['sid'], [tag], only_unread, projection)
    db_posts = list(db_posts_c)

    if user['settings']['similar_posts']:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(user['sid'], list(clusters), only_unread, projection)
        db_posts.extend(cl_posts)
    posts = []
    by_feed = {}
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode('utf-8', 'replace')
        if post['pid'] not in pids:
            pids.add(post['pid'])
            if post['feed_id'] not in by_feed:
                feed = app.feeds.get_by_feed_id(user['sid'], post['feed_id'])
                if feed:
                    by_feed[post['feed_id']] = feed
            if post['feed_id']in by_feed:
                posts.append({
                    'post': post,
                    'pos': post['pid'],
                    'category_title': by_feed[post['feed_id']]['category_title'],
                    'feed_title': by_feed[post['feed_id']]['title'],
                    'favicon': by_feed[post['feed_id']]['favicon']
                })
    page = app.template_env.get_template('posts.html')

    return Response(
        page.render(
            posts=posts,
            tag=tag,
            group='tag',
            words=current_tag['words'],
            user_settings=user['settings'],
            provider=user['provider']
        ),
        mimetype='text/html'
    )

def on_bi_gram_get(app: "RSSTagApplication", user: dict, request: Request, bi_gram: str) -> Response:
    current_bi_gram = app.bi_grams.get_by_bi_gram(user['sid'], bi_gram)
    if not current_bi_gram:
        return app.on_error(user, request, NotFound())

    projection = {'_id': False, 'content.content': False}
    if user['settings']['only_unread']:
        only_unread = user['settings']['only_unread']
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_bi_grams(user['sid'], [bi_gram], only_unread, projection)
    db_posts = list(db_posts_c)

    if user['settings']['similar_posts']:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(user['sid'], list(clusters), only_unread, projection)
        db_posts.extend(cl_posts)
    posts = []
    by_feed = {}
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode('utf-8', 'replace')
        if post['pid'] not in pids:
            pids.add(post['pid'])
            if post['feed_id'] not in by_feed:
                feed = app.feeds.get_by_feed_id(user['sid'], post['feed_id'])
                if feed:
                    by_feed[post['feed_id']] = feed
            if post['feed_id'] in by_feed:
                posts.append({
                    'post': post,
                    'pos': post['pid'],
                    'category_title': by_feed[post['feed_id']]['category_title'],
                    'feed_title': by_feed[post['feed_id']]['title'],
                    'favicon': by_feed[post['feed_id']]['favicon']
                })
    page = app.template_env.get_template('posts.html')

    return Response(
        page.render(
            posts=posts,
            tag=bi_gram,
            group='tag',
            words=current_bi_gram['words'],
            user_settings=user['settings'],
            provider=user['provider']
        ),
        mimetype='text/html'
    )

def on_feed_get(app: "RSSTagApplication", user: dict, request: Request, quoted_feed: str) -> Response:
    feed = unquote_plus(quoted_feed)
    current_feed = app.feeds.get_by_feed_id(user['sid'], feed)
    if not current_feed:
        return app.on_error(user, request, NotFound())

    projection = {'_id': False, 'content.content': False}
    if user['settings']['only_unread']:
        only_unread = user['settings']['only_unread']
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_feed_id(
        user['sid'],
        current_feed['feed_id'],
        only_unread,
        projection
    )
    db_posts = list(db_posts_c)

    posts = []
    if user['settings']['similar_posts']:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(user['sid'], list(clusters), only_unread, projection)
        db_posts.extend(cl_posts)
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode('utf-8', 'replace')
        if post['pid'] not in pids:
            pids.add(post['pid'])
            posts.append({
                'post': post,
                'category_title': current_feed['category_title'],
                'pos': post['pid'],
                'feed_title': current_feed['title'],
                'favicon': current_feed['favicon']
            })
    page = app.template_env.get_template('posts.html')

    return Response(
        page.render(
            posts=posts,
            tag=current_feed['title'],
            group='feed',
            words=[],
            user_settings=user['settings'],
            provider=user['provider']
        ),
        mimetype='text/html'
    )

def on_read_posts_post(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    try:
        data = json.loads(request.get_data(as_text=True))
        if data['ids'] and isinstance(data['ids'], list):
            post_ids = data['ids']
        else:
            raise Exception('Bad ids for posts status')
        readed = bool(data['readed'])
    except Exception as e:
        logging.warning('Send wrond data for read posts. Cause: %s', e)
        post_ids = None
        result = {'error': 'Bad ids or status'}
        code = 400

    if post_ids:
        tags = defaultdict(int)
        bi_grams = defaultdict(int)
        letters = defaultdict(int)
        for_insert = []
        db_posts = app.posts.get_by_pids(
            user['sid'],
            post_ids,
            {'id': True, 'tags': True, 'bi_grams': True, 'read': True}
        )
        for d in db_posts:
            if d['read'] != readed:
                for_insert.append({
                    'user': user['sid'],
                    'id': d['id'],
                    'status': readed,
                    'processing': TASK_NOT_IN_PROCESSING,
                    'type': TASK_MARK,
                })
                for t in d['tags']:
                    tags[t] += 1
                    if not t:
                        continue
                    letters[t[0]] += 1
                for bi_g in d['bi_grams']:
                    bi_grams[bi_g] += 1

        if app.tasks.add_task({'type': TASK_MARK, 'user': user['sid'], 'data': for_insert}):
            changed = app.posts.change_status(user['sid'], post_ids, readed)
            if changed and tags:
                changed = app.tags.change_unread(user['sid'], tags, readed)
            if changed and bi_grams:
                changed = app.bi_grams.change_unread(user['sid'], bi_grams, readed)
            if changed and letters:
                app.letters.change_unread(user['sid'], letters, readed)
                changed = True
            if changed:
                code = 200
                result = {'data': 'ok'}
            else:
                code = 500
                result = {'error': 'Database error'}

    return Response(
        json.dumps(result),
        mimetype="application/json",
        status=code
    )

def on_posts_content_post(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    try:
        wanted_posts = json.loads(request.get_data(as_text=True))
        if not (isinstance(wanted_posts, list) and wanted_posts):
            raise Exception('Empty list of ids for post content')
    except Exception as e:
        logging.warning('Send bad posts ids for posts content. Cause: %s', e)
        wanted_posts = []
        result = {'error': 'Bad posts ids'}
        code = 400

    if wanted_posts:
        projection = {
            'pid': True,
            'content': True,
            'attachments': True
        }
        posts = app.posts.get_by_pids(user['sid'], wanted_posts, projection)
        posts_content = []
        for post in posts:
            attachments = ''
            if post['attachments']:
                for href in post['attachments']:
                    attachments += '<a href="{0}">{0}</a><br />'.format(href)
            content = gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
            if attachments:
                content += '<p>Attachments:<br />{0}<p>'.format(attachments)
            posts_content.append({'pos': post['pid'], 'content': content})

        if posts_content:
            result = {'data': posts_content}
            code = 200
        else:
            code = 404
            result = {'error': 'Not found'}

    return Response(
        json.dumps(result),
        mimetype="application/json",
        status=code
    )

def on_post_links_get(app: "RSSTagApplication", user: dict, post_id: int) -> Response:
    projection = {
        'tags': True,
        'feed_id': True,
        'url': True,
        'clusters': True
    }
    current_post = app.posts.get_by_pid(user['sid'], post_id, projection)
    if current_post:
        feed = app.feeds.get_by_feed_id(user['sid'], current_post['feed_id'])
        if feed:
            code = 200
            result = {
                'data': {
                    'c_url': feed['category_local_url'],
                    'c_title': feed['category_title'],
                    'f_url': feed['local_url'],
                    'f_title': feed['title'],
                    'p_url': current_post['url'],
                    "ctx_url": app.routes.getUrlByEndpoint(
                        endpoint='on_posts_get',
                        params={"pids": post_id, "context": int(user["settings"]["context_n"])}
                    ),
                    'tags': []
                }
            }
            if "clusters" in current_post:
                result["data"]["clst_url"] = app.routes.getUrlByEndpoint(
                    endpoint='on_cluster_get',
                    params={"cluster": current_post["clusters"][0]}
                )
            for t in current_post['tags']:
                result['data']['tags'].append({
                    'url': app.routes.getUrlByEndpoint(endpoint='on_get_tag_page', params={'tag': t}),
                    'tag': t
                })
        else:
            code = 500
            result = {'error': 'Server trouble'}
    else:
        code = 404
        result = {'error': 'Not found'}

    return Response(
        json.dumps(result),
        mimetype="application/json",
        status=code
    )

#TODO: delete or change or something other
def on_get_posts_with_tags(app: "RSSTagApplication", user: dict, s_tags: str) -> Response:
    if not s_tags:
        return redirect(app.routes.getUrlByEndpoint('on_root_get'))

    tags = s_tags.split('-')
    if tags:
        result = {}
        query = {'owner': user['sid'], 'tag': {'$in': tags}}
        tags_cursor = app.db.tags.find(query, {'_id': 0, 'tag': 1, 'words': 1})
        for tag in tags_cursor:
            result[tag['tag']] = {'words': ', '.join(tag['words']), 'posts': []}

        query = {'owner': user['sid'], 'tags': {'$in': tags}}
        if user['settings']['only_unread']:
            query['read'] = False
        posts_cursor = app.db.posts.find(query, {'content.content': 0})
        feeds = {}
        posts = {}
        for post in posts_cursor:
            posts[post['id']] = post
            if post['feed_id'] not in feeds:
                feeds[post['feed_id']] = {}
        feeds_cursor = app.db.feeds.find({'owner': user['sid'], 'feed_id': {'$in': list(feeds.keys())}})
        for feed in feeds_cursor:
            feeds[feed['feed_id']] = feed
        for tag in tags:
            posts_for_delete = []
            for p_id in posts:
                if tag in posts[p_id]['tags']:
                    posts[p_id]['feed_title'] = feeds[posts[p_id]['feed_id']]['title']
                    posts[p_id]['category_title'] = feeds[posts[p_id]['feed_id']]['category_title']
                    result[tag]['posts'].append(posts[p_id])
                    posts_for_delete.append(p_id)
            for p_id in posts_for_delete:
                del posts[p_id]
            result[tag]['posts'] = sorted(result[tag]['posts'], key=lambda p: p['feed_id'])
        page = app.template_env.get_template('tags-posts.html')

        return Response(
            page.render(
                tags=result,
                selected_tags=','.join(tags),
                group='tag',
                user_settings=user['settings'],
                provider=user['provider']
            ),
            mimetype='text/html'
        )

def on_entity_get(app: "RSSTagApplication", user: dict, quoted_tag: str) -> Response:
    tag = unquote(quoted_tag)
    projection = {'_id': False, 'content.content': False}
    if user['settings']['only_unread']:
        only_unread = user['settings']['only_unread']
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_tags(user['sid'], tag.split(), only_unread, projection)
    db_posts = list(db_posts_c)

    if user['settings']['similar_posts']:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(user['sid'], list(clusters), only_unread, projection)
        db_posts.extend(cl_posts)
    posts = []
    by_feed = {}
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode('utf-8', 'replace')
        if post['pid'] not in pids:
            pids.add(post['pid'])
            if post['feed_id'] not in by_feed:
                feed = app.feeds.get_by_feed_id(user['sid'], post['feed_id'])
                if feed:
                    by_feed[post['feed_id']] = feed
            if post['feed_id']in by_feed:
                posts.append({
                    'post': post,
                    'pos': post['pid'],
                    'category_title': by_feed[post['feed_id']]['category_title'],
                    'feed_title': by_feed[post['feed_id']]['title'],
                    'favicon': by_feed[post['feed_id']]['favicon']
                })
    tags_cur = app.tags.get_by_tags(user["sid"], tag.split(), only_unread=only_unread)
    words = set()
    for tg in tags_cur:
        words.update(tg["words"])

    page = app.template_env.get_template('posts.html')

    return Response(
        page.render(
            posts=posts,
            tag=tag,
            group='tag',
            words=list(words),
            user_settings=user['settings'],
            provider=user['provider']
        ),
        mimetype='text/html'
    )

def on_posts_get(app: "RSSTagApplication", user: dict, request: Request, pids: str) -> Response:
    context_n = 0
    ctx_n = None
    if "context" in request.args:
        ctx_n = request.args["context"]
    if ctx_n:
        context_n = int(ctx_n)
    projection = {'_id': False, 'content.content': False}
    if user['settings']['only_unread']:
        only_unread = user['settings']['only_unread']
    else:
        only_unread = None
    pids_i = [int(p) for p in pids.split("_")]
    c_pids = set()
    if context_n > 0:
        only_unread = None
        for pid_i in pids_i:
            for i in range(context_n):
                i += 1
                pd = pid_i - i
                if pd >= 0:
                    c_pids.add(pd)
                c_pids.add(pid_i + i)
    if c_pids:
        pids_i.extend(c_pids)

    db_posts_c = app.posts.get_by_pids(user['sid'], pids_i, projection)
    db_posts = list(db_posts_c)

    if user['settings']['similar_posts']:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(user['sid'], list(clusters), only_unread, projection)
        db_posts.extend(cl_posts)
    posts = []
    by_feed = {}
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode('utf-8', 'replace')
        if post['pid'] not in pids:
            pids.add(post['pid'])
            if post['feed_id'] not in by_feed:
                feed = app.feeds.get_by_feed_id(user['sid'], post['feed_id'])
                if feed:
                    by_feed[post['feed_id']] = feed
            if post['feed_id'] in by_feed:
                posts.append({
                    'post': post,
                    'pos': post['pid'],
                    'category_title': by_feed[post['feed_id']]['category_title'],
                    'feed_title': by_feed[post['feed_id']]['title'],
                    'favicon': by_feed[post['feed_id']]['favicon']
                })
    page = app.template_env.get_template('posts.html')
    if context_n:
        posts.sort(key=lambda p: p["pos"], reverse=True)

    return Response(
        page.render(
            posts=posts,
            tag="NoTag",
            group='tag',
            words=[],
            user_settings=user['settings'],
            provider=user['provider']
        ),
        mimetype='text/html'
    )

def on_cluster_get(app: "RSSTagApplication", user: dict, cluster: int) -> Response:
    projection = {'_id': False, 'content.content': False}
    if user['settings']['only_unread']:
        only_unread = user['settings']['only_unread']
    else:
        only_unread = None
    db_posts = app.posts.get_by_clusters(user['sid'], [cluster], only_unread, projection)

    posts = []
    by_feed = {}
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode('utf-8', 'replace')
        if post['pid'] not in pids:
            pids.add(post['pid'])
            if post['feed_id'] not in by_feed:
                feed = app.feeds.get_by_feed_id(user['sid'], post['feed_id'])
                if feed:
                    by_feed[post['feed_id']] = feed
            if post['feed_id'] in by_feed:
                posts.append({
                    'post': post,
                    'pos': post['pid'],
                    'category_title': by_feed[post['feed_id']]['category_title'],
                    'feed_title': by_feed[post['feed_id']]['title'],
                    'favicon': by_feed[post['feed_id']]['favicon']
                })
    page = app.template_env.get_template('posts.html')

    return Response(
        page.render(
            posts=posts,
            tag="NoTag",
            group='tag',
            words=[],
            user_settings=user['settings'],
            provider=user['provider']
        ),
        mimetype='text/html'
    )
