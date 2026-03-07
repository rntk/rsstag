import inspect
import socket
import tempfile
import unittest
from typing import Any, Callable, Dict, List
from unittest.mock import MagicMock, patch

from pymongo.database import Database

from rsstag import tasks as task_module
from rsstag.tasks import EXTERNAL_WORKER_ALLOWED_TASK_TYPES
from rsstag.workers.dispatcher import _build_registry
from rsstag.workers.external_worker import ExternalWorkerRegistry
from rsstag.workers.registry import WorkerRegistry
from tests.db_utils import DBHelper
from tests.web_test_utils import create_test_config


EXPECTED_INTERNAL_TASK_TYPES: List[int] = [
    task_module.TASK_DOWNLOAD,
    task_module.TASK_MARK,
    task_module.TASK_TAGS,
    task_module.TASK_LETTERS,
    task_module.TASK_NER,
    task_module.TASK_CLUSTERING,
    task_module.TASK_SNIPPET_CLUSTERING,
    task_module.TASK_W2V,
    task_module.TASK_TAGS_SENTIMENT,
    task_module.TASK_TAGS_GROUP,
    task_module.TASK_BIGRAMS_RANK,
    task_module.TASK_TAGS_RANK,
    task_module.TASK_FASTTEXT,
    task_module.TASK_CLEAN_BIGRAMS,
    task_module.TASK_MARK_TELEGRAM,
    task_module.TASK_GMAIL_SORT,
    task_module.TASK_POST_GROUPING,
    task_module.TASK_TAG_CLASSIFICATION,
    task_module.TASK_POST_GROUPING_BATCH,
    task_module.TASK_TAG_CLASSIFICATION_BATCH,
    task_module.TASK_DELETE_FEEDS,
    task_module.TASK_POST_GROUPING_CLEANUP,
]


def _require_test_mongo() -> None:
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            pass
    except OSError as exc:
        raise unittest.SkipTest(
            f"MongoDB on port 8765 is required for worker registry tests: {exc}"
        )


def _get_task_constants() -> Dict[str, int]:
    return {
        name: value
        for name, value in vars(task_module).items()
        if name.startswith("TASK_") and isinstance(value, int)
    }


