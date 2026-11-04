// Summary tree view model: server result -> collapsible display tree.
// Pure functions only, so they run under node:test without a DOM.

export const POST_KIND = 'post';
export const TOPIC_KIND = 'topic';
export const ROOT_KIND = 'root';

/**
 * Build the display tree. Topics with sub-topics show them as children;
 * the deepest topics show their source posts as leaves.
 * @param {{root_id: string, nodes: Record<string, any>, posts: Record<string, any>}} result
 * @returns {any|null}
 */
export function buildDisplayTree(result) {
  if (result?.schema_version === 3) {
    return buildTopicTree(result);
  }
  if (result?.schema_version === 2) {
    return buildClaimTree(result);
  }
  const nodes = result?.nodes || {};
  const posts = result?.posts || {};
  const visit = (id, path) => {
    const node = nodes[id];
    if (!node || path.has(id)) {
      return null;
    }
    const nextPath = new Set(path).add(id);
    const childIds = Array.isArray(node.children) ? node.children : [];
    const children = childIds.length
      ? childIds.map((childId) => visit(childId, nextPath)).filter(Boolean)
      : postLeaves(node, posts);
    return {
      key: id,
      kind: node.virtual ? ROOT_KIND : TOPIC_KIND,
      title: node.title || '',
      node,
      postIds: Array.isArray(node.post_ids) ? node.post_ids : [],
      children,
    };
  };
  return result?.root_id ? visit(result.root_id, new Set()) : null;
}

/**
 * Schema 3: the stored topic hierarchy is the display tree (focus → categories →
 * sub-topics → posts). Each node carries its level summary; ``parts`` are the
 * parent's segments that cite it, so a route can highlight what led to a post.
 */
function buildTopicTree(result) {
  const nodes = result.nodes || {};
  const posts = result.posts || {};
  const citing = (parent, childId) =>
    (parent?.segments || []).flatMap((segment, index) =>
      (segment.sources || []).some((s) => s.kind === 'claim' && s.child === childId)
        ? [{ node: parent.id, segment: index }]
        : []
    );
  const visit = (id, parent, seen) => {
    const node = nodes[id];
    if (!node || seen.has(id)) return null;
    const parts = citing(parent, id);
    if (node.kind === 'post') {
      const pid = String(node.post_ids[0]);
      const post = posts[pid];
      if (!post) return null; // skipped: irrelevant or failed
      return {
        key: id,
        kind: POST_KIND,
        title: post.title || pid,
        post,
        rows: citedRows(id, nodes),
        node,
        parts,
        postIds: [pid],
        children: [],
      };
    }
    const path = new Set(seen).add(id);
    const children = (node.children || []).map((child) => visit(child, node, path)).filter(Boolean);
    return {
      key: id,
      kind: node.kind === 'root' ? ROOT_KIND : TOPIC_KIND,
      title: node.title || '',
      summary: proseOf(node),
      node,
      parts,
      postIds: [...new Set(children.flatMap((child) => child.postIds))],
      children,
    };
  };
  if (result.root_id) {
    const tree = visit(result.root_id, null, new Set());
    return tree;
  }
  // Still summarizing posts: show those done so far under a provisional root.
  const children = Object.values(nodes)
    .filter((node) => node.kind === 'post' && node.segments?.length)
    .map((node) => visit(node.id, null, new Set()))
    .filter(Boolean);
  return children.length
    ? {
        key: 'root',
        kind: ROOT_KIND,
        title: '',
        postIds: children.flatMap((child) => child.postIds),
        children,
      }
    : null;
}

function proseOf(node) {
  return (node?.segments || [])
    .map((segment) => segment.text)
    .join('')
    .trim();
}

/** Passage ranges cited by a post node and its passage chunks. */
function citedRows(id, nodes, seen = new Set()) {
  const node = nodes[id];
  if (!node || seen.has(id)) return [];
  seen.add(id);
  const own = (node.segments || []).flatMap((segment) =>
    (segment.sources || []).filter((s) => s.kind === 'rows').map((s) => [s.first, s.last])
  );
  return [...own, ...(node.children || []).flatMap((child) => citedRows(child, nodes, seen))];
}

