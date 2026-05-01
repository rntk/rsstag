import json

from tests.web_test_utils import MongoWebTestCase


class TestWebAnthologies(MongoWebTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _, cls.user_sid = cls.seed_test_user("anthologywebuser", "pass")
        cls.auth_client = cls.get_authenticated_client(cls.user_sid)
        cls.seed_minimal_data(cls.user_sid)
        cls.app.db.posts.update_many(
            {"owner": cls.user_sid},
            {"$set": {"bi_grams": ["test phrase"], "read": False}},
        )
        cls.app.db.letters.delete_many({"owner": cls.user_sid})
        cls.app.db.letters.insert_one(
            {
                "owner": cls.user_sid,
                "letters": {
                    "t": {
                        "letter": "t",
                        "local_url": "/group/tag/startwith/t/1",
                        "unread_count": 2,
                    }
                },
            }
        )
        cls.app.db.bi_grams.update_one(
            {"owner": cls.user_sid, "tag": "test phrase"},
            {"$set": {"unread_count": 2}},
        )
        cls.app.post_grouping.save_grouped_posts(
            cls.user_sid,
            ["test-post-1"],
            sentences=[
                {"number": 0, "text": "Muse article opening", "read": False},
                {"number": 1, "text": "Anthology source detail", "read": False},
            ],
            groups={"Muse > Albums": [0, 1]},
        )

    def test_anthologies_page_renders_for_authenticated_user(self) -> None:
        response = self.auth_client.get("/anthologies")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Anthologies", response.data)

    def test_tag_page_contains_start_anthology_button(self) -> None:
        response = self.auth_client.get("/tag/testtag")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Start Anthology", response.data)

    def test_topics_list_contains_anthologies_navigation_link(self) -> None:
        response = self.auth_client.get("/topics-list")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/anthologies", response.data)

    def test_create_list_get_and_delete_anthology_via_api(self) -> None:
        create_response = self.auth_client.post(
            "/api/anthologies",
            data=json.dumps(
                {
                    "seed_type": "tag",
                    "seed_value": "testtag",
                    "scope": {"mode": "all"},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 200)
        create_payload = json.loads(create_response.data)
        anthology_id = create_payload["data"]["anthology_id"]
        self.assertTrue(anthology_id)
        self.assertEqual(create_payload["data"]["status"], "pending")

        list_response = self.auth_client.get("/api/anthologies")
        self.assertEqual(list_response.status_code, 200)
        list_payload = json.loads(list_response.data)
        self.assertEqual(len(list_payload["data"]), 1)
        self.assertEqual(list_payload["data"][0]["id"], anthology_id)

        self.app.db.anthologies.update_one(
            {"_id": self.app.anthologies._to_object_id(anthology_id)},
            {
                "$set": {
                    "status": "done",
                    "result": {
                        "title": "testtag",
                        "summary": "done",
                        "source_refs": [],
                        "sub_anthologies": [],
                    },
                }
            },
        )

        detail_response = self.auth_client.get(f"/api/anthologies/{anthology_id}")
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = json.loads(detail_response.data)
        self.assertEqual(detail_payload["data"]["id"], anthology_id)
        self.assertEqual(detail_payload["data"]["result"]["title"], "testtag")

        delete_response = self.auth_client.delete(f"/api/anthologies/{anthology_id}")
        self.assertEqual(delete_response.status_code, 200)
        delete_payload = json.loads(delete_response.data)
        self.assertEqual(delete_payload["data"], "ok")
        self.assertEqual(self.app.db.anthologies.count_documents({}), 0)

    def test_anthology_detail_page_renders_hierarchy_and_logs(self) -> None:
        anthology_id = self.app.anthologies.create(
            self.user_sid,
            "tag",
            "testtag",
            {"mode": "all"},
        )
        self.assertIsNotNone(anthology_id)

        run_id = self.app.anthology_runs.create(anthology_id, self.user_sid)
        self.assertIsNotNone(run_id)
        self.assertTrue(
            self.app.anthology_runs.append_turn(
                run_id,
                {
                    "turn": 1,
                    "messages": [{"role": "system", "content": "Preparing anthology"}],
                    "tool_calls": [{"name": "collect_sources"}],
                    "tool_results": [{"status": "ok"}],
                },
            )
        )
        self.assertTrue(self.app.anthology_runs.finish(run_id, "done"))
        self.assertTrue(
            self.app.anthologies.update_result(
                anthology_id,
                {
                    "title": "testtag anthology",
                    "summary": "Anthology summary",
                    "source_refs": [{"post_id": "test-post-1", "title": "Test Post 1"}],
                    "sub_anthologies": [
                        {
                            "title": "Child chapter",
                            "summary": "Nested summary",
                            "source_refs": [],
                            "sub_anthologies": [],
                        }
                    ],
                },
                run_id,
                {
                    "post_grouping_updated_at": 1700000000,
                    "post_grouping_doc_ids": ["test-post-1"],
                },
            )
        )

        response = self.auth_client.get(f"/anthologies/{anthology_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Hierarchy", response.data)
        self.assertIn(b"Agent run", response.data)
        self.assertIn(b"Child chapter", response.data)
        self.assertIn(b"Preparing anthology", response.data)
        self.assertIn(f"/api/anthologies/{anthology_id}".encode("utf-8"), response.data)
        self.assertIn(b"Retry", response.data)
        self.assertIn(b"Export", response.data)

    def test_anthology_run_retry_read_and_export_endpoints(self) -> None:
        anthology_id = self.app.anthologies.create(
            self.user_sid,
            "tag",
            "testtag",
            {"mode": "all"},
        )
        self.assertIsNotNone(anthology_id)

        run_id = self.app.anthology_runs.create(anthology_id, self.user_sid)
        self.assertIsNotNone(run_id)
        self.assertTrue(
            self.app.anthology_runs.append_turn(
                run_id,
                {
                    "turn": 1,
                    "messages": [{"role": "assistant", "content": "done"}],
                    "tool_calls": [],
                    "tool_results": [],
                },
            )
        )
        self.assertTrue(self.app.anthology_runs.finish(run_id, "failed", "boom"))
        self.app.db.anthologies.update_one(
            {"_id": self.app.anthologies._to_object_id(anthology_id)},
            {
                "$set": {
                    "status": "failed",
                    "current_run_id": self.app.anthologies._to_object_id(run_id),
                    "result": {
                        "title": "testtag",
                        "summary": "done",
                        "source_refs": [
                            {
                                "post_id": "test-post-1",
                                "sentence_indices": [0, 1],
                                "topic_path": "Muse > Albums",
                                "tag": "testtag",
                            }
                        ],
                        "sub_anthologies": [
                            {
                                "node_id": "albums",
                                "title": "Albums",
                                "summary": "album updates",
                                "source_refs": [
                                    {
                                        "post_id": "test-post-1",
                                        "sentence_indices": [0],
                                        "topic_path": "Muse > Albums",
                                        "tag": "testtag",
                                    }
                                ],
                                "sub_anthologies": [],
                            }
                        ],
                    },
                }
            },
        )

        run_response = self.auth_client.get(f"/api/anthologies/{anthology_id}/run")
        self.assertEqual(run_response.status_code, 200)
        run_payload = json.loads(run_response.data)
        self.assertEqual(run_payload["data"]["status"], "failed")

        detail_response = self.auth_client.get(f"/api/anthologies/{anthology_id}")
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = json.loads(detail_response.data)
        self.assertEqual(
            detail_payload["data"]["result"]["read_state"]["unread_sentences"],
            2,
        )

        read_response = self.auth_client.post(
            f"/api/anthologies/{anthology_id}/read",
            data=json.dumps(
                {
                    "readed": True,
                    "target": {
                        "kind": "node",
                        "node_id": "albums",
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(read_response.status_code, 200)
        grouping = self.app.db.post_grouping.find_one({"owner": self.user_sid, "post_ids": "test-post-1"})
        self.assertTrue(grouping["sentences"][0]["read"])

        export_response = self.auth_client.get(
            f"/api/anthologies/{anthology_id}/export?format=markdown"
        )
        self.assertEqual(export_response.status_code, 200)
        self.assertIn(b"# testtag", export_response.data)

        retry_response = self.auth_client.post(f"/api/anthologies/{anthology_id}/retry")
        self.assertEqual(retry_response.status_code, 200)
        retried = self.app.anthologies.get_by_id(self.user_sid, anthology_id)
        self.assertIsNotNone(retried)
        self.assertEqual(retried["status"], "pending")

    def test_create_anthology_requires_seed_value(self) -> None:
        response = self.auth_client.post(
            "/api/anthologies",
            data=json.dumps({"seed_type": "tag", "seed_value": ""}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.data)
        self.assertIn("error", payload)
