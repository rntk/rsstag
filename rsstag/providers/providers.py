from typing import Any, List

BAZQUX = "bazqux"
TELEGRAM = "telegram"
TEXT_FILE = "textfile"
JSONS_FILE = "jsonsfile"
GMAIL = "gmail"
X = "x"

# Name of the optional provider capability that returns the list of sources
# (feeds/channels/subscriptions) available to a user without downloading any
# posts. A provider opts in simply by implementing it; nothing here is
# telegram specific.
FEEDS_LIST_CAPABILITY = "list_feeds"


def supports_feeds_list(provider: Any) -> bool:
    """Tell whether a provider can enumerate its sources without downloading."""
    return callable(getattr(provider, FEEDS_LIST_CAPABILITY, None))


def feeds_list_providers(providers: dict) -> List[str]:
    """Return the names of providers that can refresh their sources list."""
    return sorted(name for name, provider in providers.items() if supports_feeds_list(provider))
