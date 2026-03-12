"""Paths model — saved, deduplicated filter views."""

import hashlib
import json
import logging
import time
from copy import deepcopy
from typing import Any, Optional

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import pairwise_distances

from pymongo import ASCENDING, DESCENDING


class RssTagPaths:
    _RECOMMENDATION_DISTANCE_LIMIT: float = 0.4

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

    @staticmethod
    def _normalize_filter_value(dim: str, value: Any) -> Optional[Any]:
        if dim == "topics":
            return RssTagPaths._normalize_topic_value(value)

        normalized_value: str = str(value).strip()
        return normalized_value or None

    @staticmethod
    def _normalize_dimension_values(dim: str, values: list[Any]) -> list[Any]:
        normalized_values: list[Any] = []
        seen: set[str] = set()
        for value in values:
            normalized_value: Optional[Any] = RssTagPaths._normalize_filter_value(dim, value)
            if normalized_value is None:
                continue
            key: str = json.dumps(normalized_value, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            normalized_values.append(normalized_value)

        normalized_values.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return normalized_values

    @staticmethod
    def _build_similarity_matches(
        query: str, candidates: list[dict[str, Any]], distance_limit: float
    ) -> list[dict[str, Any]]:
        normalized_query: str = str(query).strip()
        candidate_labels: list[str] = [str(item.get("label", "")).strip() for item in candidates]
        if not normalized_query or not candidate_labels:
            return []

        vectorizer = CountVectorizer(ngram_range=(2, 2), analyzer="char")
        try:
            candidate_vectors = vectorizer.fit_transform(candidate_labels)
            query_vector = vectorizer.transform([normalized_query])
        except ValueError:
            return []

        distances = pairwise_distances(query_vector, candidate_vectors, metric="cosine")[0]
        matches: list[dict[str, Any]] = []
        for index, distance in enumerate(distances):
            if distance >= distance_limit:
                continue
            candidate = dict(candidates[index])
            candidate["score"] = round(1.0 - float(distance), 6)
            matches.append(candidate)

        matches.sort(
            key=lambda item: (
                -float(item.get("score", 0.0)),
                -int(item.get("popularity", 0)),
                str(item.get("label", "")),
            )
        )
        return matches

    def _collect_tag_inventory(self, owner: str) -> list[dict[str, Any]]:
        inventory: list[dict[str, Any]] = []
        cursor = self._db.tags.find(
            {"owner": owner},
            projection={"_id": 0, "tag": 1, "posts_count": 1},
        )
        for doc in cursor:
            tag: str = str(doc.get("tag", "")).strip()
            if not tag:
                continue
            inventory.append(
                {
                    "label": tag,
                    "value": tag,
                    "popularity": int(doc.get("posts_count", 0)),
                }
            )
        return inventory

    def _collect_topic_inventory(
        self, owner: str
    ) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
        exact_counts: dict[str, int] = {}
        level_counts: dict[int, dict[str, int]] = {}

        cursor = self._db.post_grouping.find(
            {"owner": owner},
            projection={"_id": 0, "groups": 1},
        )
        for doc in cursor:
            groups: Any = doc.get("groups", {})
            if not isinstance(groups, dict):
                continue
            for raw_topic in groups:
                normalized_topic: Optional[Any] = self._normalize_topic_value(raw_topic)
                if not isinstance(normalized_topic, str):
                    continue

                exact_counts[normalized_topic] = exact_counts.get(normalized_topic, 0) + 1
                for level, part in enumerate(
                    [item.strip() for item in normalized_topic.split(">") if item.strip()],
                    start=1,
                ):
                    if level not in level_counts:
                        level_counts[level] = {}
                    level_counts[level][part] = level_counts[level].get(part, 0) + 1

        exact_inventory: list[dict[str, Any]] = [
            {"label": topic, "value": topic, "popularity": count}
            for topic, count in exact_counts.items()
        ]
        level_inventory: dict[int, list[dict[str, Any]]] = {}
        for level, counts in level_counts.items():
            level_inventory[level] = [
                {"label": value, "value": value, "popularity": count}
                for value, count in counts.items()
            ]

        return exact_inventory, level_inventory

    def _build_recommendation_candidate(
        self,
        owner: str,
        content_type: str,
        current_filterset: dict[str, Any],
        exclude: dict[str, Any],
        dimension: str,
        operation: str,
        source_value: Any,
        suggested_value: Any,
        provider: str,
        score: float,
    ) -> Optional[dict[str, Any]]:
        candidate_filterset: dict[str, Any] = deepcopy(current_filterset)
        dimension_spec: Optional[dict[str, Any]] = candidate_filterset.get(dimension)
        if not isinstance(dimension_spec, dict):
            return None

        values: list[Any] = list(dimension_spec.get("values", []))
        current_values: list[Any] = self._normalize_dimension_values(dimension, values)
        if not current_values:
            return None

        normalized_source: Optional[Any] = self._normalize_filter_value(dimension, source_value)
        normalized_suggested: Optional[Any] = self._normalize_filter_value(dimension, suggested_value)
        if normalized_source is None or normalized_suggested is None:
            return None

        if operation == "replace":
            updated_values: list[Any] = []
            replaced: bool = False
            for value in current_values:
                if not replaced and json.dumps(value, sort_keys=True) == json.dumps(
                    normalized_source, sort_keys=True
                ):
                    updated_values.append(normalized_suggested)
                    replaced = True
                else:
                    updated_values.append(value)
            if not replaced:
                return None
        elif operation == "add":
            updated_values = list(current_values)
            if any(
                json.dumps(value, sort_keys=True) == json.dumps(normalized_suggested, sort_keys=True)
                for value in updated_values
            ):
                return None
            updated_values.append(normalized_suggested)
        else:
            return None

        updated_values = self._normalize_dimension_values(dimension, updated_values)
        if updated_values == current_values:
            return None

        dimension_spec["values"] = updated_values
        candidate_filterset = self._canonicalize(candidate_filterset)
        canonical_exclude: dict[str, Any] = self._canonicalize(exclude or {})
        suggestion_id: str = self.compute_path_id(
            owner, content_type, candidate_filterset, canonical_exclude
        )

        return {
            "suggestion_id": suggestion_id,
            "content_type": content_type,
            "filterset": candidate_filterset,
            "exclude": canonical_exclude,
            "score": round(float(score), 6),
            "source_value": normalized_source,
            "suggested_value": normalized_suggested,
            "provider": provider,
        }

    def _merge_group_items(
        self,
        grouped_items: dict[str, dict[str, Any]],
        group_id: str,
        item: dict[str, Any],
        popularity: int,
    ) -> None:
        group = grouped_items.setdefault(group_id, {})
        suggestion_id: str = str(item.get("suggestion_id", "")).strip()
        if not suggestion_id:
            return

        current: Optional[dict[str, Any]] = group.get(suggestion_id)
        payload: dict[str, Any] = dict(item)
        payload["popularity"] = int(popularity)
        if current is None or (
            float(payload.get("score", 0.0)),
            int(payload.get("popularity", 0)),
        ) > (
            float(current.get("score", 0.0)),
            int(current.get("popularity", 0)),
        ):
            group[suggestion_id] = payload

    def _collect_tag_recommendations(
        self,
        owner: str,
        content_type: str,
        current_filterset: dict[str, Any],
        exclude: dict[str, Any],
        limit_per_group: int,
    ) -> dict[str, list[dict[str, Any]]]:
        spec: Any = current_filterset.get("tags", {})
        if not isinstance(spec, dict):
            return {}

        current_tags: list[Any] = self._normalize_dimension_values("tags", spec.get("values", []))
        if not current_tags:
            return {}

        inventory = self._collect_tag_inventory(owner)
        current_keys = {json.dumps(value, sort_keys=True) for value in current_tags}
        groups: dict[str, dict[str, Any]] = {
            "tags_replace": {},
            "tags_add": {},
        }
        for tag in current_tags:
            tag_candidates = [
                item
                for item in inventory
                if json.dumps(item.get("value"), sort_keys=True) not in current_keys
            ]
            for match in self._build_similarity_matches(
                str(tag), tag_candidates, self._RECOMMENDATION_DISTANCE_LIMIT
            ):
                replace_item = self._build_recommendation_candidate(
                    owner=owner,
                    content_type=content_type,
                    current_filterset=current_filterset,
                    exclude=exclude,
                    dimension="tags",
                    operation="replace",
                    source_value=tag,
                    suggested_value=match["value"],
                    provider="similar_tags",
                    score=float(match["score"]),
                )
                if replace_item:
                    self._merge_group_items(
                        groups, "tags_replace", replace_item, int(match.get("popularity", 0))
                    )

                add_item = self._build_recommendation_candidate(
                    owner=owner,
                    content_type=content_type,
                    current_filterset=current_filterset,
                    exclude=exclude,
                    dimension="tags",
                    operation="add",
                    source_value=tag,
                    suggested_value=match["value"],
                    provider="similar_tags",
                    score=float(match["score"]),
                )
                if add_item:
                    self._merge_group_items(
                        groups, "tags_add", add_item, int(match.get("popularity", 0))
                    )

        finalized: dict[str, list[dict[str, Any]]] = {}
        for group_id, items in groups.items():
            ordered = sorted(
                items.values(),
                key=lambda item: (
                    -float(item.get("score", 0.0)),
                    -int(item.get("popularity", 0)),
                    str(item.get("suggestion_id", "")),
                ),
            )
            if ordered:
                finalized[group_id] = ordered[:limit_per_group]
        return finalized

    def _collect_topic_recommendations(
        self,
        owner: str,
        content_type: str,
        current_filterset: dict[str, Any],
        exclude: dict[str, Any],
        limit_per_group: int,
    ) -> dict[str, list[dict[str, Any]]]:
        spec: Any = current_filterset.get("topics", {})
        if not isinstance(spec, dict):
            return {}

        current_topics: list[Any] = self._normalize_dimension_values("topics", spec.get("values", []))
        if not current_topics:
            return {}

        exact_inventory, level_inventory = self._collect_topic_inventory(owner)
        current_keys = {json.dumps(value, sort_keys=True) for value in current_topics}
        groups: dict[str, dict[str, Any]] = {
            "topics_replace": {},
            "topics_add": {},
        }

        for topic in current_topics:
            if isinstance(topic, str):
                topic_candidates = [
                    item
                    for item in exact_inventory
                    if json.dumps(item.get("value"), sort_keys=True) not in current_keys
                ]
                suggested_values: list[tuple[Any, dict[str, Any]]] = [
                    (match["value"], match)
                    for match in self._build_similarity_matches(
                        topic, topic_candidates, self._RECOMMENDATION_DISTANCE_LIMIT
                    )
                ]
            elif isinstance(topic, dict) and topic.get("mode") == "level":
                level: int = int(topic["level"])
                value: str = str(topic.get("value", "")).strip()
                level_candidates = [
                    item
                    for item in level_inventory.get(level, [])
                    if json.dumps(
                        {"mode": "level", "level": level, "value": item.get("value")},
                        sort_keys=True,
                    )
                    not in current_keys
                ]
                suggested_values = [
                    (
                        {"mode": "level", "level": level, "value": match["value"]},
                        match,
                    )
                    for match in self._build_similarity_matches(
                        value, level_candidates, self._RECOMMENDATION_DISTANCE_LIMIT
                    )
                ]
            else:
                continue

            for suggested_value, match in suggested_values:
                replace_item = self._build_recommendation_candidate(
                    owner=owner,
                    content_type=content_type,
                    current_filterset=current_filterset,
                    exclude=exclude,
                    dimension="topics",
                    operation="replace",
                    source_value=topic,
                    suggested_value=suggested_value,
                    provider="similar_topics",
                    score=float(match["score"]),
                )
                if replace_item:
                    self._merge_group_items(
                        groups,
                        "topics_replace",
                        replace_item,
                        int(match.get("popularity", 0)),
                    )

                add_item = self._build_recommendation_candidate(
                    owner=owner,
                    content_type=content_type,
                    current_filterset=current_filterset,
                    exclude=exclude,
                    dimension="topics",
                    operation="add",
                    source_value=topic,
                    suggested_value=suggested_value,
                    provider="similar_topics",
                    score=float(match["score"]),
                )
                if add_item:
                    self._merge_group_items(
                        groups,
                        "topics_add",
                        add_item,
                        int(match.get("popularity", 0)),
                    )

        finalized: dict[str, list[dict[str, Any]]] = {}
        for group_id, items in groups.items():
            ordered = sorted(
                items.values(),
                key=lambda item: (
                    -float(item.get("score", 0.0)),
                    -int(item.get("popularity", 0)),
                    str(item.get("suggestion_id", "")),
                ),
            )
            if ordered:
                finalized[group_id] = ordered[:limit_per_group]
        return finalized

    def get_recommendations(
        self, owner: str, path_doc: dict[str, Any], limit_per_group: int = 5
    ) -> list[dict[str, Any]]:
        if not isinstance(path_doc, dict):
            return []

        content_type: str = str(path_doc.get("content_type", "sentences")).strip() or "sentences"
        current_filterset: dict[str, Any] = self._canonicalize(path_doc.get("filterset", {}))
        exclude: dict[str, Any] = self._canonicalize(path_doc.get("exclude", {}))
        if not current_filterset:
            return []

        grouped_results: dict[str, list[dict[str, Any]]] = {}
        for collector in (self._collect_tag_recommendations, self._collect_topic_recommendations):
            try:
                grouped_results.update(
                    collector(owner, content_type, current_filterset, exclude, limit_per_group)
                )
            except Exception as e:
                self._log.error("Error collecting path recommendations: %s", e)

        group_meta: dict[str, tuple[str, str, str]] = {
            "tags_replace": ("Replace Tag", "tags", "replace"),
            "tags_add": ("Add Tag", "tags", "add"),
            "topics_replace": ("Replace Topic", "topics", "replace"),
            "topics_add": ("Add Topic", "topics", "add"),
        }
        groups: list[dict[str, Any]] = []
        for group_id in ("tags_replace", "tags_add", "topics_replace", "topics_add"):
            items = grouped_results.get(group_id, [])
            if not items:
                continue
            title, dimension, operation = group_meta[group_id]
            cleaned_items = []
            for item in items:
                cleaned = dict(item)
                cleaned.pop("popularity", None)
                cleaned_items.append(cleaned)
            groups.append(
                {
                    "id": group_id,
                    "title": title,
                    "dimension": dimension,
                    "operation": operation,
                    "items": cleaned_items,
                }
            )

        return groups
