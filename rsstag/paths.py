"""Paths model — saved, deduplicated filter views."""

import hashlib
import json
import logging
import time
from typing import Any, Optional

from pymongo import ASCENDING, DESCENDING


class RssTagPaths:
    def __init__(self, db) -> None:
        self._db = db
        self._log = logging.getLogger("paths")

    def prepare(self) -> None:
        try:
            self._db.paths.create_index([("owner", ASCENDING)])
        except Exception as e:
            self._log.warning("Can't create paths index owner. Info: %s", e)
        try:
            self._db.paths.create_index(
                [("owner", ASCENDING), ("path_id", ASCENDING)], unique=True
            )
        except Exception as e:
            self._log.warning("Can't create paths compound index. Info: %s", e)

    @staticmethod
    def _normalize_topic_value(value: Any) -> Optional[Any]:
        """Normalize a stored topic filter value for hashing and comparison."""
        if isinstance(value, str):
            normalized: str = " > ".join(
                part.strip() for part in value.split(">") if part.strip()
            )
            return normalized or None

        if not isinstance(value, dict):
            return None

        mode: str = str(value.get("mode", "")).strip()
        if mode == "level":
            try:
                level: int = int(value.get("level"))
            except (TypeError, ValueError):
                return None
            normalized_value: str = str(value.get("value", "")).strip()
            if level <= 0 or not normalized_value:
                return None
            return {"mode": "level", "level": level, "value": normalized_value}

        if mode == "topic":
            normalized_topic: str = " > ".join(
                part.strip() for part in str(value.get("topic", "")).split(">") if part.strip()
            )
            return normalized_topic or None

        return None

    @staticmethod
    def _canonicalize(d: dict) -> dict:
        """Sort keys and values within each dimension; normalize topic paths."""
        result: dict[str, dict[str, Any]] = {}
        for dim in sorted(d.keys()):
            spec: dict[str, Any] = d[dim]
            values: list[Any] = []
            for value in spec.get("values", []):
                if dim == "topics":
                    normalized_topic_value: Optional[Any] = RssTagPaths._normalize_topic_value(
                        value
                    )
                    if normalized_topic_value is None:
                        continue
                    values.append(normalized_topic_value)
                    continue

                normalized_value: str = str(value).strip()
                if normalized_value:
                    values.append(normalized_value)

            values = sorted(values, key=lambda value: json.dumps(value, sort_keys=True))
            result[dim] = {"values": values, "logic": spec.get("logic", "and")}
        return result

    @staticmethod
    def compute_path_id(
        owner: str,
        content_type: str,
        filterset: dict,
        exclude: Optional[dict] = None,
    ) -> str:
        canon_filterset = RssTagPaths._canonicalize(filterset or {})
        canon_exclude = RssTagPaths._canonicalize(exclude or {})
        payload = json.dumps(
            {
                "owner": owner,
                "content_type": content_type,
                "filterset": canon_filterset,
                "exclude": canon_exclude,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def create_or_get(
        self,
        owner: str,
        content_type: str,
        filterset: dict,
        exclude: Optional[dict],
        title: str,
    ) -> Optional[dict]:
        try:
            path_id = self.compute_path_id(owner, content_type, filterset, exclude or {})
            now = time.time()
            doc = {
                "path_id": path_id,
                "owner": owner,
                "content_type": content_type,
                "title": title,
                "filterset": filterset,
                "exclude": exclude or {},
                "created_at": now,
                "updated_at": now,
            }
            self._db.paths.update_one(
                {"owner": owner, "path_id": path_id},
                {"$setOnInsert": doc},
                upsert=True,
            )
            return self._db.paths.find_one(
                {"owner": owner, "path_id": path_id}, {"_id": 0}
            )
        except Exception as e:
            self._log.error("Error creating/getting path: %s", e)
            return None

    def get_by_path_id(self, owner: str, path_id: str) -> Optional[dict]:
        try:
            return self._db.paths.find_one(
                {"owner": owner, "path_id": path_id}, {"_id": 0}
            )
        except Exception as e:
            self._log.error("Error getting path %s: %s", path_id, e)
            return None

    def list_paths(self, owner: str, limit: int = 50, skip: int = 0) -> list:
        try:
            cursor = (
                self._db.paths.find({"owner": owner}, {"_id": 0})
                .sort("updated_at", DESCENDING)
                .skip(skip)
                .limit(limit)
            )
            return list(cursor)
        except Exception as e:
            self._log.error("Error listing paths: %s", e)
            return []

    def update(self, owner: str, path_id: str, updates: dict) -> bool:
        try:
            updates["updated_at"] = time.time()
            result = self._db.paths.update_one(
                {"owner": owner, "path_id": path_id},
                {"$set": updates},
            )
            return result.modified_count > 0
        except Exception as e:
            self._log.error("Error updating path %s: %s", path_id, e)
            return False

    def delete(self, owner: str, path_id: str) -> bool:
        try:
            result = self._db.paths.delete_one({"owner": owner, "path_id": path_id})
            return result.deleted_count > 0
        except Exception as e:
            self._log.error("Error deleting path %s: %s", path_id, e)
            return False
