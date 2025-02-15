import re

TEXT_CLEAN_RE = re.compile(r"[^\w\d ]")

def text2words(text: str) -> list[str]:
    """Make words list from text"""
    text = TEXT_CLEAN_RE.sub(" ", text)
    text = text.strip().casefold()
    words = [w.strip() for w in text.split()]

    return words

class PrefixTreeBuilder:
    def __init__(self):
        self.tree = {}

    def add_words_from_doc(self, text: str):
        words = text2words(text)
        for word in words:
            self._add_word(word)

    def _add_word(self, word: str):
        current = self.tree
        for char in word:
            if char not in current:
                current[char] = {'count': 0, 'children': {}}
            current = current[char]['children']
            current['count'] = current.get('count', 0) + 1

    def __str__(self) -> str:
        def _format_node(node: dict[str, dict], indent=0) -> list[str]:
            result = []
            for char, child in sorted(node.items()):
                if char == 'count':
                    continue
                count = child['children'].get('count', 0)
                result.append(" " * indent + f"{char} ({count})")
                result.extend(_format_node(child['children'], indent + 2))

            return result
        
        return "\n".join(_format_node(self.tree))

    def _has_single_path(self, node: dict[str, dict]) -> tuple[bool, str]:
        """Check if node has only one possible path down the tree.
        Returns (is_single_path, collected_chars)"""
        path = ""
        while True:
            # Count non-count children
            children = [(k, v) for k, v in node.items() if k != 'count']
            if not children:  # End of branch
                return (True, path)
            if len(children) != 1:
                return (False, path)
            char, child = children[0]
            path += char
            node = child['children']

    def get_top_n(self, n: int) -> list[tuple[str, int]]:
        """Get the most frequent prefixes of length n.
        Returns list of tuples (prefix, count) sorted by count in descending order."""
        def collect_prefix_counts(node: dict, prefix: str = "", length: int = n) -> list[tuple[str, int]]:
            if len(prefix) == length:
                return [(prefix, node.get('count', 0))]
            
            results = []
            for char, child in node.items():
                if char != 'count':
                    results.extend(collect_prefix_counts(child['children'], prefix + char, length))
                    
            return results

        prefixes = collect_prefix_counts(self.tree)

        return sorted(prefixes, key=lambda x: x[1], reverse=True)

    def get_tails(self, prefix: str) -> list[str]:
        """Get all tails for the prefix"""
        # Navigate to the node corresponding to the prefix
        current = self.tree
        for char in prefix:
            if char not in current:
                return []
            current = current[char]['children']

        # Check if we have a single path from this point
        is_single, path = self._has_single_path(current)
        if is_single:
            return [prefix + path]

        words = []
        def collect_tails(node, tail="") -> None:
            children = [(k, v) for k, v in node.items() if k != 'count']
            if not children and node.get('count', 0) > 0:  # Only collect leaf nodes
                words.append(prefix + tail)
            for char, child in children:
                collect_tails(child['children'], tail + char)

        collect_tails(current)

        return words

    def get_tree(self, prefix: str) -> dict:
        """Get subtree in sunburst format starting from the given prefix.
        Returns dict with format: {"name": str, "value": int, "children": list}
        Returns None if prefix not found."""
        # Navigate to the prefix node
        current = self.tree
        for char in prefix:
            if char not in current:
                return None
            current = current[char]['children']

        def build_subtree(node: dict, name: str = "") -> dict:
            result = {
                "name": name,
                "value": node.get('count', 0),
            }
            
            children = []
            for char, child in node.items():
                if char != 'count':
                    child_tree = build_subtree(child['children'], char)
                    if child_tree.get('value', 0) > 0:
                        children.append(child_tree)
            
            if children:
                children.sort(key=lambda x: x['value'], reverse=True)
                result['children'] = children
            
            return result

        return build_subtree(current, prefix)

    def _get_single_path_node(self, node: dict, path: str) -> tuple[dict, int]:
        """Follow path to the end node and return (end_node, count)"""
        current = node
        for char in path:
            current = current[char]['children']
        return current, current.get('count', 0)

    def get_compact_tree(self, prefix: str) -> dict:
        """Get subtree in sunburst format starting from the given prefix,
        joining single-path segments into words at every possible level.
        Returns dict with format: {"name": str, "value": int, "children": list}
        Returns None if prefix not found."""
        # Navigate to the prefix node
        current = self.tree
        for char in prefix:
            if char not in current:
                return None
            current = current[char]['children']

        def build_compact_subtree(node: dict, name: str = "") -> dict:
            children = []
            node_value = node.get('count', 0)
            
            # Get all non-count children
            child_items = [(k, v) for k, v in node.items() if k != 'count']
            
            # If no children, return current node
            if not child_items:
                return {"name": name, "value": node_value}
            
            # Process children
            for char, child in child_items:
                # Check if this child has a single path
                is_single, path = self._has_single_path(child['children'])
                if is_single and path:
                    # Get the end node of the single path
                    end_node, count = self._get_single_path_node(child['children'], path)
                    child_name = char + path
                    child_tree = build_compact_subtree(end_node, child_name)
                else:
                    # Process normally if no single path
                    child_tree = build_compact_subtree(child['children'], char)
                
                if child_tree.get('value', 0) > 0:
                    children.append(child_tree)
            
            # If we have only one child, merge it with current node
            if len(children) == 1:
                child = children[0]
                return {
                    "name": name + child["name"],
                    "value": child["value"],
                    "children": child.get("children", []) if "children" in child else None
                }
            
            # Multiple children case
            result = {"name": name, "value": node_value}
            if children:
                children.sort(key=lambda x: x['value'], reverse=True)
                result['children'] = children
            
            return result

        return build_compact_subtree(current, prefix)