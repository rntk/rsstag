/* global window, document, console, setTimeout, clearTimeout, confirm */
// Summary tree page: build form + list, and the progressive-disclosure tree canvas.
import {
  escapeHtml,
  fetchJson,
  formatDate,
  postJson,
  readJsonScript,
} from './libs/anthology-common.js';
import {
  POST_KIND,
  boundsOf,
  buildDisplayTree,
  clampCardSize,
  columnOffsets,
  currentLevel,
  expandBranch,
  expandToLevel,
  findPostLeaf,
  fitTransform,
  initialExpanded,
  isRunning,
  labelSize,
  pathTo,
  progressLabel,
  revealNode,
  sourceNumbers,
  toggleNode,
  topicMaxWidth,
  treeDepth,
  visibleTree,
} from './libs/summary-tree-model.js';

const POLL_MS = 4000;
const COLUMN_GAP = 64;
const SIBLING_GAP = 12;
const BRANCH_GAP = 28;
const CARD_ANCHOR_Y = 20;
const SCALE_EXTENT = [0.15, 3];

// ============================================================
// List mode
// ============================================================

function filterChips(filters) {
  const chips = [];
  for (const key of ['tags', 'feed_ids', 'category_ids', 'post_ids']) {
    for (const value of filters?.[key] || []) {
      chips.push(
        `<span class="stree-chip">${escapeHtml(key.replace('_ids', ''))}: ${escapeHtml(value)}</span>`
      );
    }
  }
  return chips.join('');
}

function renderList(root, data) {
  const draft = data.draft || { filters: {}, options: {} };
  const rows = (data.trees || [])
    .map(
      (tree) => `<tr data-id="${escapeHtml(tree.id)}">
        <td><a href="/summary-tree/${encodeURIComponent(tree.id)}">${escapeHtml(tree.focus)}</a></td>
        <td>${escapeHtml(tree.filters_label)}</td>
        <td>${escapeHtml(progressLabel(tree))}</td>
        <td>${escapeHtml(formatDate(tree.updated_at))}</td>
        <td><button type="button" class="stree-btn stree-btn--ghost" data-action="delete">Delete</button></td>
      </tr>`
    )
    .join('');
  root.innerHTML = `
    <form class="stree-form" id="stree-form">
      <label>Entity <input name="entity" required value="${escapeHtml(draft.filters?.entity || '')}" /></label>
      <label>Extra tags <input name="tags" placeholder="comma separated" value="${escapeHtml((draft.filters?.tags || []).join(', '))}" /></label>
      <label>Max posts <input name="limit" type="number" min="1" max="300" value="${escapeHtml(draft.options?.limit || 50)}" /></label>
      <label class="stree-form__check"><input name="only_unread" type="checkbox" ${draft.filters?.only_unread ? 'checked' : ''} /> Only unread</label>
      <div class="stree-form__chips">${filterChips(draft.filters)}</div>
      <button type="submit" class="stree-btn">Build summary tree</button>
      <span class="stree-muted" id="stree-form-status" role="status"></span>
    </form>
    <table class="stree-table">
      <thead><tr><th>Entity</th><th>Filters</th><th>Status</th><th>Updated</th><th></th></tr></thead>
      <tbody>${rows || '<tr><td colspan="5" class="stree-muted">No summary trees yet.</td></tr>'}</tbody>
    </table>`;
  bindListEvents(root, draft);
}

function bindListEvents(root, draft) {
  root.querySelector('#stree-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new window.FormData(event.target);
    const status = root.querySelector('#stree-form-status');
    const filters = {
      ...draft.filters,
      entity: String(form.get('entity') || '').trim(),
      tags: String(form.get('tags') || '')
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean),
      only_unread: form.get('only_unread') === 'on',
    };
    status.textContent = 'Queuing…';
    try {
      const created = await postJson('/api/summary-trees', {
        filters,
        options: { ...draft.options, limit: Number(form.get('limit')) || 50 },
      });
      window.location.assign(created.url);
    } catch (error) {
      status.textContent = error.message;
    }
  });
  root.querySelector('tbody').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-action="delete"]');
    const row = button?.closest('tr');
    if (!row || !confirm('Delete this summary tree?')) {
      return;
    }
    try {
      await fetchJson(`/api/summary-trees/${encodeURIComponent(row.dataset.id)}`, {
        method: 'DELETE',
      });
      row.remove();
    } catch (error) {
      console.error('Delete failed', error);
    }
  });
}

