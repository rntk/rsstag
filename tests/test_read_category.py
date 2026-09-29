"""Unit tests for rsstag.web.posts.on_read_category_post."""

import json
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock

from werkzeug.wrappers import Request
from werkzeug.test import EnvironBuilder

from rsstag.web.posts import on_read_category_post, on_read_feed_post


def _request(body: Any) -> Request:
    data: str = body if isinstance(body, str) else json.dumps(body)
    return Request(EnvironBuilder(method="POST", data=data).get_environ())


def _app(pids: List[int]) -> MagicMock:
    app = MagicMock()
    app.posts.get_by_category.return_value = [{"pid": pid} for pid in pids]
    app.posts.get_by_pids.return_value = []
    app.posts.change_status.return_value = True
    app.tasks.add_task.return_value = True
    return app


class TestOnReadCategoryPost(unittest.TestCase):
    user: Dict[str, Any] = {"sid": "sid1", "provider": "x"}

    def test_marks_unread_posts_of_category_read(self) -> None:
        app: MagicMock = _app([1, 2, 3])

        response = on_read_category_post(
            app, self.user, _request({"category_id": "c1", "readed": True})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_data())["changed"], 3)
        app.posts.get_by_category.assert_called_once_with(
            "sid1", only_unread=True, category="c1", projection={"pid": True}
        )
        app.posts.change_status.assert_called_once_with("sid1", [1, 2, 3], True)

    def test_unread_selects_read_posts(self) -> None:
        app: MagicMock = _app([4])

        on_read_category_post(
            app, self.user, _request({"category_id": "c1", "readed": False})
        )

        self.assertFalse(app.posts.get_by_category.call_args.kwargs["only_unread"])
        app.posts.change_status.assert_called_once_with("sid1", [4], False)

    def test_empty_category_changes_nothing(self) -> None:
        app: MagicMock = _app([])

        response = on_read_category_post(
            app, self.user, _request({"category_id": "c1", "readed": True})
        )

        self.assertEqual(response.status_code, 200)
        app.posts.change_status.assert_not_called()

    def test_rejects_bad_body(self) -> None:
        app: MagicMock = _app([1])

        for body in ("not json", {"readed": True}, {"category_id": "", "readed": True}):
            response = on_read_category_post(app, self.user, _request(body))
            self.assertEqual(response.status_code, 400)
        app.posts.get_by_category.assert_not_called()

    def test_task_failure_returns_500(self) -> None:
        app: MagicMock = _app([1])
        app.tasks.add_task.return_value = False

        response = on_read_category_post(
            app, self.user, _request({"category_id": "c1", "readed": True})
        )

        self.assertEqual(response.status_code, 500)


class TestOnReadFeedPost(unittest.TestCase):
    user: Dict[str, Any] = {"sid": "sid1", "provider": "x"}

    def test_marks_unread_posts_of_feed_read(self) -> None:
        app: MagicMock = _app([])
        app.posts.get_by_feed_id.return_value = [{"pid": 7}, {"pid": 8}]

        response = on_read_feed_post(
            app, self.user, _request({"feed_id": "f1", "readed": True})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_data())["changed"], 2)
        app.posts.get_by_feed_id.assert_called_once_with(
            "sid1", "f1", only_unread=True, projection={"pid": True}
        )
        app.posts.change_status.assert_called_once_with("sid1", [7, 8], True)

    def test_rejects_bad_body(self) -> None:
        app: MagicMock = _app([])

        for body in ("not json", {"readed": True}, {"feed_id": "", "readed": True}):
            response = on_read_feed_post(app, self.user, _request(body))
            self.assertEqual(response.status_code, 400)
        app.posts.get_by_feed_id.assert_not_called()


if __name__ == "__main__":
    unittest.main()
