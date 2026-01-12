from abc import ABC, abstractmethod
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

    def set_filter(self, context_filter: ContextFilter) -> None:
        self._filters[context_filter.filter_type] = context_filter

    def get_combined_query(self, owner: str) -> Dict[str, Any]:
        """Combine all active filters into a single MongoDB query.

        For tags, this merges $all arrays so all context tags must match.
        """
        combined = {}
        for f in self._filters.values():
            if f.is_active():
                query_part = f.get_filter_query(owner)
                for key, value in query_part.items():
                    if key == "tags" and "$all" in value:
                        if key in combined and "$all" in combined[key]:
                            # Extend existing $all array
                            combined[key]["$all"].extend(value["$all"])
                        else:
                            combined[key] = value
                    elif key not in combined:
                        combined[key] = value
        return combined

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
            # Future: add more filter types here
        return cls(filters)
