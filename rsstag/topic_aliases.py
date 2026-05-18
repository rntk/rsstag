"""Canonical topic alias storage and resolution layer.

Topics produced by post grouping are free-text hierarchical paths like
``"Artificial Intelligence > LLMs > Training"``. Different posts may express the
same concept with different wording. This module stores a stable mapping from a
raw label (within its canonical parent context) to a canonical id, and resolves
raw topic paths into canonical paths without mutating the original grouping
data.
"""

import hashlib
import logging
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from pymongo import MongoClient

TOPIC_PATH_SEPARATOR = " > "

AliasKey = Tuple[int, str, str]


def slugify(value: str) -> str:
    """Build a stable id segment, preserving non-ASCII (e.g. Cyrillic/CJK).

    Unicode letters/digits are kept so distinct non-ASCII labels don't all
    collapse to the same fallback. If a label has no alphanumeric characters at
    all (pure punctuation/emoji), a short content hash keeps ids unique.
    """
    normalized = unicodedata.normalize("NFKC", value or "").casefold().strip()
    slug = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE).strip("-_")
    if slug:
        return slug
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return f"topic-{digest}"


class RssTagTopicAliases:
    """Stores raw-label -> canonical-id mapping per (level, parent canonical)."""

    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger("topic_aliases")

    def prepare(self) -> None:
        try:
            self._db.topic_aliases.create_index(
                [
                    ("owner", 1),
                    ("level", 1),
                    ("parent_canonical_id", 1),
                    ("raw_label", 1),
                ],
                unique=True,
            )
            self._db.topic_aliases.create_index(
                [("owner", 1), ("level", 1), ("parent_canonical_id", 1)]
            )
            self._db.topic_aliases.create_index([("owner", 1), ("canonical_id", 1)])
        except Exception as e:
            self._log.warning(
                "Can't create topic_aliases indexes. May already exist. Info: %s", e
            )

    @staticmethod
    def split_path(topic_path: str) -> List[str]:
        return [
            part.strip()
            for part in str(topic_path).split(TOPIC_PATH_SEPARATOR)
            if part.strip()
        ]

    @staticmethod
    def make_canonical_id(parent_canonical_id: str, canonical_label: str) -> str:
        slug = slugify(canonical_label)
        if parent_canonical_id:
            return f"{parent_canonical_id}/{slug}"
        return slug

    def get_alias(
        self, owner: str, level: int, parent_canonical_id: str, raw_label: str
    ) -> Optional[Dict[str, Any]]:
        return self._db.topic_aliases.find_one(
            {
                "owner": owner,
                "level": level,
                "parent_canonical_id": parent_canonical_id,
                "raw_label": raw_label,
            }
        )

    def get_existing_canonicals(
        self, owner: str, level: int, parent_canonical_id: str
    ) -> List[Dict[str, str]]:
        """Distinct canonical (id, label) pairs already known in a bucket."""
        cursor = self._db.topic_aliases.find(
            {
                "owner": owner,
                "level": level,
                "parent_canonical_id": parent_canonical_id,
            },
            projection={"canonical_id": True, "canonical_label": True},
        )
        seen: Dict[str, str] = {}
        for doc in cursor:
            canonical_id = doc.get("canonical_id", "")
            if canonical_id and canonical_id not in seen:
                seen[canonical_id] = doc.get("canonical_label", "")
        return [
            {"canonical_id": canonical_id, "canonical_label": label}
            for canonical_id, label in seen.items()
        ]

    def upsert_alias(
        self,
        owner: str,
        level: int,
        parent_canonical_id: str,
        raw_label: str,
        canonical_id: str,
        canonical_label: str,
    ) -> None:
        self._db.topic_aliases.update_one(
            {
                "owner": owner,
                "level": level,
                "parent_canonical_id": parent_canonical_id,
                "raw_label": raw_label,
            },
            {
                "$set": {
                    "owner": owner,
                    "level": level,
                    "parent_canonical_id": parent_canonical_id,
                    "raw_label": raw_label,
                    "canonical_id": canonical_id,
                    "canonical_label": canonical_label,
                    "updated_at": time.time(),
                }
            },
            upsert=True,
        )

    def load_owner_map(self, owner: str) -> Dict[AliasKey, Dict[str, str]]:
        """Preload all aliases for an owner for batch path resolution."""
        result: Dict[AliasKey, Dict[str, str]] = {}
        for doc in self._db.topic_aliases.find({"owner": owner}):
            key: AliasKey = (
                int(doc.get("level", 0)),
                str(doc.get("parent_canonical_id", "")),
                str(doc.get("raw_label", "")),
            )
            result[key] = {
                "canonical_id": str(doc.get("canonical_id", "")),
                "canonical_label": str(doc.get("canonical_label", "")),
            }
        return result

    def resolve_path(
        self,
        topic_path: str,
        alias_map: Optional[Dict[AliasKey, Dict[str, str]]] = None,
        owner: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve a raw topic path into canonical ids/labels.

        Levels that have not been merged yet fall back to the raw label so
        callers keep working before / outside the merge task.
        """
        if alias_map is None:
            if owner is None:
                raise ValueError("resolve_path requires alias_map or owner")
            alias_map = self.load_owner_map(owner)

        labels = self.split_path(topic_path)
        canonical_ids: List[str] = []
        canonical_labels: List[str] = []
        parent_canonical_id = ""
        fully_resolved = True
        for level, raw_label in enumerate(labels):
            entry = alias_map.get((level, parent_canonical_id, raw_label))
            if entry:
                canonical_id = entry["canonical_id"]
                canonical_label = entry["canonical_label"]
            else:
                fully_resolved = False
                canonical_id = self.make_canonical_id(parent_canonical_id, raw_label)
                canonical_label = raw_label
            canonical_ids.append(canonical_id)
            canonical_labels.append(canonical_label)
            parent_canonical_id = canonical_id

        return {
            "canonical_id": parent_canonical_id,
            "canonical_ids": canonical_ids,
            "canonical_path": TOPIC_PATH_SEPARATOR.join(canonical_labels),
            "fully_resolved": fully_resolved,
        }