// ============================================================
// Detail mode
// ============================================================

/**
 * Tree canvas: an HTML node layer (topics + post cards) over an SVG link layer,
 * both inside one pan/zoom stage. Node sizes are measured from the DOM, so the
 * layout follows the real text width/height instead of a character estimate.
 */
export class SummaryTreeView {
  constructor(root, payload, d3) {
    this.root = root;
    this.d3 = d3;
    this.payload = payload;
    this.exclusive = false;
    this.selectedKey = null;
    this.pollTimer = null;
    this.transform = null;
    this.offsets = new Map(); // key -> {dx, dy}: manual card moves
    this.cardSizes = new Map(); // key -> {w, h}: manual card resizes
    this.positions = new Map(); // key -> {left, top, w, h}: current placement
    this.elements = new Map(); // key -> HTMLElement
    this.hierarchy = null;
    this.setPayload(payload);
  }

  setPayload(payload) {
    this.payload = payload;
    this.tree = buildDisplayTree(payload.result);
    const keys = new Set();
    const walk = (node) => {
      if (node) {
        keys.add(node.key);
        node.children.forEach(walk);
      }
    };
    walk(this.tree);
    this.expanded = this.expanded
      ? new Set([...this.expanded].filter((key) => keys.has(key)))
      : initialExpanded(this.tree);
    if (!this.expanded.size) this.expanded = initialExpanded(this.tree);
    this.totalPosts = this.tree ? this.tree.postIds.length : 0;
    this.selectedKey = keys.has(this.selectedKey) ? this.selectedKey : this.tree?.key || null;
  }

  mount() {
    this.root.classList.add('stree-app--detail');
    this.root.closest('.stree-page')?.classList.add('stree-page--detail');
    this.root.innerHTML = `
      <header class="stree-bar">
        <div class="stree-head" id="stree-head"></div>
        <div class="stree-toolbar">
          <label class="stree-form__check"><input type="checkbox" id="stree-exclusive" /> One branch at a time</label>
          <label class="stree-form__check">Levels <select id="stree-levels" class="stree-select"></select></label>
          <button type="button" class="stree-btn stree-btn--ghost" id="stree-expand">Expand all</button>
          <button type="button" class="stree-btn stree-btn--ghost" id="stree-tidy" title="Undo manual moves and resizes">Tidy</button>
          <button type="button" class="stree-btn stree-btn--ghost" id="stree-fit">Fit</button>
          <button type="button" class="stree-btn stree-btn--ghost" id="stree-reset">Reset</button>
        </div>
      </header>
      <div class="stree-canvas" id="stree-canvas">
        <div class="stree-stage">
          <svg class="stree-links"></svg>
          <div class="stree-nodes"></div>
        </div>
        <p class="stree-hint stree-muted">Drag empty space to pan · wheel to zoom (Ctrl+wheel over a card) · drag a card header to move it, its corner to resize</p>
      </div>`;
    this.stage = this.root.querySelector('.stree-stage');
    this.linksLayer = this.root.querySelector('.stree-links');
    this.nodesLayer = this.root.querySelector('.stree-nodes');
    this.bindToolbar();
    this.bindNodes();
    this.initZoom();
    this.render();
    this.fitView();
  }

  bindToolbar() {
    const on = (id, handler) => this.root.querySelector(id).addEventListener('click', handler);
    this.root.querySelector('#stree-exclusive').addEventListener('change', (event) => {
      this.exclusive = event.target.checked;
    });
    this.root.querySelector('#stree-levels').addEventListener('change', (event) => {
      const level = Number(event.target.value);
      if (level) this.setLevel(level);
    });
    on('#stree-expand', () => this.expandAll());
    on('#stree-tidy', () => this.tidy());
    on('#stree-fit', () => this.fitView());
    on('#stree-reset', () => this.reset());
  }

