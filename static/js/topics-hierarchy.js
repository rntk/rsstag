'use strict';

/**
 * Topics Hierarchy View
 *
 * A swim-lane style visualization of the topics tree. Each non-leaf topic
 * renders a label column on the left with its children stacked to the right;
 * leaf topics render as compact pills. Colors are derived deterministically
 * from the root topic name with a depth-based gradient.
 *
 * Adapted from the React TopicHierarchyView component to match the vanilla
 * component style used elsewhere in this codebase (topics-sunburst.js, etc.).
 *
 * For this first implementation we only visualize the topics hierarchy -
 * article texts and sentences are intentionally skipped.
 */

/**
 * Non-negative integer hash of a string (djb2-ish, matches topicColorUtils).
 * @param {string} value
 * @returns {number}
 */
function hashString(value) {
  let hash = 0;
  const input = String(value || '');
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

/**
 * Background color for a hierarchy node: all descendants of the same root
 * share a hue; saturation/lightness shift by depth for a gradient effect.
 * @param {string} rootName
 * @param {number} depth
 * @returns {string}
 */
function hierarchyHighlightColor(rootName, depth) {
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
function hierarchyAccentColor(rootName, depth) {
  const hue = hashString(rootName) % 360;
  const saturation = Math.max(30, 60 - depth * 6);
  const lightness = Math.min(62, 38 + depth * 6);
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

/**
 * Count the rows a subtree occupies so parent labels can span their children.
 * @param {object} node
 * @returns {number}
 */
function countRenderedRows(node) {
  const children = Array.isArray(node.children) ? node.children : [];
  if (children.length === 0) {
    return 1;
  }
  return children.reduce((total, child) => total + countRenderedRows(child), 0);
}

/**
 * Recursively build the DOM for a single topic node.
 * @param {object} node - tree node ({name, value, children, _topicPath})
 * @param {string} rootName - name of the top-level ancestor (for coloring)
 * @param {number} depth - depth from the root (0 based)
 * @returns {HTMLElement}
 */
function buildNode(node, rootName, depth) {
  const children = Array.isArray(node.children) ? node.children : [];
  const isLeaf = children.length === 0;
  const fullPath = node._topicPath || node.name;
  const count = typeof node.value === 'number' ? node.value : 0;
  const highlightColor = hierarchyHighlightColor(rootName, depth);
  const accentColor = hierarchyAccentColor(rootName, depth);

  if (isLeaf) {
    const leaf = document.createElement('div');
    leaf.className = 'th-leaf';
    leaf.style.backgroundColor = highlightColor;
    leaf.style.borderLeftColor = accentColor;
    leaf.title = `${fullPath} (${count})`;

    const label = document.createElement('span');
    label.className = 'th-leaf__label';
    label.textContent = node.name;
    leaf.appendChild(label);

    if (count > 0) {
      const countEl = document.createElement('span');
      countEl.className = 'th-leaf__count';
      countEl.textContent = String(count);
      leaf.appendChild(countEl);
    }
    return leaf;
  }

  const nodeEl = document.createElement('div');
  nodeEl.className = 'th-node';
  nodeEl.style.setProperty('--th-row-span', String(countRenderedRows(node)));

  // The label is a full-height colored panel spanning all child rows so the
  // hierarchy relationship stays visible even for tall top-level topics.
  const labelEl = document.createElement('div');
  labelEl.className = 'th-node__label';
  // Drives the sticky `top` offset so nested titles stack below their
  // ancestors instead of overlapping when scrolling tall branches.
  labelEl.style.setProperty('--th-depth', String(depth));
  labelEl.style.backgroundColor = highlightColor;
  labelEl.style.borderLeftColor = accentColor;
  labelEl.title = fullPath;

  // Only this inner wrapper sticks while scrolling the tall panel.
  const labelSticky = document.createElement('div');
  labelSticky.className = 'th-node__label-sticky';

  const labelText = document.createElement('span');
  labelText.className = 'th-node__label-text';
  labelText.textContent = node.name;
  labelSticky.appendChild(labelText);

  const labelCount = document.createElement('span');
  labelCount.className = 'th-leaf__count';
  labelCount.textContent = String(count);
  labelSticky.appendChild(labelCount);

  labelEl.appendChild(labelSticky);

  const childrenEl = document.createElement('div');
  childrenEl.className = 'th-node__children';
  children.forEach((child) => {
    childrenEl.appendChild(buildNode(child, rootName, depth + 1));
  });

  nodeEl.appendChild(labelEl);
  nodeEl.appendChild(childrenEl);
  return nodeEl;
}

/**
 * Render the topics hierarchy into the given container.
 * @param {HTMLElement} container
 * @param {object} data - { name, children: [...] } (window.sunburst_data shape)
 */
export function renderTopicsHierarchy(container, data) {
  if (!container) {
    return;
  }
  container.innerHTML = '';

  const roots = data && Array.isArray(data.children) ? data.children : [];
  if (roots.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'th-empty';
    empty.textContent = 'No topics available for this page.';
    container.appendChild(empty);
    return;
  }

  const root = document.createElement('div');
  root.className = 'th-root';
  roots.forEach((topic) => {
    root.appendChild(buildNode(topic, topic.name, 0));
  });
  container.appendChild(root);
}

export default renderTopicsHierarchy;
