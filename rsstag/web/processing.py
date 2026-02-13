import logging
from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect


def on_processing_get(app, user: dict, request: Request) -> Response:
    posts = list(app.posts.get_processing(user["sid"]))
    tags = list(app.tags.get_processing(user["sid"]))
    
    page = app.template_env.get_template("processing.html")
    return Response(
        page.render(
            posts=posts,
            tags=tags,
            user_settings=user["settings"],
            provider=user["provider"],
            support=app.config["settings"]["support"],
            version=app.config["settings"]["version"],
        ),
        mimetype="text/html",
    )


def on_processing_reset_post(app, user: dict, request: Request) -> Response:
    item_type = request.form.get("type")
    item_id = request.form.get("id")
    
    if item_type == "post":
        app.posts.reset_processing(user["sid"], item_id)
    elif item_type == "tag":
        app.tags.reset_processing(user["sid"], item_id)
    
    return redirect("/processing")
