from abc import ABC, abstractmethod
import re
from typing import List, Dict, Any, Optional


class ContextFilter(ABC):
    """Abstract base class for context filters.

    Future implementations could include:
    - EmbeddingsContextFilter: Filter by semantic similarity
    - UserCommentsContextFilter: Filter posts user commented on
    - DateRangeContextFilter: Filter by date range
    """

    @property
    @abstractmethod
    def filter_type(self) -> str:
        """Return filter type identifier (e.g., 'tags', 'embeddings')"""
        pass

    @abstractmethod
    def get_filter_query(self, owner: str) -> Dict[str, Any]:
        """Return MongoDB query fragment for this filter"""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Check if this filter is currently active"""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize filter state for storage"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextFilter":
        """Deserialize filter from stored data"""
        pass


class TagContextFilter(ContextFilter):
    """POC: Context filter based on tags with AND logic."""

    def __init__(self, tags: Optional[List[str]] = None):
        self._tags = tags or []

    @property
    def filter_type(self) -> str:
        return "tags"

    @property
    def tags(self) -> List[str]:
        return self._tags.copy()

    def add_tag(self, tag: str) -> bool:
        """Add tag if not already present. Returns True if added."""
        if tag and tag not in self._tags:
            self._tags.append(tag)
            return True
        return False

    def remove_tag(self, tag: str) -> bool:
        """Remove tag if present. Returns True if removed."""
        if tag in self._tags:
            self._tags.remove(tag)
            return True
        return False

    def clear(self) -> None:
        self._tags = []

    def get_filter_query(self, owner: str) -> Dict[str, Any]:
        """Return MongoDB query for posts matching ALL context tags."""
        if not self._tags:
            return {}
        return {"tags": {"$all": self._tags}}

    def is_active(self) -> bool:
        return len(self._tags) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.filter_type, "tags": self._tags}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TagContextFilter":
        return cls(tags=data.get("tags", []))


def _normalize_id_list(values: Optional[List[Any]]) -> List[str]:
    normalized: List[str] = []
    for value in values or []:
        normalized_value = str(value).strip()
        if normalized_value and normalized_value not in normalized:
            normalized.append(normalized_value)
    return normalized


def _normalize_topic_path(path: Optional[str]) -> str:
    if not path:
        return ""
    parts = [part.strip() for part in str(path).split(">") if part.strip()]
    return " > ".join(parts)


def _topic_prefix_regex(path: str) -> str:
    parts = [re.escape(part) for part in _normalize_topic_path(path).split(" > ") if part]
    if not parts:
        return ""
    joined = r"\s*>\s*".join(parts)
    return rf"^{joined}(?:\s*>\s*.*)?$"


class FeedContextFilter(ContextFilter):
    def __init__(self, feed_ids: Optional[List[Any]] = None):
        self._feed_ids = _normalize_id_list(feed_ids)

    @property
    def filter_type(self) -> str:
        return "feeds"

    @property
    def feed_ids(self) -> List[str]:
        return self._feed_ids.copy()

    def get_filter_query(self, owner: str) -> Dict[str, Any]:
        if not self._feed_ids:
            return {}
        if len(self._feed_ids) == 1:
            return {"feed_id": self._feed_ids[0]}
        return {"feed_id": {"$in": self._feed_ids}}

    def is_active(self) -> bool:
        return len(self._feed_ids) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.filter_type, "feed_ids": self._feed_ids}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedContextFilter":
        feed_ids = data.get("feed_ids")
        if feed_ids is None and data.get("feed_id"):
            feed_ids = [data.get("feed_id")]
        return cls(feed_ids=feed_ids)


class CategoryContextFilter(ContextFilter):
    def __init__(self, category_ids: Optional[List[Any]] = None):
        self._category_ids = _normalize_id_list(category_ids)

    @property
    def filter_type(self) -> str:
        return "categories"

    @property
    def category_ids(self) -> List[str]:
        return self._category_ids.copy()

    def get_filter_query(self, owner: str) -> Dict[str, Any]:
        if not self._category_ids:
            return {}
        if len(self._category_ids) == 1:
            return {"category_id": self._category_ids[0]}
        return {"category_id": {"$in": self._category_ids}}

    def is_active(self) -> bool:
        return len(self._category_ids) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.filter_type, "category_ids": self._category_ids}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CategoryContextFilter":
        category_ids = data.get("category_ids")
        if category_ids is None and data.get("category_id"):
            category_ids = [data.get("category_id")]
        return cls(category_ids=category_ids)


class TopicContextFilter(ContextFilter):
    def __init__(self, topic_path: Optional[str] = None):
        self._topic_path = _normalize_topic_path(topic_path)

    @property
    def filter_type(self) -> str:
        return "topic"

    @property
    def topic_path(self) -> str:
        return self._topic_path

    def get_filter_query(self, owner: str) -> Dict[str, Any]:
        if not self._topic_path:
            return {}
        return {"topic": {"$regex": _topic_prefix_regex(self._topic_path)}}

    def is_active(self) -> bool:
        return bool(self._topic_path)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.filter_type, "topic_path": self._topic_path}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TopicContextFilter":
        return cls(topic_path=data.get("topic_path") or data.get("topic"))


class SubtopicContextFilter(ContextFilter):
    def __init__(
        self,
        topic_path: Optional[str] = None,
        parent_topic_path: Optional[str] = None,
        node: Optional[str] = None,
    ):
        self._topic_path = _normalize_topic_path(topic_path)
        self._parent_topic_path = _normalize_topic_path(parent_topic_path)
        self._node = str(node or "").strip()

    @property
    def filter_type(self) -> str:
        return "subtopic"

    @property
    def topic_path(self) -> str:
        if self._topic_path:
            return self._topic_path
        if self._parent_topic_path and self._node:
            return _normalize_topic_path(f"{self._parent_topic_path} > {self._node}")
        return ""

    def get_filter_query(self, owner: str) -> Dict[str, Any]:
        if not self.topic_path:
            return {}
        return {"topic": {"$regex": _topic_prefix_regex(self.topic_path)}}

    def is_active(self) -> bool:
        return bool(self.topic_path)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.filter_type,
            "topic_path": self._topic_path,
            "parent_topic_path": self._parent_topic_path,
            "node": self._node,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtopicContextFilter":
        return cls(
            topic_path=data.get("topic_path") or data.get("subtopic_path"),
            parent_topic_path=data.get("parent_topic_path"),
            node=data.get("node") or data.get("subtopic_node"),
        )


class ContextFilterManager:
    """Manages multiple context filters for a user session."""

    def __init__(self, filters: Optional[Dict[str, ContextFilter]] = None):
        self._filters = filters or {}

    def get_filter(self, filter_type: str) -> Optional[ContextFilter]:
        return self._filters.get(filter_type)

    def get_tag_filter(self) -> TagContextFilter:
        """Convenience method - get or create TagContextFilter."""
        f = self._filters.get("tags")
        if not f:
            f = TagContextFilter()
            self._filters["tags"] = f
        return f

    def get_feed_filter(self) -> FeedContextFilter:
        f = self._filters.get("feeds")
        if not f:
            f = FeedContextFilter()
            self._filters["feeds"] = f
        return f

    def get_category_filter(self) -> CategoryContextFilter:
        f = self._filters.get("categories")
        if not f:
            f = CategoryContextFilter()
            self._filters["categories"] = f
        return f

    def get_topic_filter(self) -> TopicContextFilter:
        f = self._filters.get("topic")
        if not f:
            f = TopicContextFilter()
            self._filters["topic"] = f
        return f

    def get_subtopic_filter(self) -> SubtopicContextFilter:
        f = self._filters.get("subtopic")
        if not f:
            f = SubtopicContextFilter()
            self._filters["subtopic"] = f
        return f

    def set_filter(self, context_filter: ContextFilter) -> None:
        self._filters[context_filter.filter_type] = context_filter

    def get_combined_query(self, owner: str) -> Dict[str, Any]:
        """Combine all active filters into a single MongoDB query.

        For tags, this merges $all arrays so all context tags must match.
        """
        clauses: List[Dict[str, Any]] = [{"owner": owner}]
        merged_tags: List[str] = []
        for f in self._filters.values():
            if f.is_active():
                query_part = f.get_filter_query(owner)
                if not query_part:
                    continue
                if "tags" in query_part and isinstance(query_part["tags"], dict):
                    tag_clause = query_part.get("tags", {})
                    if "$all" in tag_clause:
                        for tag in tag_clause["$all"]:
                            if tag not in merged_tags:
                                merged_tags.append(tag)
                        query_part = {k: v for k, v in query_part.items() if k != "tags"}
                if query_part:
                    clauses.append(query_part)

        if merged_tags:
            clauses.append({"tags": {"$all": merged_tags}})

        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def has_active_filters(self) -> bool:
        return any(f.is_active() for f in self._filters.values())

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() for k, v in self._filters.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextFilterManager":
        filters = {}
        if not data:
            return cls(filters)
        for filter_type, filter_data in data.items():
            if filter_type == "tags":
                filters[filter_type] = TagContextFilter.from_dict(filter_data)
            elif filter_type == "feeds":
                filters[filter_type] = FeedContextFilter.from_dict(filter_data)
            elif filter_type == "categories":
                filters[filter_type] = CategoryContextFilter.from_dict(filter_data)
            elif filter_type == "topic":
                filters[filter_type] = TopicContextFilter.from_dict(filter_data)
            elif filter_type == "subtopic":
                filters[filter_type] = SubtopicContextFilter.from_dict(filter_data)
        return cls(filters)