  expandAll() {
    const all = new Set();
    const walk = (node) => {
      if (node.kind !== POST_KIND) {
        all.add(node.key);
        node.children.forEach(walk);
      }
    };
    if (this.tree) {
      walk(this.tree);
    }
    this.expanded = all;
    this.render();
    this.fitView();
  }

  setLevel(level) {
    this.expanded = expandToLevel(this.tree, level);
    this.selectedKey = this.tree?.key || null;
    this.renderTree();
    this.fitView();
  }

  /** Offer one option per tree level and show the one matching the current expansion. */
  renderLevels() {
    const select = this.root.querySelector('#stree-levels');
    if (!select) {
      return;
    }
    const depth = treeDepth(this.tree);
    const options = Array.from({ length: depth }, (_, i) => `<option value="${i + 1}">${i + 1}</option>`);
    select.innerHTML = `<option value="">custom</option>${options.join('')}`;
    select.disabled = depth === 0;
    select.value = String(this.tree ? currentLevel(this.tree, this.expanded) ?? '' : '');
  }

  tidy() {
    this.offsets.clear();
    this.cardSizes.clear();
    this.renderTree();
  }

  reset() {
    this.expanded = initialExpanded(this.tree);
    this.selectedKey = this.tree?.key || null;
    this.offsets.clear();
    this.cardSizes.clear();
    this.render();
    this.fitView();
  }

  // ---------- zoom ----------

  initZoom() {
    const canvas = this.root.querySelector('#stree-canvas');
    this.zoom = this.d3
      .zoom()
      .scaleExtent(SCALE_EXTENT)
      .filter((event) => this.zoomAllowed(event))
      .on('zoom', (event) => this.applyTransform(event.transform));
    this.d3.select(canvas).call(this.zoom).on('dblclick.zoom', null);
  }

  /** Cards keep their own scrolling, text selection and dragging; Ctrl+wheel still zooms. */
  zoomAllowed(event) {
    if (event.target?.closest?.('.stree-card, .stree-node__summary')) {
      return event.type === 'wheel' && event.ctrlKey;
    }
    return (!event.ctrlKey || event.type === 'wheel') && !event.button;
  }

  applyTransform(transform) {
    this.transform = transform;
    this.stage.style.transform = `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`;
  }

  fitView() {
    const canvas = this.root.querySelector('#stree-canvas');
    const viewport = { width: canvas.clientWidth || 800, height: canvas.clientHeight || 600 };
    const fit = fitTransform(boundsOf([...this.positions.values()]), viewport);
    const transform = this.d3.zoomIdentity.translate(fit.x, fit.y).scale(fit.k);
    this.d3.select(canvas).call(this.zoom.transform, transform);
  }

  /** Shift the view so the node ``key`` stays where it was on screen before a relayout. */
  keepAnchored(key, before) {
    const after = this.positions.get(key);
    if (!before || !after) {
      return;
    }
    const canvas = this.d3.select(this.root.querySelector('#stree-canvas'));
    canvas.call(this.zoom.translateBy, before.left - after.left, before.top - after.top);
  }

  // ---------- header / polling ----------

  render() {
    this.renderHead();
    this.renderTree();
  }

  renderHead() {
    const tree = this.payload;
    const metrics = tree.metrics || {};
    const stats =
      tree.status === 'done'
        ? `${metrics.summarized || 0} of ${metrics.posts || 0} posts · ${metrics.topics || 0} summary groups`
        : '';
    this.root.querySelector('#stree-head').innerHTML = `
      <a class="stree-back" href="/summary-tree/" title="All summary trees">‹</a>
      <h1 class="stree-title">${escapeHtml(tree.focus)}</h1>
      <span class="stree-muted">${escapeHtml(tree.filters_label)} ${stats ? `· ${escapeHtml(stats)}` : ''}</span>
      <span class="stree-status stree-status--${escapeHtml(tree.status)}">${escapeHtml(progressLabel(tree))}</span>
      ${isRunning(tree) ? '' : '<button type="button" class="stree-btn" id="stree-rebuild">Rebuild</button>'}
      ${this.skippedBlock()}`;
    this.root.querySelector('#stree-rebuild')?.addEventListener('click', () => this.rebuild());
  }

