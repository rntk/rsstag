import json
import logging
from werkzeug.wrappers import Response, Request
from rsstag.tasks import TASK_DELETE_FEEDS


def on_delete_feeds_categories_post(app, user: dict, request: Request) -> Response:
    try:
        data = json.loads(request.data)
        feed_ids = data.get("feed_ids", [])
        category_ids = data.get("category_ids", [])

        logging.info(
            "Delete request for user %s: feeds=%s, categories=%s",
            user["sid"],
            feed_ids,
            category_ids,
        )

        if not feed_ids and not category_ids:
            return Response(
                json.dumps(
                    {"status": "error", "message": "No feeds or categories selected"}
                ),
                mimetype="application/json",
                status=400,
            )

        # Expand categories to feed_ids
        if category_ids:
            db_feeds = app.feeds.get_by_categories(
                user["sid"], category_ids, projection={"feed_id": True}
            )
            for f in db_feeds:
                if f["feed_id"] not in feed_ids:
                    feed_ids.append(f["feed_id"])
            logging.info("Expanded feed IDs from categories: %s", feed_ids)

        if feed_ids:
            # Create task
            task_data = {
                "user": user["sid"],
                "type": TASK_DELETE_FEEDS,
                "feed_ids": feed_ids,
                "manual": True,
                "host": app.config["settings"]["host_name"],
            }
            res = app.tasks.add_task(task_data)
            logging.info("Task added: %s, result: %s", task_data, res)

            return Response(
                json.dumps({"status": "success", "message": "Deletion task started"}),
                mimetype="application/json",
            )
        else:
            logging.warning("No feeds found to delete for user %s", user["sid"])
            return Response(
                json.dumps(
                    {"status": "error", "message": "No feeds found for selection"}
                ),
                mimetype="application/json",
                status=404,
            )

    except Exception as e:
        logging.error(
            "Failed to process delete request for user %s: %s", user["sid"], e
        )
        return Response(
            json.dumps({"status": "error", "message": str(e)}),
            mimetype="application/json",
            status=500,
        )