class TestWorkerRegistryCompleteness(unittest.TestCase):
    db_helper: DBHelper
    test_db: Database
    config_path: str
    tmp_dir: tempfile.TemporaryDirectory[str]

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
                f"MongoDB on port 8765 is required for worker registry tests: {exc}"
            )

        cls.test_db = cls.db_helper.create_test_db()
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.config_path = create_test_config(
            db_host=cls.db_helper.host,
            db_port=cls.db_helper.port,
            db_name=cls.test_db.name,
            tmp_dir=cls.tmp_dir.name,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db_helper.drop_test_db(cls.test_db)
        cls.db_helper.close()
        cls.tmp_dir.cleanup()
        super().tearDownClass()

    def _build_internal_registry(self) -> WorkerRegistry:
        tag_worker: MagicMock = MagicMock()
        llm_worker: MagicMock = MagicMock()
        provider_worker: MagicMock = MagicMock()

        registry: WorkerRegistry = _build_registry(
            tag_worker=tag_worker,
            llm_worker=llm_worker,
            provider_worker=provider_worker,
        )
        return registry

    def test_build_internal_registry_registers_expected_task_types(self) -> None:
        registry: WorkerRegistry = self._build_internal_registry()

        self.assertEqual(
            set(EXPECTED_INTERNAL_TASK_TYPES),
            set(registry._handlers.keys()),
        )

    def test_internal_registry_has_no_duplicate_task_types(self) -> None:
        registry: WorkerRegistry = self._build_internal_registry()

        self.assertEqual(
            len(EXPECTED_INTERNAL_TASK_TYPES),
            len(set(EXPECTED_INTERNAL_TASK_TYPES)),
        )
        self.assertEqual(len(EXPECTED_INTERNAL_TASK_TYPES), len(registry._handlers))

    def test_all_registered_handlers_are_callable(self) -> None:
        registry: WorkerRegistry = self._build_internal_registry()

        for task_type, handler in registry._handlers.items():
            with self.subTest(task_type=task_type):
                self.assertTrue(callable(handler))

    def test_registry_handle_returns_none_for_unknown_task_type(self) -> None:
        registry: WorkerRegistry = self._build_internal_registry()

        handled: Any = registry.handle({"type": 999999})

        self.assertIsNone(handled)

    def test_registry_handle_calls_registered_handler(self) -> None:
        registry: WorkerRegistry = WorkerRegistry()
        handler: MagicMock = MagicMock(return_value=True)
        task: Dict[str, Any] = {"type": 123, "payload": "x"}
        registry.register(123, handler)

        handled: Any = registry.handle(task)

        self.assertTrue(handled)
        handler.assert_called_once_with(task)

    def test_external_registry_contains_only_allowed_task_plugins(self) -> None:
        with patch(
            "rsstag.workers.external_worker.LLMRouter",
            return_value=MagicMock(),
        ):
            registry: ExternalWorkerRegistry = ExternalWorkerRegistry()
            from rsstag.workers.external_worker import (
                PostGroupingPlugin,
                TagClassificationPlugin,
            )

            registry.register(PostGroupingPlugin(MagicMock()))
            registry.register(TagClassificationPlugin(MagicMock()))

        self.assertEqual(set(EXTERNAL_WORKER_ALLOWED_TASK_TYPES), set(registry._plugins))

    def test_external_registry_whitelist_matches_expected_plugins(self) -> None:
        self.assertEqual(
            {
                task_module.TASK_POST_GROUPING,
                task_module.TASK_TAG_CLASSIFICATION,
            },
            set(EXTERNAL_WORKER_ALLOWED_TASK_TYPES),
        )

    def test_task_constants_are_unique(self) -> None:
        task_constants: Dict[str, int] = _get_task_constants()
        values: List[int] = list(task_constants.values())

        self.assertEqual(len(values), len(set(values)))

    def test_tasks_after_chain_references_valid_task_constants(self) -> None:
        task_constants: Dict[str, int] = _get_task_constants()
        valid_values = set(task_constants.values())

        for parent_task, child_tasks in task_module.RssTagTasks._tasks_after.items():
            with self.subTest(parent_task=parent_task):
                self.assertIn(parent_task, valid_values)
                for child_task in child_tasks:
                    self.assertIn(child_task, valid_values)

    def test_registered_handlers_map_to_expected_worker_methods(self) -> None:
        tag_worker: MagicMock = MagicMock()
        llm_worker: MagicMock = MagicMock()
        provider_worker: MagicMock = MagicMock()
        registry: WorkerRegistry = _build_registry(tag_worker, llm_worker, provider_worker)

        expected_sources: Dict[int, Callable[..., Any]] = {
            task_module.TASK_DOWNLOAD: provider_worker.handle_download,
            task_module.TASK_MARK: provider_worker.handle_mark,
            task_module.TASK_MARK_TELEGRAM: provider_worker.handle_mark_telegram,
            task_module.TASK_GMAIL_SORT: provider_worker.handle_gmail_sort,
            task_module.TASK_TAGS: tag_worker.handle_tags,
            task_module.TASK_LETTERS: tag_worker.handle_letters,
            task_module.TASK_NER: tag_worker.handle_ner,
            task_module.TASK_TAGS_SENTIMENT: tag_worker.handle_tags_sentiment,
            task_module.TASK_CLUSTERING: tag_worker.handle_clustering,
            task_module.TASK_SNIPPET_CLUSTERING: tag_worker.handle_snippet_clustering,
            task_module.TASK_W2V: tag_worker.handle_w2v,
            task_module.TASK_FASTTEXT: tag_worker.handle_fasttext,
            task_module.TASK_TAGS_GROUP: tag_worker.handle_tags_groups,
            task_module.TASK_BIGRAMS_RANK: tag_worker.make_bi_grams_rank,
            task_module.TASK_TAGS_RANK: tag_worker.make_tags_rank,
            task_module.TASK_CLEAN_BIGRAMS: tag_worker.make_clean_bigrams,
            task_module.TASK_POST_GROUPING: llm_worker.handle_post_grouping,
            task_module.TASK_TAG_CLASSIFICATION: llm_worker.handle_tags_classification,
            task_module.TASK_POST_GROUPING_BATCH: llm_worker.make_post_grouping_batch,
            task_module.TASK_TAG_CLASSIFICATION_BATCH: llm_worker.make_tags_classification_batch,
            task_module.TASK_POST_GROUPING_CLEANUP: llm_worker.handle_post_grouping_cleanup,
            task_module.TASK_DELETE_FEEDS: tag_worker.handle_delete_feeds,
        }

        self.assertEqual(expected_sources, registry._handlers)


class TestWorkerRegistrySignatures(unittest.TestCase):
    def test_worker_registry_register_signature_accepts_handler(self) -> None:
        signature: inspect.Signature = inspect.signature(WorkerRegistry.register)
        self.assertIn("task_type", signature.parameters)
        self.assertIn("handler", signature.parameters)