  async rebuild() {
    try {
      this.payload = await postJson(
        `/api/summary-trees/${encodeURIComponent(this.payload.id)}/retry`,
        {}
      );
      this.renderHead();
      this.schedulePoll();
    } catch (error) {
      console.error('Rebuild failed', error);
    }
  }

  schedulePoll() {
    clearTimeout(this.pollTimer);
    if (!isRunning(this.payload)) {
      return;
    }
    this.pollTimer = setTimeout(async () => {
      try {
        const fresh = await fetchJson(`/api/summary-trees/${encodeURIComponent(this.payload.id)}`);
        const hadTree = Boolean(this.tree);
        this.setPayload(fresh);
        this.render();
        if (!hadTree) this.fitView();
      } catch (error) {
        console.error('Poll failed', error);
      }
      this.schedulePoll();
    }, POLL_MS);
  }

  emptyText() {
    if (isRunning(this.payload)) {
      return 'Building the tree…';
    }
    return this.payload.error || 'No result yet.';
  }

  // ---------- tree rendering ----------

  renderTree() {
    this.renderLevels();
    this.positions.clear();
    this.elements.clear();
    if (!this.tree) {
      this.hierarchy = null;
      this.linksLayer.innerHTML = '';
      this.nodesLayer.innerHTML = `<p class="stree-empty">${escapeHtml(this.emptyText())}</p>`;
      return;
    }
    this.hierarchy = this.d3.hierarchy(visibleTree(this.tree, this.expanded));
    const nodes = this.hierarchy.descendants();
    this.nodesLayer.innerHTML = nodes.map((d) => this.nodeHtml(d.data)).join('');
    [...this.nodesLayer.children].forEach((el, index) => {
      this.elements.set(nodes[index].data.key, el);
      this.styleNode(el, nodes[index].data);
    });
    this.markSelection();
    this.layout();
  }

  styleNode(el, node) {
    if (node.kind === POST_KIND) {
      const size = this.cardSizes.get(node.key);
      if (size) {
        el.classList.add('is-sized');
        el.style.width = `${size.w}px`;
        el.style.height = `${size.h}px`;
      }
      return;
    }
    const fontSize = labelSize(node, this.totalPosts);
    el.style.setProperty('--stree-font', `${fontSize}px`);
    el.style.maxWidth = `${topicMaxWidth(fontSize)}px`;
  }

  /** Measure every node, run a variable-size tidy tree and place the nodes. */
  layout() {
    const sizes = new Map();
    this.elements.forEach((el, key) => sizes.set(key, { w: el.offsetWidth, h: el.offsetHeight }));
    const sizeOf = (d) => sizes.get(d.data.key);
    this.d3
      .tree()
      .nodeSize([1, 1])
      .separation(
        (a, b) =>
          (sizeOf(a).h + sizeOf(b).h) / 2 + (a.parent === b.parent ? SIBLING_GAP : BRANCH_GAP)
      )(this.hierarchy);
    const widths = [];
    this.hierarchy.each((d) => {
      widths[d.depth] = Math.max(widths[d.depth] || 0, sizeOf(d).w);
    });
    const offsets = columnOffsets(widths, COLUMN_GAP);
    this.hierarchy.each((d) => {
      const { w, h } = sizeOf(d);
      const shift = this.offsets.get(d.data.key) || { dx: 0, dy: 0 };
      this.positions.set(d.data.key, {
        left: offsets[d.depth] + shift.dx,
        top: d.x - h / 2 + shift.dy,
        w,
        h,
      });
      this.placeNode(d.data.key);
    });
    this.drawLinks();
  }

