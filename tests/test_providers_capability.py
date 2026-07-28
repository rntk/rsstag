"""Unit tests for the provider-agnostic "supports feeds list" capability check.

A provider opts into the sources-list refresh feature purely by implementing
``list_feeds``; ``supports_feeds_list``/``feeds_list_providers`` must reflect
that without any provider-name special-casing.
"""

import unittest
from typing import Any

from rsstag.providers.providers import feeds_list_providers, supports_feeds_list


class _WithListFeeds:
    def list_feeds(self, user: dict) -> list:
        return []


class _WithoutListFeeds:
    def download(self, user: dict, selection: Any = None) -> tuple:
        return ([], [])


class _ListFeedsNotCallable:
    # Attribute exists but is not callable: must not count as support.
    list_feeds = "not-a-method"


class TestSupportsFeedsList(unittest.TestCase):
    def test_true_for_provider_implementing_list_feeds(self) -> None:
        self.assertTrue(supports_feeds_list(_WithListFeeds()))

    def test_true_for_provider_class_itself(self) -> None:
        # The web layer checks capability on the class, before instantiation.
        self.assertTrue(supports_feeds_list(_WithListFeeds))

    def test_false_for_provider_without_list_feeds(self) -> None:
        self.assertFalse(supports_feeds_list(_WithoutListFeeds()))

    def test_false_when_list_feeds_attribute_is_not_callable(self) -> None:
        self.assertFalse(supports_feeds_list(_ListFeedsNotCallable()))

    def test_false_for_none(self) -> None:
        self.assertFalse(supports_feeds_list(None))


class TestFeedsListProviders(unittest.TestCase):
    def test_filters_to_capable_providers_only(self) -> None:
        providers = {
            "telegram": _WithListFeeds(),
            "bazqux": _WithoutListFeeds(),
            "x": _WithoutListFeeds(),
        }

        result = feeds_list_providers(providers)

        self.assertEqual(result, ["telegram"])

    def test_returns_sorted_names(self) -> None:
        providers = {
            "zprovider": _WithListFeeds(),
            "aprovider": _WithListFeeds(),
        }

        result = feeds_list_providers(providers)

        self.assertEqual(result, ["aprovider", "zprovider"])

    def test_empty_dict_returns_empty_list(self) -> None:
        self.assertEqual(feeds_list_providers({}), [])

    def test_no_capable_providers_returns_empty_list(self) -> None:
        providers = {"bazqux": _WithoutListFeeds()}

        self.assertEqual(feeds_list_providers(providers), [])


if __name__ == "__main__":
    unittest.main()