/** Claim occurrences follow only explicit links; membership is used for uncited fallback. */
function buildClaimTree(result) {
  const nodes = result.nodes || {};
  const posts = result.posts || {};
  const visit = (id, selected, key, ancestry) => {
    const node = nodes[id];
    if (!node || ancestry.has(id)) return [];
    const path = new Set(ancestry).add(id);
    const segments = node.segments || [];
    const indices = selected ?? segments.flatMap((s, i) => (s.sources?.length ? [i] : []));
    const parts = indices.flatMap((index) => {
      const segment = segments[index];
      if (!segment) return [];
      const claims = new Map();
      const rows = [];
      for (const source of segment.sources || []) {
        if (source.kind === 'claim' && (node.children || []).includes(source.child)) {
          if (!claims.has(source.child)) claims.set(source.child, new Set());
          claims.get(source.child).add(source.segment);
        } else if (source.kind === 'rows') rows.push([source.first, source.last]);
      }
      const childKey = `${key}/s${index}`;
      const children = [...claims].flatMap(([child, chosen]) =>
        visit(child, [...chosen], `${childKey}/${child}`, path)
      );
      if (rows.length) {
        const pid = String(node.post_ids[0]);
        const post = posts[pid] || { pid };
        children.push({
          key: `${childKey}/post`,
          kind: POST_KIND,
          title: post.title || pid,
          post,
          rows,
          node,
          postIds: [pid],
          children: [],
        });
      }
      const postIds = [...new Set(children.flatMap((child) => child.postIds))];
      return [
        {
          key: childKey,
          kind: TOPIC_KIND,
          title: segment.text.trim(),
          node,
          segmentIndex: index,
          parts: [{ node: id, segment: index }],
          postIds,
          children,
        },
      ];
    });
    if (selected !== null) return parts;
    const cited = new Set(
      indices.flatMap((index) =>
        (segments[index]?.sources || [])
          .filter((source) => source.kind === 'claim')
          .map((source) => source.child)
      )
    );
    const rest = (node.children || [])
      .filter((child) => !cited.has(child))
      .flatMap((child) => visit(child, null, `${key}/uncited/${child}`, path));
    if (!parts.length && !rest.length && node.kind === 'post' && node.segments === null) {
      const pid = String(node.post_ids[0]);
      return [
        {
          key: `${key}/post`,
          kind: POST_KIND,
          title: node.title || pid,
          post: posts[pid] || { pid },
          node,
          rows: [],
          postIds: [pid],
          children: [],
        },
      ];
    }
    return [...parts, ...rest];
  };
  const merge = (part) => {
    const children = part.children.map(merge);
    const only = children.length === 1 ? children[0] : null;
    if (
      only &&
      (part.title === only.title ||
        (only.kind === POST_KIND && ['post', 'chunk'].includes(part.node?.kind)))
    ) {
      return {
        ...only,
        title: part.title || only.title,
        parts: [...(part.parts || []), ...(only.parts || [])],
      };
    }
    return { ...part, children };
  };
  const root = nodes[result.root_id];
  if (!root) return null;
  const children = visit(result.root_id, null, 'root', new Set()).map(merge);
  return children.length === 1
    ? children[0]
    : {
        key: 'root',
        kind: ROOT_KIND,
        title: root.title,
        node: root,
        postIds: [...new Set(children.flatMap((child) => child.postIds))],
        children,
      };
}

function postLeaves(node, posts) {
  const ids = Array.isArray(node.post_ids) ? node.post_ids : [];
  return ids.map((pid) => {
    const post = posts[pid] || { pid };
    return {
      key: `${node.id}:${pid}`,
      kind: POST_KIND,
      title: post.summary_title || post.title || String(pid),
      post,
      postIds: [pid],
      children: [],
    };
  });
}

/** Start with only the root visible. */
export function initialExpanded() {
  return new Set();
}

