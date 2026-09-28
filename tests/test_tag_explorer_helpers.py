"""Small explorer checks that do not require a MongoDB service."""

import gzip
import unittest
from types import SimpleNamespace
from typing import Any, Iterator
from unittest.mock import Mock, patch

from werkzeug.wrappers import Request

from rsstag.web.tag_explorer import (
    DEFAULT_POSTS_ON_PAGE,
    _make_tree,
    _validate_selection,
    _load_result_content,
    _grouped_sentences,
    _matching_posts,
    _posts_for_tag,
    _results,
    _topic_memberships,
    _topic_nodes,
    on_tag_explorer_get,
)
from rsstag.web.tags import _build_tag_context_tree, _label_tag_context_tree


class TestTagExplorerHelpers(unittest.TestCase):
    def setUp(self) -> None:
        self.user: dict[str, Any] = {"sid": "owner", "settings": {"only_unread": False}}

    def test_filter_query_loads_only_needed_fields(self) -> None:
        posts: Mock = Mock()
        posts.get_by_tags.return_value = []
        app: Any = SimpleNamespace(posts=posts)
        selection: dict[str, Any] = {
            "kind": "context", "chain": ["cli"],
        }

        _posts_for_tag(app, self.user, "root", selection)

        projection: dict[str, int] = posts.get_by_tags.call_args.args[3]
        self.assertEqual(projection, {"_id": 0, "pid": 1, "read": 1, "lemmas": 1})

    def test_result_content_loads_all_supplied_page_posts(self) -> None:
        posts: Mock = Mock()
        posts.get_by_pids.return_value = [
            {"pid": str(index), "content": {"title": f"Post {index}"}}
            for index in reversed(range(DEFAULT_POSTS_ON_PAGE + 5))
        ]
        app: Any = SimpleNamespace(posts=posts)
        matches: list[dict[str, Any]] = [{"pid": str(index)} for index in range(DEFAULT_POSTS_ON_PAGE + 5)]

        visible: list[dict[str, Any]] = _load_result_content(app, self.user, matches)

        self.assertEqual(len(visible), DEFAULT_POSTS_ON_PAGE + 5)
        self.assertEqual(visible[0]["content"]["title"], "Post 0")
        self.assertEqual(len(posts.get_by_pids.call_args.args[1]), DEFAULT_POSTS_ON_PAGE + 5)
        self.assertEqual(posts.get_by_pids.call_args.kwargs["projection"], {"_id": 0, "pid": 1, "content": 1, "read": 1})

    def test_results_include_addressable_sentence_and_post_read_state(self) -> None:
        grouping: Mock = Mock()
        grouping.get_by_post_ids.return_value = [{
            "post_ids": ["one"],
            "sentences": [{"number": 1, "text": "Root sentence.", "read": True}],
        }]
        app: Any = SimpleNamespace(post_grouping=grouping)
        grouped: dict[str, list[dict[str, Any]]] = _grouped_sentences(app, self.user, [{"pid": "one"}])
        result: dict[str, Any] = _results(
            [{"pid": "one", "content": {"title": "Example"}, "read": False}],
            "root", {"kind": "root"}, grouped,
        )

        self.assertEqual(result["sentences"][0]["number"], 1)
        self.assertTrue(result["sentences"][0]["read"])
        self.assertFalse(result["posts"][0]["read"])

    def test_posts_show_full_body_independently_of_sentence_filters(self) -> None:
        body: str = "Root read sentence. " + "Unrelated body text. " * 40 + "Root cli unread sentence."
        post: dict[str, Any] = {
            "pid": 1, "content": {"title": "Example", "content": gzip.compress(body.encode())},
        }
        grouped: dict[str, list[dict[str, Any]]] = {"1": [
            {"number": 1, "text": "Root read sentence.", "read": True},
            {"number": 2, "text": "Root cli unread sentence.", "read": False},
        ]}
        selections: list[dict[str, Any]] = [
            {"kind": "root"}, {"kind": "context", "chain": ["cli"]},
            {"kind": "topic", "chain": ["Tech"]},
        ]
        for selection in selections:
            with self.subTest(selection=selection):
                selected_post: dict[str, Any] = {**post, "topic_numbers": {2}} if selection["kind"] == "topic" else post
                result: dict[str, Any] = _results([selected_post], "root", selection, grouped, True)
                self.assertEqual(result["posts"][0]["excerpt"], body)
                self.assertEqual([sentence["number"] for sentence in result["sentences"]], [2])
                self.assertEqual(result["sentences"][0]["text"], "Root cli unread sentence.")

    def test_long_sentence_cannot_exceed_full_post_body(self) -> None:
        for body in ("Root " + "word " * 120, "Root short body."):
            with self.subTest(length=len(body)):
                post: dict[str, Any] = {
                    "pid": "one", "content": {"content": gzip.compress(f"<p>{body}</p>".encode())},
                }
                grouped: dict[str, list[dict[str, Any]]] = {"one": [
                    {"number": 1, "text": f"<b>{body}</b> Additional grouping text."},
                ]}
                result: dict[str, Any] = _results([post], "root", {"kind": "root"}, grouped)
                self.assertEqual(result["posts"][0]["excerpt"], body.strip())
                sentence_text: str = result["sentences"][0]["text"]
                self.assertEqual(sentence_text, (body + " Additional grouping text.")[:min(500, len(body.strip()))])
                self.assertLessEqual(len(sentence_text), len(result["posts"][0]["excerpt"]))

    def test_ungrouped_posts_show_whole_body_and_matching_sentence(self) -> None:
        body: str = "Opening sentence. Root matching sentence. Closing sentence."
        post: dict[str, Any] = {"pid": 1, "content": {"content": gzip.compress(body.encode())}}
        result: dict[str, Any] = _results([post], "root", {"kind": "root"}, {})
        self.assertEqual(result["posts"][0]["excerpt"], body)
        self.assertEqual(result["sentences"][0]["text"], "Root matching sentence.")
        self.assertIsNone(result["sentences"][0]["number"])

    def test_chain_counts_documents_and_includes_all_posts(self) -> None:
        posts: list[dict[str, Any]] = [
            {"pid": index, "lemmas": gzip.compress(b"codex cli tool codex cli tool")}
            for index in range(150)
        ]
        posts.append({"pid": 150, "lemmas": gzip.compress(b"codex cli other")})
        tree: dict[str, Any] = _make_tree(iter(posts), "codex")
        cli: dict[str, Any] = next(node for node in tree["context"] if node["name"] == "cli")
        tool: dict[str, Any] = next(node for node in cli["children"] if node["name"] == "tool")
        self.assertEqual(tree["count"], 151)
        self.assertEqual(cli["count"], 151)
        self.assertEqual(cli["occurrences"], 301)
        self.assertEqual(tool["count"], 150)
        matches: list[dict[str, Any]] = list(_matching_posts(
            SimpleNamespace(), self.user, "codex", posts,
            {"kind": "context", "chain": ["cli", "tool"]},
        ))
        self.assertEqual(len(matches), tool["count"])

    def test_five_word_chains_in_both_directions_preserve_repeated_words(self) -> None:
        posts: list[dict[str, Any]] = [{"pid": 1, "lemmas": gzip.compress(b"a b c d e root x x y z end beyond")}]
        tree: dict[str, Any] = _make_tree(posts, "root")
        for words in (["e", "d", "c", "b", "a"], ["x", "x", "y", "z", "end"]):
            nodes: list[dict[str, Any]] = tree["context"]
            chain: list[str] = []
            for word in words:
                node: dict[str, Any] = next(node for node in nodes if node["name"] == word)
                self.assertEqual(node["name"], word)
                chain.append(word)
                nodes = node["children"]
            self.assertEqual(nodes, [])
            selection: dict[str, Any] = _validate_selection({"kind": "context", "chain": chain})
            self.assertEqual(len(list(_matching_posts(SimpleNamespace(), self.user, "root", posts, selection))), 1)

    def test_invalid_chains_are_rejected(self) -> None:
        for chain in ([], [True], [1], [""], [{"word": "cli"}], ["x"] * 6):
            with self.assertRaises(ValueError):
                _validate_selection({"kind": "context", "chain": chain})

    def test_directions_merge_without_double_counting_posts(self) -> None:
        texts: list[str] = ["codex cli tool", "tool cli codex", "tool cli codex cli tool", "codex cli other", "codex other cli tool"]
        posts: list[dict[str, Any]] = [
            {"pid": index, "lemmas": gzip.compress(text.encode())}
            for index, text in enumerate(texts)
        ]
        tree: dict[str, Any] = _make_tree(posts, "codex")
        cli: dict[str, Any] = next(node for node in tree["context"] if node["name"] == "cli")
        tool: dict[str, Any] = next(node for node in cli["children"] if node["name"] == "tool")
        self.assertEqual(len([node for node in tree["context"] if node["name"] == "cli"]), 1)
        self.assertEqual(cli["count"], 4)
        self.assertEqual(cli["occurrences"], 5)
        self.assertEqual(tool["count"], 3)
        self.assertEqual(tool["occurrences"], 4)
        for chain, expected in ((["cli"], [0, 1, 2, 3]), (["cli", "tool"], [0, 1, 2])):
            matches: list[dict[str, Any]] = list(_matching_posts(
                SimpleNamespace(), self.user, "codex", posts,
                _validate_selection({"kind": "context", "chain": chain}),
            ))
            self.assertEqual([post["pid"] for post in matches], expected)

    def test_all_branches_are_retained(self) -> None:
        posts: list[dict[str, Any]] = [
            {"pid": index, "lemmas": gzip.compress(f"root word{index}".encode())}
            for index in range(50)
        ]
        self.assertEqual(len(_make_tree(posts, "root")["context"]), 50)

    def test_mindmap_distinguishes_before_and_after(self) -> None:
        context: list[dict[str, Any]] = [{
            "pid": "one", "lemmas": ["same", "root", "same"], "root_positions": [1]
        }]
        nodes: list[dict[str, Any]] = _build_tag_context_tree(context, "root", 1)

        _label_tag_context_tree(nodes, "root")

        self.assertEqual({node["name"] for node in nodes}, {"same (before 1)", "same (after 1)"})
        self.assertEqual(len({node["_topicPath"] for node in nodes}), 2)

    def test_html_render_value_error_is_server_error(self) -> None:
        posts: Mock = Mock()
        posts.count_by_tags.return_value = 0
        app: Any = SimpleNamespace(posts=posts)
        request: Request = Request.from_values("/tag-explorer/root")
        with patch("rsstag.web.tag_explorer._posts_for_tag", return_value=[]), patch(
            "rsstag.web.tag_explorer._make_tree", side_effect=ValueError("bad data")
        ):
            response: Any = on_tag_explorer_get(app, self.user, request, "root")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.mimetype, "text/plain")

    def test_results_paginate_with_exact_document_count(self) -> None:
        posts: Mock = Mock()
        posts.get_by_tags.side_effect = lambda *args: iter({"pid": str(index)} for index in range(85))
        posts.get_by_pids.side_effect = lambda owner, pids, projection: (
            {"pid": pid, "content": {"title": f"Post {pid}", "content": gzip.compress(b"Root sentence.")}} for pid in pids
        )
        grouping: Mock = Mock()
        grouping.get_by_post_ids.return_value = []
        app: Any = SimpleNamespace(posts=posts, post_grouping=grouping)
        for setting, page_size in ((None, 30), (10, 10), (60, 60), ("50", 50), (0, 30), (-1, 30), ("invalid", 30)):
            with self.subTest(setting=setting):
                if setting is None:
                    self.user["settings"].pop("posts_on_page", None)
                else:
                    self.user["settings"]["posts_on_page"] = setting
                for page_number in (1, 2, 3):
                    request: Request = Request.from_values(
                        "/tag-explorer/root", query_string={"format": "json", "page": str(page_number)}
                    )
                    posts.get_by_pids.reset_mock()
                    response: Any = on_tag_explorer_get(app, self.user, request, "root")
                    result: dict[str, Any] = response.get_json()
                    offset: int = (page_number - 1) * page_size
                    expected_pids: list[str] = [str(index) for index in range(offset, min(offset + page_size, 85))]

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual([post["pid"] for post in result["posts"]], expected_pids)
                    self.assertEqual([sentence["pid"] for sentence in result["sentences"]], expected_pids)
                    self.assertEqual(result["page_size"], page_size)
                    self.assertEqual(result["page"], page_number)
                    self.assertEqual(result["has_more"], 85 > offset + page_size)
                    self.assertEqual(result["total"], 85)
                    if expected_pids:
                        self.assertEqual(posts.get_by_pids.call_args.args[1], expected_pids)
                    else:
                        posts.get_by_pids.assert_not_called()

    def test_invalid_page_is_rejected(self) -> None:
        response: Any = on_tag_explorer_get(
            SimpleNamespace(), self.user,
            Request.from_values("/tag-explorer/root", query_string={"format": "json", "page": "0"}),
            "root",
        )
        self.assertEqual(response.status_code, 400)

    def test_tree_consumes_all_posts(self) -> None:
        posts: Mock = Mock()
        consumed: list[int] = []

        def post_stream() -> Iterator[dict[str, str]]:
            for index in range(150):
                consumed.append(index)
                yield {"pid": str(index)}

        posts.get_by_tags.return_value = post_stream()
        template_env: Mock = Mock()
        template_env.get_template.return_value.render.return_value = "page"
        grouping: Mock = Mock()
        grouping.get_by_post_ids.return_value = []
        app: Any = SimpleNamespace(posts=posts, template_env=template_env, post_grouping=grouping)
        response: Any = on_tag_explorer_get(
            app, self.user, Request.from_values("/tag-explorer/root"), "root"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(consumed), 150)
        self.assertEqual(template_env.get_template.return_value.render.call_args.kwargs["tree"]["count"], 150)
        self.assertEqual(posts.get_by_tags.call_args.args[3], {"_id": 0, "pid": 1, "read": 1, "lemmas": 1})


    def test_topic_prefixes_count_unique_posts_and_filter_exact_branches(self) -> None:
        grouping: Mock = Mock()
        grouping.get_by_post_ids.return_value = [
            {"post_ids": [1], "groups": {"Tech > AI": [1], "Tech>Tools": [2]},
             "sentences": [{"number": 1, "text": "AI sentence."}, {"number": 2, "text": "Tools sentence."}]},
            {"post_ids": ["2"], "groups": {"Tech > AI": [1]},
             "sentences": [{"number": 1, "text": "Other AI sentence.", "read": True}]},
            {"post_ids": [3], "groups": {"Technology > AI": [1]},
             "sentences": [{"number": 1, "text": "Unrelated sentence."}]},
            {"post_ids": ["outside"], "groups": {"Tech > AI": [1]}, "sentences": []},
        ]
        app: Any = SimpleNamespace(post_grouping=grouping)
        posts: list[dict[str, Any]] = [{"pid": pid} for pid in (1, 2, 3)]
        memberships: dict[tuple[str, ...], dict[str, set[int]]] = _topic_memberships(app, self.user, posts)
        tree: list[dict[str, Any]] = _topic_nodes(memberships)
        self.assertEqual(tree[0]["name"], "Tech")
        self.assertEqual(tree[0]["count"], 2)
        self.assertEqual(tree[0]["children"][0]["count"], 2)
        matches: list[dict[str, Any]] = list(_matching_posts(
            app, self.user, "root", posts, {"kind": "topic", "chain": ["Tech"]},
        ))
        self.assertEqual([post["pid"] for post in matches], [1, 2])
        self.assertEqual(matches[0]["topic_numbers"], {1, 2})
        unread_user: dict[str, Any] = {"sid": "owner", "settings": {"only_unread": True}}
        self.assertEqual(_topic_memberships(app, unread_user, posts)[("Tech", "AI")], {"1": {1}})

    def test_topic_results_show_only_selected_sentences_for_page_and_all_scope(self) -> None:
        posts: Mock = Mock()
        posts.get_by_tags.side_effect = lambda *args: iter([{"pid": 1}])
        posts.get_by_pids.return_value = [{"pid": 1, "content": {"title": "Example"}}]
        grouping: Mock = Mock()
        grouping.get_by_post_ids.return_value = [{
            "post_ids": ["1"], "groups": {"Tech > AI": [2, 3, 4], "Tech > Tools": [1]},
            "sentences": [{"number": number, "text": f"Sentence {number}."} for number in range(1, 5)],
        }]
        app: Any = SimpleNamespace(posts=posts, post_grouping=grouping)
        for scope in ("page", "all"):
            request: Request = Request.from_values("/tag-explorer/root", query_string={
                "format": "json", "scope": scope,
                "selection": '{"kind":"topic","chain":["Tech","AI"]}',
            })
            response: Any = on_tag_explorer_get(app, self.user, request, "root")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["total"], 1)
            self.assertEqual([item["number"] for item in response.get_json()["sentences"]], [2, 3, 4])

    def test_invalid_topic_paths_are_rejected(self) -> None:
        for chain in ([], "Tech", [True], [""], [" Tech"], ["Tech > AI"], ["x"] * 101):
            with self.assertRaises(ValueError):
                _validate_selection({"kind": "topic", "chain": chain})


    def test_only_unread_setting_filters_posts_query(self) -> None:
        posts: Mock = Mock()
        posts.get_by_tags.return_value = []
        app: Any = SimpleNamespace(posts=posts)
        for setting, expected in ((True, True), (False, None)):
            user: dict[str, Any] = {"sid": "owner", "settings": {"only_unread": setting}}
            _posts_for_tag(app, user, "root", {"kind": "root"})
            self.assertEqual(posts.get_by_tags.call_args.args[2], expected)

    def test_only_unread_hides_read_sentences(self) -> None:
        grouped: dict[str, list[dict[str, Any]]] = {"one": [
            {"number": 1, "text": "Root read.", "read": True},
            {"number": 2, "text": "Root unread.", "read": False},
        ]}
        post: dict[str, Any] = {"pid": "one", "content": {"title": "Example"}, "read": False}

        shown: dict[str, Any] = _results([post], "root", {"kind": "root"}, grouped, True)
        everything: dict[str, Any] = _results([post], "root", {"kind": "root"}, grouped, None)

        self.assertEqual([item["number"] for item in shown["sentences"]], [2])
        self.assertEqual([item["number"] for item in everything["sentences"]], [1, 2])

    def test_all_scope_returns_every_page(self) -> None:
        posts: Mock = Mock()
        posts.get_by_tags.side_effect = lambda *args: iter(
            {"pid": str(index), "read": index % 2 == 0} for index in range(85)
        )
        grouping: Mock = Mock()
        grouping.get_by_post_ids.return_value = [
            {"post_ids": ["3"], "sentences": [
                {"number": 1, "text": "Root read.", "read": True},
                {"number": 2, "text": "Root other.", "read": False},
            ]},
        ]
        app: Any = SimpleNamespace(posts=posts, post_grouping=grouping)
        request: Request = Request.from_values(
            "/tag-explorer/root", query_string={"format": "json", "scope": "all"}
        )

        result: dict[str, Any] = on_tag_explorer_get(app, self.user, request, "root").get_json()

        self.assertEqual(result["total"], 85)
        self.assertEqual(len(result["posts"]), 85)
        self.assertTrue(result["posts"][0]["read"])
        self.assertEqual(
            result["sentences"],
            [{"pid": "3", "number": 1, "read": True}, {"pid": "3", "number": 2, "read": False}],
        )
        self.assertEqual(len(grouping.get_by_post_ids.call_args.args[1]), 85)

    def test_invalid_scope_is_rejected(self) -> None:
        response: Any = on_tag_explorer_get(
            SimpleNamespace(), self.user,
            Request.from_values("/tag-explorer/root", query_string={"format": "json", "scope": "x"}),
            "root",
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
