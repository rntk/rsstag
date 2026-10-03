"""Post canvas topic generation API tests using mocked persistence."""

import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from rsstag.web.routes import RSSTagRoutes
from typing import Any
from unittest.mock import MagicMock

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from rsstag.tasks import TASK_POST_GROUPING, RssTagTasks
from rsstag.web.posts import on_post_canvas_topics


class PostCanvasTopicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app: MagicMock = MagicMock()
        self.user: dict[str, Any] = {"sid": "owner", "provider": "rss"}
        self.app.posts.get_by_pid.return_value = {"processing": 0}
        self.app.post_grouping.get_grouped_posts.return_value = None
        self.app.tasks.get_post_grouping_status.return_value = "missing"
        self.app.tasks.add_task.return_value = True
        self.app.config = {"settings": {"host_name": "localhost"}}

    def call(self, method: str = "GET") -> Response:
        request: Request = Request(
            EnvironBuilder(path="/post-canvas/p1/topics", method=method).get_environ()
        )
        return on_post_canvas_topics(self.app, self.user, request, "p1")

    def test_post_queues_only_requested_post(self) -> None:
        response: Response = self.call("POST")
        self.assertEqual(response.json, {"status": "queued"})
        task: dict[str, Any] = self.app.tasks.add_task.call_args.args[0]
        self.assertEqual(task["type"], TASK_POST_GROUPING)
        self.assertEqual(task["user"], "owner")
        self.assertEqual(task["scope"], {"mode": "posts", "post_ids": ["p1"]})
        self.app.posts.get_by_pid.assert_called_with("owner", "p1", unittest.mock.ANY)

    def test_get_does_not_enqueue(self) -> None:
        self.assertEqual(self.call().json, {"status": "missing"})
        self.app.tasks.add_task.assert_not_called()

    def test_existing_task_is_reused_and_processing_is_reported(self) -> None:
        self.app.tasks.get_post_grouping_status.return_value = "queued"
        self.app.posts.get_by_pid.return_value = {"processing": 123}
        self.assertEqual(self.call("POST").json, {"status": "processing"})
        self.app.tasks.add_task.assert_not_called()

    def test_saved_topics_report_ready(self) -> None:
        self.app.post_grouping.get_grouped_posts.return_value = {
            "groups": {"Topic": [1]},
            "sentences": [{"number": 1}],
        }
        self.assertEqual(self.call("POST").json, {"status": "ready"})
        self.app.tasks.add_task.assert_not_called()

    def test_missing_or_unowned_post_is_not_found(self) -> None:
        self.app.posts.get_by_pid.return_value = None
        self.assertEqual(self.call("POST").status_code, 404)
        self.app.tasks.add_task.assert_not_called()

    def test_failed_post_can_be_retried(self) -> None:
        self.app.posts.get_by_pid.return_value = {"grouping": 1}
        self.assertEqual(self.call().json["status"], "error")
        self.assertEqual(self.call("POST").json["status"], "queued")
        self.app.db.posts.update_one.assert_called_once_with(
            {"owner": "owner", "pid": "p1"},
            {"$unset": {"grouping": "", "grouping_attempts": "", "grouping_error": ""}},
        )

    def test_queue_failure_returns_informative_error(self) -> None:
        self.app.tasks.add_task.return_value = False
        response: Response = self.call("POST")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Please try again", response.json["message"])

    def test_grouping_scope_is_part_of_queue_identity(self) -> None:
        db: MagicMock = MagicMock()
        tasks: RssTagTasks = RssTagTasks(db)
        tasks._state = MagicMock()
        for pid in ("p1", "p2"):
            tasks.add_task(
                {
                    "user": "owner",
                    "type": TASK_POST_GROUPING,
                    "scope": {"mode": "posts", "post_ids": [pid]},
                }
            )
        keys: list[dict[str, Any]] = [
            call.args[0] for call in tasks._state.enqueue.call_args_list
        ]
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0]["scope_key"], keys[1]["scope_key"])

    def test_status_lookup_checks_owner_and_scope(self) -> None:
        db: MagicMock = MagicMock()
        tasks: RssTagTasks = RssTagTasks(db)
        db.tasks.find.return_value = [{"scope": {"mode": "posts", "post_ids": ["p2"]}}]
        db.posts.find_one.return_value = None
        self.assertEqual(tasks.get_post_grouping_status("owner", "p1"), "missing")
        query: dict[str, Any] = db.posts.find_one.call_args.args[0]
        self.assertEqual(query["$and"][0]["owner"], "owner")
        self.assertEqual(query["$and"][0]["pid"], {"$in": ["p2"]})
        self.assertEqual(query["$and"][1], {"pid": "p1"})


class PostCanvasTopicsTemplateTests(unittest.TestCase):
    def test_mixed_canvas_offers_grouping_only_for_posts_without_topics(self) -> None:
        template_dir: Path = Path(__file__).parents[1] / "rsstag/web/templates/default"
        environment: Environment = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html"]),
        )
        rendered: str = environment.get_template("post-canvas.html").render(
            posts=[
                {"post_id": "p1", "has_topics": True},
                {"post_id": "p2", "has_topics": False},
            ],
            has_grouped_data=True,
            canvas_posts=[],
            sentences=[],
            groups={},
            user_settings={},
        )
        self.assertIn("This post does not have topics yet.", rendered)
        self.assertIn("Split into topics", rendered)
        self.assertIn('data-topics-url="/post-canvas/p2/topics"', rendered)
        self.assertNotIn('data-topics-url="/post-canvas/p1/topics"', rendered)
        self.assertIn(
            '<progress aria-label="Splitting post into topics" hidden>', rendered
        )

    def test_topics_endpoint_accepts_get_and_post(self) -> None:
        routes: RSSTagRoutes = RSSTagRoutes("localhost")
        for method in ("GET", "POST"):
            endpoint: str
            values: dict[str, str]
            endpoint, values = (
                routes.get_werkzeug_routes()
                .bind("localhost")
                .match("/post-canvas/p1/topics", method=method)
            )
            self.assertEqual(endpoint, "on_post_canvas_topics")
            self.assertEqual(values, {"pid": "p1"})