  placeNode(key) {
    const pos = this.positions.get(key);
    const el = this.elements.get(key);
    if (pos && el) {
      el.style.transform = `translate(${pos.left}px, ${pos.top}px)`;
    }
  }

  drawLinks() {
    if (!this.hierarchy) {
      return;
    }
    const link = this.d3
      .linkHorizontal()
      .x((p) => p[0])
      .y((p) => p[1]);
    const onPath = this.pathKeys();
    this.linksLayer.innerHTML = this.hierarchy
      .links()
      .map(({ source, target }) => {
        const from = this.positions.get(source.data.key);
        const to = this.positions.get(target.data.key);
        const toY =
          target.data.kind === POST_KIND
            ? to.top + Math.min(CARD_ANCHOR_Y, to.h / 2)
            : to.top + to.h / 2;
        const d = link({
          source: [from.left + from.w + 4, from.top + from.h / 2],
          target: [to.left - 4, toY],
        });
        const cls = onPath.has(target.data.key) ? 'stree-link is-on-path' : 'stree-link';
        return `<path class="${cls}" d="${d}"></path>`;
      })
      .join('');
  }

  pathKeys() {
    return new Set(
      this.selectedKey ? pathTo(this.tree, this.selectedKey).map((node) => node.key) : []
    );
  }

  updateSelection() {
    this.markSelection();
    this.drawLinks();
  }

  markSelection() {
    const onPath = this.pathKeys();
    this.elements.forEach((el, key) => {
      el.classList.toggle('is-selected', key === this.selectedKey);
      el.classList.toggle('is-on-path', onPath.has(key));
    });
  }

  nodeHtml(node) {
    return node.kind === POST_KIND ? this.cardHtml(node) : this.topicHtml(node);
  }

  topicHtml(node) {
    const count = node.postIds.length;
    const hidden = node.hiddenCount > 0 ? ` · +${node.hiddenCount} hidden` : '';
    const posts = `<button type="button" class="stree-node__posts" data-branch title="Unfold this branch down to its posts">${count} post${count === 1 ? '' : 's'}</button>`;
    return `<div class="stree-node stree-node--${escapeHtml(node.kind)}${node.hiddenCount ? ' is-collapsed' : ''}" role="button" tabindex="0">
      <div class="stree-node__title">${escapeHtml(node.title)}</div>
      <div class="stree-node__meta">${posts}${escapeHtml(hidden)}</div>
      ${this.statementsBlock(node)}
    </div>`;
  }

  /** Legacy (schema 1) topics carry statements with numbered source references. */
  statementsBlock(display) {
    const node = display.node;
    if (this.payload.result?.schema_version === 2 || !node?.statements?.length) {
      return '';
    }
    const numbers = sourceNumbers(node);
    const chip = (pid) =>
      `<button type="button" class="stree-ref" data-pid="${escapeHtml(pid)}">${numbers.get(pid)}</button>`;
    const items = node.statements
      .map((s) => `<li>${escapeHtml(s.text)} ${(s.sources || []).map(chip).join('')}</li>`)
      .join('');
    return `<details class="stree-node__summary"><summary>Summary</summary><ol class="stree-statements">${items}</ol></details>`;
  }

  cardHtml(display) {
    const post = display.post || {};
    const pid = String(post.pid);
    const claim =
      display.title && display.title !== post.title && display.title !== post.summary_title
        ? `<p class="stree-card__claim">${escapeHtml(display.title)}</p>`
        : '';
    return `<article class="stree-card">
      <header class="stree-card__head" title="Drag to move">
        <div class="stree-card__title">${escapeHtml(post.title || pid)}</div>
        <div class="stree-muted">${escapeHtml(post.feed_title || '')} · ${escapeHtml(formatDate(post.date))}</div>
      </header>
      <div class="stree-card__body">${claim}${this.postPanel(post, display.rows || [], display.key)}</div>
      <div class="stree-card__resize" title="Drag to resize" aria-hidden="true"></div>
    </article>`;
  }

