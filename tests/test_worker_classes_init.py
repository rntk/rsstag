import inspect
import socket
import tempfile
import unittest
from typing import Any, Dict, List, Type
from unittest.mock import MagicMock, patch

from rsstag.workers.base import BaseWorker
from rsstag.workers.llm_worker import LLMWorker
from rsstag.workers.provider_worker import ProviderWorker
from rsstag.workers.tag_worker import TagWorker
from tests.db_utils import DBHelper
from tests.web_test_utils import create_test_config


def _require_test_mongo() -> None:
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            pass
    except OSError as exc:
        raise unittest.SkipTest(
            f"MongoDB on port 8765 is required for worker class init tests: {exc}"
        )


class TestWorkerClassesInit(unittest.TestCase):
    db_helper: DBHelper
    tmp_dir: tempfile.TemporaryDirectory[str]
    config: Dict[str, Any]
    db: Any

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _require_test_mongo()
        cls.db_helper = DBHelper(port=8765)
        try:
            cls.db_helper.client.admin.command("ping")
        except Exception as exc:
            cls.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for worker class init tests: {exc}"
            )
        cls.db = cls.db_helper.create_test_db()
        cls.tmp_dir = tempfile.TemporaryDirectory()
        config_path: str = create_test_config(
            db_host=cls.db_helper.host,
            db_port=cls.db_helper.port,
            db_name=cls.db.name,
            tmp_dir=cls.tmp_dir.name,
        )
        from rsstag.utils import load_config

        cls.config = load_config(config_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db_helper.drop_test_db(cls.db)
        cls.db_helper.close()
        cls.tmp_dir.cleanup()
        super().tearDownClass()

    def test_base_worker_construction_succeeds(self) -> None:
        with patch("rsstag.workers.base.stopwords.words", side_effect=[["a"], ["b"]]):
            worker: BaseWorker = BaseWorker(self.db, self.config)

        self.assertIs(worker._db, self.db)
        self.assertEqual(self.config, worker._config)

    def test_base_worker_loads_stopwords(self) -> None:
        with patch("rsstag.workers.base.stopwords.words", side_effect=[["a"], ["b"]]):
            worker: BaseWorker = BaseWorker(self.db, self.config)

        self.assertEqual({"a", "b"}, worker._stopw)

    def test_tag_worker_construction_succeeds(self) -> None:
        with patch("rsstag.workers.base.stopwords.words", side_effect=[["a"], ["b"]]):
            worker: TagWorker = TagWorker(self.db, self.config)

        self.assertIsInstance(worker, TagWorker)

    def test_tag_worker_exposes_expected_handler_methods(self) -> None:
        expected_methods: List[str] = [
            "handle_tags",
            "handle_letters",
            "handle_ner",
            "handle_clustering",
            "handle_snippet_clustering",
            "handle_w2v",
            "handle_tags_sentiment",
            "handle_tags_groups",
            "make_bi_grams_rank",
            "make_tags_rank",
            "handle_fasttext",
            "make_clean_bigrams",
            "handle_delete_feeds",
        ]

        for method_name in expected_methods:
            with self.subTest(method_name=method_name):
                self.assertTrue(callable(getattr(TagWorker, method_name, None)))

    def test_llm_worker_construction_succeeds(self) -> None:
        with patch("rsstag.workers.base.stopwords.words", side_effect=[["a"], ["b"]]):
            with patch("rsstag.workers.llm_worker.LLMRouter", return_value=MagicMock()):
                worker: LLMWorker = LLMWorker(self.db, self.config)

        self.assertIsInstance(worker, LLMWorker)

    def test_llm_worker_has_llm_router_attribute(self) -> None:
        router: MagicMock = MagicMock()
        with patch("rsstag.workers.base.stopwords.words", side_effect=[["a"], ["b"]]):
            with patch("rsstag.workers.llm_worker.LLMRouter", return_value=router):
                worker: LLMWorker = LLMWorker(self.db, self.config)

        self.assertIs(worker._llm, router)

    def test_llm_worker_exposes_expected_handler_methods(self) -> None:
        expected_methods: List[str] = [
            "handle_post_grouping",
            "handle_tags_classification",
            "make_post_grouping_batch",
            "make_tags_classification_batch",
            "handle_post_grouping_cleanup",
        ]

        for method_name in expected_methods:
            with self.subTest(method_name=method_name):
                self.assertTrue(callable(getattr(LLMWorker, method_name, None)))

    def test_provider_worker_construction_succeeds(self) -> None:
        worker: ProviderWorker = ProviderWorker(
            self.db,
            self.config,
            providers={},
            users=MagicMock(),
            tasks=MagicMock(),
            record_bulk_write=MagicMock(),
        )

        self.assertIsInstance(worker, ProviderWorker)

    def test_provider_worker_exposes_expected_handler_methods(self) -> None:
        expected_methods: List[str] = [
            "handle_download",
            "handle_mark",
            "handle_mark_telegram",
            "handle_gmail_sort",
        ]

        for method_name in expected_methods:
            with self.subTest(method_name=method_name):
                self.assertTrue(callable(getattr(ProviderWorker, method_name, None)))

    def test_all_handler_methods_accept_task_argument(self) -> None:
        method_map: Dict[Type[Any], List[str]] = {
            TagWorker: [
                "handle_tags",
                "handle_letters",
                "handle_ner",
                "handle_clustering",
                "handle_snippet_clustering",
                "handle_w2v",
                "handle_tags_sentiment",
                "handle_tags_groups",
                "make_bi_grams_rank",
                "make_tags_rank",
                "handle_fasttext",
                "make_clean_bigrams",
                "handle_delete_feeds",
            ],
            LLMWorker: [
                "handle_post_grouping",
                "handle_tags_classification",
                "make_post_grouping_batch",
                "make_tags_classification_batch",
                "handle_post_grouping_cleanup",
            ],
            ProviderWorker: [
                "handle_download",
                "handle_mark",
                "handle_mark_telegram",
                "handle_gmail_sort",
            ],
        }

        for worker_cls, method_names in method_map.items():
            for method_name in method_names:
                with self.subTest(worker_cls=worker_cls.__name__, method_name=method_name):
                    signature: inspect.Signature = inspect.signature(
                        getattr(worker_cls, method_name)
                    )
                    self.assertIn("task", signature.parameters)
