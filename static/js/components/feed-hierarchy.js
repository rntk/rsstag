/* global document, window */

/**
 * Feed Hierarchy page (/hierarchy)
 *
 * Vanilla-JS rendering of a topic hierarchy tree built from a flat list of
 * topics whose `name` encodes a path ("A > B > C"). Mirrors the behaviour of
 * the React HierarchyApp/TopicHierarchyView components (see /app/ext/src/hierarchy)
 * but intentionally skips summaries, YouTube links and record/status states —
 * this page only ever renders the topic tree for a feed.
 *
 * Matches the vanilla component style used elsewhere in this codebase
 * (components/feed-canvas.js, topics-hierarchy.js).
 */

/**
 * @typedef {{name: string, posts_count?: number, sentences_count?: number}} Topic
 * @typedef {{name: string, fullPath: string, uid: string, depth: number, topic: Topic|null}} TreeNode
 * @typedef {{node: TreeNode, children: Map<string, TreeEntry>, parent: TreeEntry|null, leafCount: number}} TreeEntry
 */

/**
 * Build a nested tree from a flat list of topics whose `name` encodes a
 * hierarchy path ("A > B > C"). Returns an array of root tree entries.
 *
 * Each entry: { node, children: Map<string, entry>, parent, leafCount }
 * node: { name, fullPath, uid, depth, topic }
 * `fullPath` joins parts with ">" (no spaces) to match the color helpers.
 *
 * @param {Topic[]} topics
 * @param {number} [startDepth]
 * @returns {TreeEntry[]}
 */
export function buildTopicTree(topics, startDepth = 0) {
  const roots = new Map();

  for (const topic of Array.isArray(topics) ? topics : []) {
    const parts = String(topic?.name || '')
      .split('>')
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length <= startDepth) continue;

    let level = roots;
    let parent = null;
    for (let i = startDepth; i < parts.length; i += 1) {
      const name = parts[i];
      const fullPath = parts.slice(0, i + 1).join('>');
      let entry = level.get(name);
      if (!entry) {
        entry = {
          node: { name, fullPath, uid: fullPath, depth: i, topic: null },
          children: new Map(),
          parent,
        };
        level.set(name, entry);
      }
      if (i === parts.length - 1) {
        entry.node.topic = topic;
      }
      parent = entry;
      level = entry.children;
    }
  }

  const rootEntries = Array.from(roots.values());
  rootEntries.forEach(computeLeafCount);
  return rootEntries;
}

/** @param {TreeEntry} entry @returns {number} */
function computeLeafCount(entry) {
  const children = Array.from(entry.children.values());
  if (children.length === 0) {
    entry.leafCount = 1;
    return entry.leafCount;
  }
  entry.leafCount = children.reduce((total, child) => total + computeLeafCount(child), 0);
  return entry.leafCount;
}

/**
 * Calculate the deepest zero-based level among the supplied topics.
 *
 * @param {Topic[]} topics
 * @returns {number}
 */
export function getMaxTopicLevel(topics) {
  if (!Array.isArray(topics) || topics.length === 0) return 0;
  let max = 0;
  for (const topic of topics) {
    const parts = String(topic?.name || '')
      .split('>')
      .map((part) => part.trim())
      .filter(Boolean);
    const depth = parts.length - 1;
    if (depth > max) max = depth;
  }
  return Math.max(0, max);
}

/**
 * Collect the `fullPath` of every non-leaf (branch) node in a topic tree, in
 * pre-order. Optionally restrict to nodes at or below a minimum depth so
 * callers can fold the tree down to a chosen level: collapsing every branch
 * with `depth >= minDepth` hides everything deeper while leaving levels
 * above intact.
 *
 * @param {TreeEntry[]} roots
 * @param {{minDepth?: number}} [options]
 * @returns {string[]}
 */
export function collectNonLeafPaths(roots, { minDepth = 0 } = {}) {
  const paths = [];
  const traverse = (entry) => {
    const children = Array.from(entry.children.values());
    if (children.length === 0) return;
    if (entry.node.depth >= minDepth) {
      paths.push(entry.node.fullPath);
    }
    children.forEach(traverse);
  };
  (Array.isArray(roots) ? roots : []).forEach(traverse);
  return paths;
}