  /** Card body for a post leaf: summary, source passages and supporting context. */
  postPanel(post, rows = [], key = this.selectedKey) {
    const pid = String(post.pid);
    const link = post.url
      ? `<a href="${escapeHtml(post.url)}" target="_blank" rel="noopener">original</a> · `
      : '';
    const citations = this.citations(pid);
    const route = this.payload.result?.schema_version === 2 ? this.fullSummaries(key) : '';
    return `
      ${post.summary ? `<p class="stree-card__summary">${escapeHtml(post.summary)}</p>` : ''}
      ${this.passagesBlock(post, rows)}
      ${route ? `<details class="stree-card__more"><summary>Full summaries along this route</summary>${route}</details>` : ''}
      ${citations ? `<details class="stree-card__more"><summary>Cited in</summary><ul class="stree-sources">${citations}</ul></details>` : ''}
      <p class="stree-card__links">${link}<a href="/posts/${encodeURIComponent(pid)}">open post</a></p>`;
  }

  passagesBlock(post, rows) {
    if (!post.evidence?.length) {
      return '';
    }
    const cited = (index) => rows.some(([first, last]) => index + 1 >= first && index + 1 <= last);
    const items = post.evidence
      .map(
        (text, index) => `<li${cited(index) ? ' class="is-cited"' : ''}>${escapeHtml(text)}</li>`
      )
      .join('');
    return `<ol class="stree-passages${rows.length ? ' has-cited' : ''}">${items}</ol>`;
  }

  fullSummaries(key) {
    const nodes = this.payload.result?.nodes || {};
    const selected = new Map();
    for (const occurrence of pathTo(this.tree, key)) {
      for (const part of occurrence.parts || []) {
        if (!selected.has(part.node)) selected.set(part.node, new Set());
        selected.get(part.node).add(part.segment);
      }
    }
    return [...selected]
      .map(([id, indices]) => {
        const node = nodes[id];
        const prose = (node?.segments || [])
          .map((segment, index) =>
            indices.has(index)
              ? `<mark>${escapeHtml(segment.text)}</mark>`
              : escapeHtml(segment.text)
          )
          .join('');
        return `<section><h3>${escapeHtml(node?.title || '')}</h3><p>${prose}</p></section>`;
      })
      .join('');
  }

  skippedBlock() {
    const skipped = this.payload.result?.skipped || [];
    if (!skipped.length) {
      return '';
    }
    const items = skipped
      .map(
        (post) =>
          `<li>${escapeHtml(post.title || post.pid)} <span class="stree-muted">${escapeHtml(post.reason)}</span></li>`
      )
      .join('');
    return `<details class="stree-skipped"><summary>${skipped.length} posts not used</summary><ul>${items}</ul></details>`;
  }

  citations(pid) {
    const nodes = this.payload.result?.nodes || {};
    return Object.values(nodes)
      .flatMap((node) =>
        (node.statements || [])
          .filter((s) => (s.sources || []).includes(pid))
          .map((s) => `<li><strong>${escapeHtml(node.title)}</strong>: ${escapeHtml(s.text)}</li>`)
      )
      .join('');
  }

  // ---------- interaction ----------

