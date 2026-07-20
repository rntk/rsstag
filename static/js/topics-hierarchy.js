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
    if (node._url) {
      const link = document.createElement('a');
      link.href = node._url;
      link.textContent = node.name;
      label.appendChild(link);
    } else {
      label.textContent = node.name;
    }
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
  if (node._url) {
    const link = document.createElement('a');
    link.href = node._url;
    link.textContent = node.name;
    labelText.appendChild(link);
  } else {
    labelText.textContent = node.name;
  }
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

/**
 * Clamp a canvas zoom scale to the useful range for overview and detail work.
 * @param {number} scale
 * @returns {number}
 */
function clampScale(scale) {
  return Math.min(2.5, Math.max(0.12, scale));
}

/**
 * Initialize the full-page hierarchy canvas.
 * @param {object} options
 * @param {string} options.viewportId
 * @param {string} options.canvasId
 * @param {string} options.containerId
 * @param {object} options.data
 */
export function initTopicHierarchyCanvasPage({
  viewportId = 'topic_hierarchy_viewport',
  canvasId = 'topic_hierarchy_canvas',
  containerId = 'topic_hierarchy_container',
  data = window.topic_hierarchy_data,
} = {}) {
  const viewport = document.getElementById(viewportId);
  const canvas = document.getElementById(canvasId);
  const container = document.getElementById(containerId);
  if (!viewport || !canvas || !container) {
    return;
  }

  renderTopicsHierarchy(container, data);

  let scale = 1;
  let translate = { x: 24, y: 24 };
  let isDragging = false;
  let lastPointer = { x: 0, y: 0 };

  const zoomLabel = document.getElementById('topic_hierarchy_zoom_label');
  const updateTransform = () => {
    const readableScale = Math.min(3.2, Math.max(0.85, 1 / Math.sqrt(scale)));
    container.style.setProperty('--th-readable-scale', String(readableScale));
    canvas.style.transform = `translate(${translate.x}px, ${translate.y}px) scale(${scale})`;
    if (zoomLabel) {
      zoomLabel.textContent = `${Math.round(scale * 100)}%`;
    }
  };

  const setScaleAt = (nextScale, anchor) => {
    const clampedScale = clampScale(nextScale);
    if (clampedScale === scale) {
      return;
    }
    const rect = viewport.getBoundingClientRect();
    const cursor = anchor || { x: rect.width / 2, y: rect.height / 2 };
    const worldX = (cursor.x - translate.x) / scale;
    const worldY = (cursor.y - translate.y) / scale;
    translate = {
      x: cursor.x - worldX * clampedScale,
      y: cursor.y - worldY * clampedScale,
    };
    scale = clampedScale;
    updateTransform();
  };

  const getViewportSize = () => {
    const rect = viewport.getBoundingClientRect();
    return {
      width: rect.width || window.innerWidth,
      height: rect.height || window.innerHeight,
    };
  };

  const getContentSize = () => {
    const root = container.querySelector('.th-root');
    if (!root) {
      return { width: 1, height: 1 };
    }
    return {
      width: Math.max(root.scrollWidth, root.offsetWidth, 1),
      height: Math.max(root.scrollHeight, root.offsetHeight, 1),
    };
  };

  const panBy = (dx, dy) => {
    translate = {
      x: translate.x + dx,
      y: translate.y + dy,
    };
    updateTransform();
  };

  const moveToTop = () => {
    translate = { ...translate, y: 24 };
    updateTransform();
  };

  const moveToBottom = () => {
    const viewportSize = getViewportSize();
    const contentSize = getContentSize();
    translate = {
      ...translate,
      y: Math.min(24, viewportSize.height - contentSize.height * scale - 24),
    };
    updateTransform();
  };

  const fitToView = () => {
    const root = container.querySelector('.th-root');
    if (!root) {
      return;
    }
    const viewportRect = viewport.getBoundingClientRect();
    const contentWidth = Math.max(root.scrollWidth, root.offsetWidth, 1);
    const contentHeight = Math.max(root.scrollHeight, root.offsetHeight, 1);
    const fitScale = clampScale(
      Math.min((viewportRect.width - 48) / contentWidth, (viewportRect.height - 48) / contentHeight)
    );
    scale = fitScale;
    translate = {
      x: Math.max(24, (viewportRect.width - contentWidth * scale) / 2),
      y: Math.max(24, (viewportRect.height - contentHeight * scale) / 2),
    };
    updateTransform();
  };

  viewport.addEventListener(
    'wheel',
    (event) => {
      event.preventDefault();
      const rect = viewport.getBoundingClientRect();
      const factor = event.deltaY > 0 ? 0.88 : 1.14;
      setScaleAt(scale * factor, {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      });
    },
    { passive: false }
  );

  viewport.addEventListener('mousedown', (event) => {
    if (event.button !== 0 || event.target.closest('a, button, input, textarea, select')) {
      return;
    }
    isDragging = true;
    lastPointer = { x: event.clientX, y: event.clientY };
    viewport.classList.add('is-dragging');
    event.preventDefault();
  });

  window.addEventListener('mousemove', (event) => {
    if (!isDragging) {
      return;
    }
    translate = {
      x: translate.x + event.clientX - lastPointer.x,
      y: translate.y + event.clientY - lastPointer.y,
    };
    lastPointer = { x: event.clientX, y: event.clientY };
    updateTransform();
  });

  window.addEventListener('mouseup', () => {
    isDragging = false;
    viewport.classList.remove('is-dragging');
  });

  document.getElementById('topic_hierarchy_zoom_in')?.addEventListener('click', () => {
    setScaleAt(scale * 1.2);
  });
  document.getElementById('topic_hierarchy_zoom_out')?.addEventListener('click', () => {
    setScaleAt(scale / 1.2);
  });
  document.getElementById('topic_hierarchy_reset')?.addEventListener('click', () => {
    scale = 1;
    translate = { x: 24, y: 24 };
    updateTransform();
  });
  document.getElementById('topic_hierarchy_fit')?.addEventListener('click', fitToView);
  window.addEventListener('resize', fitToView);
  window.addEventListener('keydown', (event) => {
    if (event.defaultPrevented) {
      return;
    }
    if (
      event.target &&
      typeof event.target.closest === 'function' &&
      event.target.closest('input, textarea, select, [contenteditable="true"]')
    ) {
      return;
    }

    const viewportSize = getViewportSize();
    const arrowStep = event.shiftKey ? 180 : 70;
    const pageStep = Math.max(120, viewportSize.height * 0.8);
    const handlers = {
      ArrowUp: () => panBy(0, arrowStep),
      ArrowDown: () => panBy(0, -arrowStep),
      ArrowLeft: () => panBy(arrowStep, 0),
      ArrowRight: () => panBy(-arrowStep, 0),
      PageUp: () => panBy(0, pageStep),
      PageDown: () => panBy(0, -pageStep),
      Home: moveToTop,
      End: moveToBottom,
    };
    const handler = handlers[event.key];
    if (!handler) {
      return;
    }
    event.preventDefault();
    handler();
  });

  updateTransform();
  window.requestAnimationFrame(fitToView);
}

export { hashString, hierarchyHighlightColor, hierarchyAccentColor, countRenderedRows, clampScale };
export default renderTopicsHierarchy;