/** @returns {any[]} chain of display nodes from the root to the node with ``key`` */
export function pathTo(tree, key) {
  if (!tree) {
    return [];
  }
  if (tree.key === key) {
    return [tree];
  }
  for (const child of tree.children) {
    const path = pathTo(child, key);
    if (path.length) {
      return [tree, ...path];
    }
  }
  return [];
}

/**
 * Leaf key showing ``pid`` inside the subtree of ``fromKey`` (or anywhere).
 * @returns {string|null}
 */
export function findPostLeaf(tree, pid, fromKey = null) {
  const start = fromKey ? pathTo(tree, fromKey).at(-1) : tree;
  const search = (node) => {
    if (!node) {
      return null;
    }
    if (node.kind === POST_KIND) {
      return String(node.post?.pid) === String(pid) ? node.key : null;
    }
    if (!node.postIds.map(String).includes(String(pid))) {
      return null;
    }
    for (const child of node.children) {
      const found = search(child);
      if (found) {
        return found;
      }
    }
    return null;
  };
  return search(start);
}

/**
 * Toggle a node; with ``exclusive`` opening a node closes its siblings
 * (and their descendants) so only one branch is walked at a time.
 * @param {Set<string>} expanded
 * @returns {Set<string>}
 */
export function toggleNode(tree, expanded, key, exclusive) {
  const next = new Set(expanded);
  if (next.has(key)) {
    collapseSubtree(pathTo(tree, key).at(-1), next);
    return next;
  }
  const path = pathTo(tree, key);
  if (exclusive && path.length > 1) {
    for (const sibling of path.at(-2).children) {
      if (sibling.key !== key) {
        collapseSubtree(sibling, next);
      }
    }
  }
  path.forEach((node) => next.add(node.key));
  return next;
}

/** Number of levels in the tree, the root being level 1 (a lone root is 1). */
export function treeDepth(tree) {
  if (!tree) {
    return 0;
  }
  return 1 + Math.max(0, ...tree.children.map(treeDepth));
}

/**
 * Keys to expand so that exactly ``level`` levels are visible (root = level 1).
 * @returns {Set<string>}
 */
export function expandToLevel(tree, level) {
  const keys = new Set();
  const walk = (node, depth) => {
    if (node.kind !== POST_KIND && depth + 1 < level) {
      keys.add(node.key);
      node.children.forEach((child) => walk(child, depth + 1));
    }
  };
  if (tree) {
    walk(tree, 0);
  }
  return keys;
}

/** The level whose expansion equals ``expanded`` exactly, or null for a custom state. */
export function currentLevel(tree, expanded) {
  for (let level = 1; level <= treeDepth(tree); level += 1) {
    const keys = expandToLevel(tree, level);
    if (keys.size === expanded.size && [...keys].every((key) => expanded.has(key))) {
      return level;
    }
  }
  return null;
}

/** Expand ``key`` and everything below it, down to the post leaves. */
export function expandBranch(tree, expanded, key) {
  const next = revealNode(tree, expanded, key);
  const walk = (node) => {
    if (node.kind !== POST_KIND) {
      next.add(node.key);
      node.children.forEach(walk);
    }
  };
  const start = pathTo(tree, key).at(-1);
  if (start) {
    walk(start);
  }
  return next;
}

/** Expand every ancestor of ``key`` so it becomes visible. */
export function revealNode(tree, expanded, key) {
  const next = new Set(expanded);
  pathTo(tree, key)
    .slice(0, -1)
    .forEach((node) => next.add(node.key));
  return next;
}

function collapseSubtree(node, expanded) {
  if (!node) {
    return;
  }
  expanded.delete(node.key);
  node.children.forEach((child) => collapseSubtree(child, expanded));
}

/** Copy of the tree keeping only children of expanded nodes (input for d3.hierarchy). */
export function visibleTree(tree, expanded) {
  if (!tree) {
    return null;
  }
  const open = expanded.has(tree.key);
  return {
    ...tree,
    hiddenCount: open ? 0 : tree.children.length,
    children: open ? tree.children.map((child) => visibleTree(child, expanded)) : [],
  };
}