/**
 * Non-negative integer hash of a string (djb2-ish, matches topics-hierarchy.js).
 * @param {string} value
 * @returns {number}
 */
export function hashString(value) {
  let hash = 0;
  const input = String(value || '');
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

/**
 * Light background color for a hierarchy node: all descendants of the same
 * root share a hue; saturation/lightness shift by depth for a gradient effect.
 * @param {string} rootName
 * @param {number} depth
 * @returns {string}
 */
export function highlightColor(rootName, depth) {
  const hue = hashString(rootName) % 360;
  const saturation = Math.max(25, 55 - depth * 7);
  const lightness = Math.min(94, 78 + depth * 4);
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

/**
 * Accent (border) color for a hierarchy node.
 * @param {string} rootName
 * @param {number} depth
 * @returns {string}
 */
export function accentColor(rootName, depth) {
  const hue = hashString(rootName) % 360;
  const saturation = Math.max(30, 60 - depth * 6);
  const lightness = Math.min(62, 38 + depth * 6);
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

/**
 * Small badge text for a leaf topic card, e.g. "3 posts · 12 sentences".
 * @param {Topic|null|undefined} topic
 * @returns {string}
 */
export function formatLeafMeta(topic) {
  const posts = Number.isFinite(topic?.posts_count) ? topic.posts_count : 0;
  const sentences = Number.isFinite(topic?.sentences_count) ? topic.sentences_count : 0;
  const postsLabel = posts === 1 ? 'post' : 'posts';
  const sentencesLabel = sentences === 1 ? 'sentence' : 'sentences';
  return `${posts} ${postsLabel} · ${sentences} ${sentencesLabel}`;
}

/**
 * Build the DOM for a single leaf topic card.
 * @param {TreeEntry} entry
 * @param {string} rootName
 * @returns {HTMLElement}
 */
function buildLeafElement(entry, rootName) {
  const { node } = entry;
  const leaf = document.createElement('div');
  leaf.className = 'fh-leaf';
  leaf.style.setProperty('--fh-accent-color', accentColor(rootName, node.depth));
  leaf.style.setProperty('--fh-card-bg', highlightColor(rootName, node.depth));
  leaf.title = node.fullPath.replace(/>/g, ' ');

  const label = document.createElement('span');
  label.className = 'fh-leaf__label';
  label.textContent = node.name;
  leaf.appendChild(label);

  const meta = document.createElement('span');
  meta.className = 'fh-leaf__meta';
  meta.textContent = formatLeafMeta(node.topic);
  leaf.appendChild(meta);

  return leaf;
}

/**
 * Build the DOM for a branch node (and, recursively, its children when
 * expanded).
 * @param {TreeEntry} entry
 * @param {string} rootName
 * @param {Set<string>} collapsedPaths
 * @param {(fullPath: string) => void} onToggle
 * @returns {HTMLElement}
 */
function buildBranchElement(entry, rootName, collapsedPaths, onToggle) {
  const { node } = entry;
  const isCollapsed = collapsedPaths.has(node.fullPath);

  const branch = document.createElement('div');
  branch.className = `fh-branch${isCollapsed ? ' fh-branch--collapsed' : ''}`;

  const labelRow = document.createElement('div');
  labelRow.className = 'fh-branch__label';
  labelRow.style.setProperty('--fh-accent-color', accentColor(rootName, node.depth));
  labelRow.style.setProperty('--fh-card-bg', highlightColor(rootName, node.depth));
  labelRow.title = node.fullPath.replace(/>/g, ' ');

  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'fh-toggle';
  toggle.setAttribute('aria-expanded', String(!isCollapsed));
  toggle.setAttribute('aria-label', isCollapsed ? `Expand ${node.name}` : `Collapse ${node.name}`);
  toggle.title = isCollapsed ? 'Show sub-topics' : 'Collapse sub-topics';
  toggle.textContent = isCollapsed ? '›' : '‹';
  toggle.addEventListener('click', (event) => {
    event.stopPropagation();
    onToggle(node.fullPath);
  });
  labelRow.appendChild(toggle);

  const labelText = document.createElement('span');
  labelText.className = 'fh-branch__label-text';
  labelText.textContent = node.name;
  labelRow.appendChild(labelText);

  branch.appendChild(labelRow);

  if (!isCollapsed) {
    const children = Array.from(entry.children.values());
    const childrenEl = document.createElement('div');
    childrenEl.className = 'fh-branch__children';
    children.forEach((child) => {
      childrenEl.appendChild(buildTreeElement(child, rootName, collapsedPaths, onToggle));
    });
    branch.appendChild(childrenEl);
  }

  return branch;
}

/**
 * Build the DOM for one tree entry (branch or leaf).
 * @param {TreeEntry} entry
 * @param {string} rootName
 * @param {Set<string>} collapsedPaths
 * @param {(fullPath: string) => void} onToggle
 * @returns {HTMLElement}
 */
function buildTreeElement(entry, rootName, collapsedPaths, onToggle) {
  const isLeaf = entry.children.size === 0;
  return isLeaf
    ? buildLeafElement(entry, rootName)
    : buildBranchElement(entry, rootName, collapsedPaths, onToggle);
}

/**
 * Render the topic tree into the given container.
 * @param {HTMLElement|null} container
 * @param {TreeEntry[]} roots
 * @param {Set<string>} collapsedPaths
 * @param {(fullPath: string) => void} onToggle
 */
export function renderTree(container, roots, collapsedPaths, onToggle) {
  if (!container) return;
  container.replaceChildren();

  if (!Array.isArray(roots) || roots.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'fh-empty';
    empty.textContent = 'No topics have been processed for this feed yet.';
    container.appendChild(empty);
    return;
  }

  const root = document.createElement('div');
  root.className = 'fh-root';
  roots.forEach((entry) => {
    root.appendChild(buildTreeElement(entry, entry.node.name, collapsedPaths, onToggle));
  });
  container.appendChild(root);
}

/**
 * Render the "1".."maxLevel+1" level buttons.
 * @param {HTMLElement|null} container
 * @param {number} maxLevel
 * @param {number} selectedLevel
 * @param {(level: number) => void} onSelect
 */
export function renderLevelButtons(container, maxLevel, selectedLevel, onSelect) {
  if (!container) return;
  container.replaceChildren();
  if (maxLevel < 0) return;

  for (let level = 0; level <= maxLevel; level += 1) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = String(level + 1);
    button.title = `Show topic levels 1–${level + 1}`;
    button.classList.toggle('is-active', level === selectedLevel);
    button.addEventListener('click', () => onSelect(level));
    container.appendChild(button);
  }
}

class FeedHierarchy {
  constructor() {
    /** @type {Topic[]} */
    this.topics = Array.isArray(window.hierarchyTopics) ? window.hierarchyTopics : [];
    this.levelsEl = document.getElementById('feed_hierarchy_levels');
    this.treeEl = document.getElementById('feed_hierarchy_tree');
    this.roots = buildTopicTree(this.topics, 0);
    this.maxLevel = getMaxTopicLevel(this.topics);
    // Deepest level selected by default so the tree starts fully unfolded.
    this.selectedLevel = this.maxLevel;
    this.collapsedPaths = new Set(
      collectNonLeafPaths(this.roots, { minDepth: this.selectedLevel })
    );
  }

  init() {
    if (!this.treeEl) return;
    this.renderLevels();
    this.renderTree();
  }

  renderLevels() {
    renderLevelButtons(this.levelsEl, this.maxLevel, this.selectedLevel, (level) =>
      this.handleSelectLevel(level)
    );
  }

  renderTree() {
    renderTree(this.treeEl, this.roots, this.collapsedPaths, (fullPath) =>
      this.handleToggleCollapse(fullPath)
    );
  }

  /** @param {number} level */
  handleSelectLevel(level) {
    this.selectedLevel = level;
    this.collapsedPaths = new Set(collectNonLeafPaths(this.roots, { minDepth: level }));
    this.renderLevels();
    this.renderTree();
  }

  /** @param {string} fullPath */
  handleToggleCollapse(fullPath) {
    if (this.collapsedPaths.has(fullPath)) {
      this.collapsedPaths.delete(fullPath);
    } else {
      this.collapsedPaths.add(fullPath);
    }
    this.renderTree();
  }
}

export { FeedHierarchy };

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('feed_hierarchy_tree')) {
    new FeedHierarchy().init();
  }
});