  bindNodes() {
    this.nodesLayer.addEventListener('click', (event) => this.onLayerClick(event));
    this.nodesLayer.addEventListener('keydown', (event) => {
      if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('.stree-node')) {
        event.preventDefault();
        this.onNodeClick(this.keyOf(event.target));
      }
    });
    this.nodesLayer.addEventListener('pointerdown', (event) => this.onPointerDown(event));
    // <details> toggling changes a node's size; `toggle` does not bubble, so capture it.
    this.nodesLayer.addEventListener('toggle', () => this.relayout(), true);
  }

  keyOf(el) {
    for (const [key, node] of this.elements) {
      if (node === el) return key;
    }
    return null;
  }

  onLayerClick(event) {
    const ref = event.target.closest('[data-pid]');
    const owner = event.target.closest('.stree-node, .stree-card');
    if (!owner) {
      return;
    }
    const key = this.keyOf(owner);
    if (event.target.closest('[data-branch]')) {
      this.onBranchClick(key);
      return;
    }
    if (ref) {
      this.selectPost(ref.dataset.pid, key);
      return;
    }
    if (owner.matches('.stree-card')) {
      this.selectCard(key);
      return;
    }
    if (!event.target.closest('details, a')) {
      this.onNodeClick(key);
    }
  }

  onNodeClick(key) {
    if (!key) {
      return;
    }
    const before = this.positions.get(key);
    this.selectedKey = key;
    this.expanded = toggleNode(this.tree, this.expanded, key, this.exclusive);
    this.renderTree();
    this.keepAnchored(key, before);
  }

  onBranchClick(key) {
    if (!key) {
      return;
    }
    const before = this.positions.get(key);
    this.selectedKey = key;
    this.expanded = expandBranch(this.tree, this.expanded, key);
    this.renderTree();
    this.keepAnchored(key, before);
  }

  selectCard(key) {
    this.selectedKey = key;
    this.raise(key);
    this.updateSelection();
  }

  raise(key) {
    this.elements.forEach((el, other) => el.classList.toggle('is-front', other === key));
  }

  selectPost(pid, fromKey) {
    const leaf = findPostLeaf(this.tree, pid, fromKey) || findPostLeaf(this.tree, pid);
    if (!leaf) {
      return;
    }
    const before = this.positions.get(fromKey);
    this.expanded = revealNode(this.tree, this.expanded, leaf);
    this.selectedKey = leaf;
    this.renderTree();
    this.keepAnchored(fromKey, before);
    this.raise(leaf);
  }

  /** Re-measure and re-place the current nodes without rebuilding them. */
  relayout() {
    if (!this.hierarchy) {
      return;
    }
    const before = this.positions.get(this.selectedKey);
    this.layout();
    this.keepAnchored(this.selectedKey, before);
  }

  onPointerDown(event) {
    if (event.button !== 0) {
      return;
    }
    const handle = event.target.closest('.stree-card__head, .stree-card__resize');
    const card = handle?.closest('.stree-card');
    if (!card) {
      return;
    }
    event.preventDefault();
    const key = this.keyOf(card);
    this.selectCard(key);
    const mode = handle.matches('.stree-card__resize') ? 'resize' : 'move';
    this.trackPointer(event, key, (dx, dy, start) =>
      mode === 'move' ? this.moveCard(key, start, dx, dy) : this.resizeCard(key, start, dx, dy)
    );
  }

  /** Follow the pointer in stage coordinates until release. */
  trackPointer(event, key, onMove) {
    const k = this.transform?.k || 1;
    const origin = { x: event.clientX, y: event.clientY };
    const start = {
      ...(this.offsets.get(key) || { dx: 0, dy: 0 }),
      ...this.positions.get(key),
    };
    const move = (e) => onMove((e.clientX - origin.x) / k, (e.clientY - origin.y) / k, start);
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      this.root.classList.remove('is-dragging');
    };
    this.root.classList.add('is-dragging');
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  moveCard(key, start, dx, dy) {
    this.offsets.set(key, { dx: start.dx + dx, dy: start.dy + dy });
    const pos = this.positions.get(key);
    pos.left = start.left + dx;
    pos.top = start.top + dy;
    this.placeNode(key);
    this.drawLinks();
  }

  resizeCard(key, start, dx, dy) {
    const size = clampCardSize(start.w + dx, start.h + dy);
    const el = this.elements.get(key);
    this.cardSizes.set(key, size);
    el.classList.add('is-sized');
    el.style.width = `${size.w}px`;
    el.style.height = `${size.h}px`;
    Object.assign(this.positions.get(key), size);
    this.drawLinks();
  }
}

// ============================================================
// Entry point
// ============================================================

export function initSummaryTree() {
  const root = document.getElementById('summary-tree-app');
  const data = readJsonScript('summary-tree-data');
  if (!root || !data) {
    return null;
  }
  if (data.mode !== 'detail') {
    renderList(root, data);
    return null;
  }
  const view = new SummaryTreeView(root, data.tree, window.d3);
  view.mount();
  view.schedulePoll();
  return view;
}