/** Font size grows with the share of posts a topic covers, like a word tree. */
export function labelSize(node, totalPosts) {
  if (node.kind === POST_KIND) {
    return 13;
  }
  const share = totalPosts > 0 ? node.postIds.length / totalPosts : 0;
  return Math.round(15 + 21 * Math.sqrt(Math.min(1, share)));
}

/** Numbered source references for a topic's statements: pid -> 1-based number. */
export function sourceNumbers(node) {
  const numbers = new Map();
  const statements = Array.isArray(node?.statements) ? node.statements : [];
  for (const statement of statements) {
    for (const pid of statement.sources || []) {
      if (!numbers.has(pid)) {
        numbers.set(pid, numbers.size + 1);
      }
    }
  }
  for (const pid of node?.post_ids || []) {
    if (!numbers.has(pid)) {
      numbers.set(pid, numbers.size + 1);
    }
  }
  return numbers;
}

/** @param {{status: string, stage: string|null, progress?: {done?: number, total?: number}}} tree */
export function progressLabel(tree) {
  if (tree.status === 'done') {
    return 'Done';
  }
  if (tree.status === 'failed') {
    return `Failed: ${tree.error || 'unknown error'}`;
  }
  if (tree.status === 'pending') {
    return 'Queued';
  }
  const done = tree.progress?.done || 0;
  const total = tree.progress?.total || 0;
  const count = total ? `${done}/${total}` : `${done}`;
  return `${tree.stage || 'starting'} ${count}`;
}

/** @returns {boolean} whether the page should keep polling */
export function isRunning(tree) {
  return tree?.status === 'pending' || (tree?.status === 'processing' && !tree?.stuck);
}

// ============================================================
// Canvas geometry (pure, measured sizes come from the DOM)
// ============================================================

export const CARD_MIN = { w: 240, h: 120 };

/** Left edge of every depth column so no column overlaps the widest node before it. */
export function columnOffsets(widths, gap) {
  const offsets = [0];
  for (let depth = 1; depth < widths.length; depth += 1) {
    offsets[depth] = offsets[depth - 1] + (widths[depth - 1] || 0) + gap;
  }
  return offsets;
}

/** Wrap width for a topic label: bigger type gets a wider line, within sane bounds. */
export function topicMaxWidth(fontSize) {
  return Math.max(480, Math.min(760, Math.round(fontSize * 22)));
}

/** Keep a user-resized card readable. */
export function clampCardSize(width, height) {
  return {
    w: Math.max(CARD_MIN.w, Math.round(width)),
    h: Math.max(CARD_MIN.h, Math.round(height)),
  };
}

/** @param {{left: number, top: number, w: number, h: number}[]} rects */
export function boundsOf(rects) {
  if (!rects.length) {
    return null;
  }
  const minX = Math.min(...rects.map((r) => r.left));
  const minY = Math.min(...rects.map((r) => r.top));
  const maxX = Math.max(...rects.map((r) => r.left + r.w));
  const maxY = Math.max(...rects.map((r) => r.top + r.h));
  return { minX, minY, width: maxX - minX, height: maxY - minY };
}

/**
 * Zoom transform that fits ``bounds`` into the viewport (never enlarging past 1:1),
 * centred on the axis that fits and left/top aligned on the one that does not.
 */
export function fitTransform(bounds, viewport, pad = 24, minScale = 0.2) {
  if (!bounds) {
    return { k: 1, x: pad, y: viewport.height / 2 };
  }
  const k = Math.max(
    minScale,
    Math.min(
      1,
      (viewport.width - 2 * pad) / Math.max(1, bounds.width),
      (viewport.height - 2 * pad) / Math.max(1, bounds.height)
    )
  );
  const place = (size, start, extent) =>
    size * k <= extent - 2 * pad ? (extent - size * k) / 2 - start * k : pad - start * k;
  return {
    k,
    x: place(bounds.width, bounds.minX, viewport.width),
    y: place(bounds.height, bounds.minY, viewport.height),
  };
}
