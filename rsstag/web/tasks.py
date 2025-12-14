import logging
from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect
from rsstag.tasks import (
    TASK_DOWNLOAD,
    TASK_MARK,
    TASK_TAGS,
    TASK_WORDS,
    TASK_LETTERS,
    TASK_NER,
    TASK_CLUSTERING,
    TASK_W2V,
    TASK_D2V,
    TASK_TAGS_SENTIMENT,
    TASK_TAGS_GROUP,
    TASK_TAGS_COORDS,
    TASK_BIGRAMS_RANK,
    TASK_TAGS_RANK,
    TASK_FASTTEXT,
    TASK_CLEAN_BIGRAMS,
    TASK_MARK_TELEGRAM,
    TASK_GMAIL_SORT,
)

def on_tasks_get(app, user: dict, request: Request) -> Response:
    current_tasks = app.tasks.get_current_tasks_titles(user["sid"])
    available_tasks = {
        TASK_DOWNLOAD: "Download posts",
        TASK_MARK: "Sync read state",
        TASK_TAGS: "Build tags",
        TASK_LETTERS: "Build letters",
        TASK_NER: "Named Entity Recognition",
        TASK_CLUSTERING: "Cluster posts",
        TASK_W2V: "Train Word2Vec",
        TASK_D2V: "Train Doc2Vec",
        TASK_TAGS_SENTIMENT: "Tags sentiment",
        TASK_TAGS_GROUP: "Group tags",
        TASK_TAGS_COORDS: "Tags coords",
        TASK_BIGRAMS_RANK: "Rank bigrams",
        TASK_TAGS_RANK: "Rank tags",
        TASK_FASTTEXT: "Train FastText",
        TASK_CLEAN_BIGRAMS: "Clean bigrams",
        TASK_MARK_TELEGRAM: "Sync Telegram read state",
        TASK_GMAIL_SORT: "Sort Gmail emails"
    }
    
    page = app.template_env.get_template("tasks.html")
    return Response(
        page.render(
            current_tasks=current_tasks,
            available_tasks=available_tasks,
            user_settings=user["settings"],
            provider=user["provider"],
            support=app.config["settings"]["support"],
            version=app.config["settings"]["version"],
        ),
        mimetype="text/html",
    )

def on_tasks_post(app, user: dict, request: Request) -> Response:
    task_type = request.form.get("task_type")
    if task_type:
        try:
            task_type = int(task_type)
            app.tasks.add_task({
                "user": user["sid"],
                "type": task_type,
                "data": [], # Some tasks might need data, but for general ones empty list/dict might suffice or be ignored
                "host": app.config["settings"]["host_name"] # TASK_DOWNLOAD needs host
            })
        except ValueError:
            logging.error("Invalid task type: %s", task_type)
    
    return redirect("/tasks")
