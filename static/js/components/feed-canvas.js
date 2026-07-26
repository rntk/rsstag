/* global CSS, CustomEvent, Element, console, document, fetch, window */

/** Fired on `#feed_canvas` when the toolbar moves it and its cached rect goes stale. */
const CANVAS_OFFSET_EVENT = 'canvas:offsetchange';

/* Topic card width, gap, rail padding and base font size live in
   static/css/style.scss, which derives them from the zoom scalars set by
   FeedCanvas#applyTransform. */
const MIN_SCALE = 0.15;
const MAX_SCALE = 1.8;
const ZOOM_FACTOR = 1.1;
const TOPIC_ZOOM_SCALE = 1.6;
const ARROW_PAN_STEP = 80;
const PAGE_STEP_RATIO = 0.8;
const TOPIC_CARD_CHROME_HEIGHT = 30;
const COMPACT_TOPIC_CARD_HEIGHT = 70;
/** Screen px rendered beyond each viewport edge, so panning has slack. */
const CARD_OVERSCAN = 300;

/**
 * Indices of the layouts overlapping the vertical band `[top, bottom]`, in
 * content coordinates.
 *
 * `layouts` must be sorted by `top`. A binary search finds the first candidate,
 * but a card taller than the gap can start above the band and still reach into
 * it, so the scan starts `maxHeight` earlier -- exact, and still O(log n).
 *
 * @param {Array<{top: number, height: number}>} layouts
 * @param {number} top
 * @param {number} bottom
 * @param {number} maxHeight
 * @returns {number[]}
 */
export function visibleLayoutIndices(layouts, top, bottom, maxHeight) {
  let low = 0;
  let high = layouts.length;
  const from = top - maxHeight;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (layouts[middle].top < from) low = middle + 1;
    else high = middle;
  }
  /** @type {number[]} */
  const visible = [];
  for (let index = low; index < layouts.length && layouts[index].top <= bottom; index += 1) {
    if (layouts[index].top + layouts[index].height >= top) visible.push(index);
  }
  return visible;
}

/** @param {number[]} left @param {number[]} right @returns {boolean} */
function sameIndices(left, right) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

/**
 * Prototype card, cloned for the pool. Built with createElement rather than
 * innerHTML so recycling never re-parses markup.
 *
 * @returns {HTMLDivElement}
 */
function createCardTemplate() {
  const card = document.createElement('div');
  card.className = 'canvas-topic-card';
  card.tabIndex = 0;
  card.setAttribute('role', 'button');
  const menu = document.createElement('button');
  menu.type = 'button';
  menu.className = 'canvas-topic-card__menu';
  menu.setAttribute('aria-label', 'Topic actions');
  menu.title = 'Topic actions';
  menu.textContent = '⋮';
  const name = document.createElement('span');
  name.className = 'canvas-topic-card__name';
  const meta = document.createElement('span');
  meta.className = 'canvas-topic-card__meta';
  card.append(menu, name, meta);
  return card;
}

/**
 * Keep the canvas below the global toolbar and update the shared CSS variable
 * used by pages with a fixed `#global_tools` element.
 *
 * @returns {void}
 */
export function syncGlobalToolsOffset() {
  const sharedTools = document.querySelector('#global_tools');
  const pageHeader = document.querySelector('.canvas-page__header');
  const tools = sharedTools || pageHeader;
  if (!tools) {
    document.documentElement.style.removeProperty('--global-tools-height');
    return;
  }

  const isHidden = (element) => {
    const computed =
      typeof window.getComputedStyle === 'function'
        ? window.getComputedStyle(element)
        : { display: '', visibility: '' };
    return (
      element.style.display === 'none' ||
      computed.display === 'none' ||
      computed.visibility === 'hidden'
    );
  };
  const measure = (element) => {
    if (!element || isHidden(element)) return 0;
    return Math.ceil(element.getBoundingClientRect().height);
  };
  const toolsHidden = isHidden(tools);
  const toolsHeight = toolsHidden ? 0 : measure(tools);
  const pageHeaderHeight = sharedTools && pageHeader ? measure(pageHeader) : 0;
  const height = toolsHeight + pageHeaderHeight;
  const content = document.querySelector('#feed_canvas');
  if (!toolsHidden && toolsHeight > 0) {
    document.documentElement.style.setProperty('--global-tools-height', `${height}px`);
  }
  if (content && (height > 0 || toolsHidden)) {
    content.style.top = `${height}px`;
    // FeedCanvas caches this element's rect; announce that it just moved so the
    // cache is dropped at the moment of the change rather than on the scroll
    // that scheduled it.
    content.dispatchEvent(new CustomEvent(CANVAS_OFFSET_EVENT));
  }
}

/**
 * Add the app-wide toolbar behaviour to the standalone canvas page. The page
 * has its own header, while deployments using the shared header expose it as
 * `#global_tools`.
 *
 * @returns {void}
 */
export function setupGlobalTools() {
  const tools =
    document.querySelector('#global_tools') || document.querySelector('.canvas-page__header');
  const bottomTools = document.querySelector('#global_tools_bottom');
  if (!tools || tools.dataset.globalToolsBound === 'true') return;

  tools.dataset.globalToolsBound = 'true';
  tools.dataset.globalToolsDisplay = window.getComputedStyle(tools).display || 'block';
  const apply = () => syncGlobalToolsOffset();
  apply();
  window.addEventListener('resize', apply);

  if (typeof window.ResizeObserver !== 'undefined') {
    const observer = new window.ResizeObserver(apply);
    observer.observe(tools);
  }

  if (window.EVSYS && typeof window.EVSYS.bind === 'function') {
    window.EVSYS.bind(window.EVSYS.CONTEXT_FILTER_UPDATED, apply);
  }

  // These also re-announce the offset after FeedCanvas has bound its listeners.
  // setupGlobalTools runs before FeedCanvas#init, so the `apply()` above fires
  // CANVAS_OFFSET_EVENT with nobody listening; dropping these would leave a
  // rect cached during startup with nothing to invalidate it.
  window.setTimeout(apply, 0);
  window.setTimeout(apply, 250);

  let previousScroll = window.scrollY;
  let timeout = 0;
  window.addEventListener('scroll', () => {
    window.clearTimeout(timeout);
    if (previousScroll === window.scrollY) return;
    timeout = window.setTimeout(() => {
      const currentScroll = window.scrollY;
      const shouldShow = previousScroll > currentScroll;
      tools.style.display = shouldShow ? tools.dataset.globalToolsDisplay : 'none';
      if (bottomTools) bottomTools.style.display = shouldShow ? 'block' : 'none';
      apply();
      previousScroll = currentScroll;
    }, 150);
  });
}

/** @returns {string} */
function topicColor(path) {
  let hash = 0;
  for (let index = 0; index < path.length; index += 1) {
    hash = (hash * 31 + path.charCodeAt(index)) >>> 0;
  }
  return `hsl(${hash % 360} 55% 48%)`;
}

/** @param {number[]} numbers @returns {number[][]} */
function splitRuns(numbers) {
  const sorted = [...new Set(numbers)].sort((left, right) => left - right);
  /** @type {number[][]} */
  const runs = [];
  sorted.forEach((number) => {
    const current = runs[runs.length - 1];
    if (!current || number !== current[current.length - 1] + 1) {
      runs.push([number]);
    } else {
      current.push(number);
    }
  });
  return runs;
}

/** @param {Array<Record<string, unknown>>} posts */
function buildTopicNodes(posts) {
  /** @type {Map<string, {path: string, name: string, depth: number, posts: Map<string, Set<number>>}>} */
  const nodes = new Map();
  posts.forEach((post) => {
    const postId = String(post.post_id || '');
    const groups = post.groups && typeof post.groups === 'object' ? post.groups : {};
    Object.entries(groups).forEach(([topicPath, rawNumbers]) => {
      const parts = topicPath
        .split('>')
        .map((part) => part.trim())
        .filter(Boolean);
      const numbers = Array.isArray(rawNumbers)
        ? rawNumbers.filter((number) => Number.isInteger(number))
        : [];
      parts.forEach((name, depth) => {
        const path = parts.slice(0, depth + 1).join(' > ');
        const node = nodes.get(path) || { path, name, depth, posts: new Map() };
        const postNumbers = node.posts.get(postId) || new Set();
        numbers.forEach((number) => postNumbers.add(number));
        node.posts.set(postId, postNumbers);
        nodes.set(path, node);
      });
    });
  });
  return [...nodes.values()];
}

class FeedCanvas {
  constructor() {
    /** @type {Array<Record<string, unknown>>} */
    this.posts = Array.isArray(window.canvasPosts) ? window.canvasPosts : [];
    this.root = document.getElementById('feed_canvas');
    this.viewport = document.getElementById('feed_canvas_viewport');
    this.document = document.getElementById('feed_canvas_document');
    this.rail = document.getElementById('canvas_topic_rail');
    this.cards = document.getElementById('canvas_topic_cards');
    this.levels = document.getElementById('canvas_levels');
    /** @type {Map<string, Record<string, unknown>>} */
    this.postsById = new Map(this.posts.map((post) => [String(post.post_id || ''), post]));
    /**
     * postId -> sentence number -> span. Built in one pass so geometry and
     * highlighting never run a document-wide attribute-selector match per
     * sentence.
     *
     * @type {Map<string, Map<number, Element>>}
     */
    this.sentenceIndex = new Map();
    this.nodes = buildTopicNodes(this.posts);
    this.maxLevel = Math.max(0, ...this.nodes.map((node) => node.depth));
    this.selectedLevel = this.maxLevel;
    this.scale = 1;
    this.x = 40;
    this.y = 30;
    this.drag = null;
    this.resizeTimer = 0;
    /** @type {Map<string, string>} */
    this.summaries = new Map();
    /** Layout keys with a summary request in flight. */
    /** @type {Set<string>} */
    this.summaryLoadingKeys = new Set();
    this.contextMenu = null;
    this.summaryDialog = null;
    this.statusTimer = 0;
    /** @type {Map<string, {top: number, bottom: number, left: number, right: number}>} */
    this.sentenceMetrics = new Map();
    /** @type {{scale: number, x: number, y: number}|null} */
    this.savedView = null;
    /** Cached viewport rect; invalidated on resize, scroll and root resize. */
    /** @type {DOMRect|null} */
    this.rootRect = null;
    /** Scale last written to the DOM, so panning skips the zoom-only writes. */
    /** @type {number|null} */
    this.appliedScale = null;
    this.zoomFrame = 0;
    /** @type {{factor: number, clientX: number, clientY: number}|null} */
    this.pendingZoom = null;
    /**
     * Every card position, sorted by `top`. Only the slice on screen is ever
     * given a DOM node.
     *
     * @type {Array<{node: ReturnType<typeof buildTopicNodes>[number], postId: string, run: number[], top: number, height: number, left: number, width: number}>}
     */
    this.layouts = [];
    this.maxCardHeight = 0;
    /** Recycled card elements, index-aligned with `renderedIndices`. */
    /** @type {HTMLDivElement[]} */
    this.cardPool = [];
    /** @type {HTMLDivElement|null} */
    this.cardTemplate = null;
    /** @type {number[]} */
    this.renderedIndices = [];
    /** Layout index whose card currently owns keyboard focus. */
    /** @type {number|null} */
    this.focusedLayoutIndex = null;
    this.cullFrame = 0;
    /** Selection and hover live here, not on the DOM, because cards recycle. */
    /** @type {object|null} */
    this.selectedLayout = null;
    /** @type {object|null} */
    this.hoverLayout = null;
  }

  init() {
    if (!this.root || !this.viewport || !this.document || !this.rail || !this.cards) return;
    this.renderLevelButtons();
    this.buildSentenceIndex();
    this.bindEvents();
    this.bindCardEvents();
    this.applyTransform();
    this.createSummaryDialog();
    // Sentence geometry depends on the webfonts, so laying out before they
    // arrive means measuring everything twice. Lay out once, as late as needed.
    if (document.fonts && document.fonts.status !== 'loaded') {
      document.fonts.ready.then(() => this.layoutTopics());
    } else {
      this.layoutTopics();
    }
  }

  /** @returns {void} */
  buildSentenceIndex() {
    this.sentenceIndex = new Map();
    this.document?.querySelectorAll('.canvas-post[data-post-id]').forEach((postElement) => {
      /** @type {Map<number, Element>} */
      const byNumber = new Map();
      postElement
        .querySelectorAll('.canvas-sentence[data-sentence-number]')
        .forEach((sentence) => {
          byNumber.set(Number(sentence.getAttribute('data-sentence-number')), sentence);
        });
      this.sentenceIndex.set(postElement.getAttribute('data-post-id') || '', byNumber);
    });
  }

  /** @param {string} postId @param {number} number @returns {Element|null} */
  getSentenceElement(postId, number) {
    return this.sentenceIndex.get(postId)?.get(number) || null;
  }

  renderLevelButtons() {
    if (!this.levels || this.nodes.length === 0) return;
    for (let level = 0; level <= this.maxLevel; level += 1) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = String(level + 1);
      button.title = `Show topic levels 1–${level + 1}`;
      button.classList.toggle('is-active', level === this.selectedLevel);
      button.addEventListener('click', () => {
        this.selectedLevel = level;
        this.levels?.querySelectorAll('button').forEach((item, index) => {
          item.classList.toggle('is-active', index === level);
        });
        this.layoutTopics();
      });
      this.levels.appendChild(button);
    }
  }

  bindEvents() {
    this.root?.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || event.target.closest('a, button, .canvas-topic-card')) return;
      this.drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
      this.root?.setPointerCapture(event.pointerId);
      this.root?.classList.add('is-dragging');
    });
    this.root?.addEventListener('pointermove', (event) => {
      if (!this.drag || event.pointerId !== this.drag.pointerId) return;
      this.x += event.clientX - this.drag.x;
      this.y += event.clientY - this.drag.y;
      this.drag.x = event.clientX;
      this.drag.y = event.clientY;
      this.applyTransform();
    });
    const stopDragging = () => {
      this.drag = null;
      this.root?.classList.remove('is-dragging');
    };
    this.root?.addEventListener('pointerup', stopDragging);
    this.root?.addEventListener('pointercancel', stopDragging);
    this.root?.addEventListener(
      'wheel',
      (event) => {
        event.preventDefault();
        const factor = event.deltaY < 0 ? ZOOM_FACTOR : 1 / ZOOM_FACTOR;
        this.queueZoom(factor, event.clientX, event.clientY);
      },
      { passive: false }
    );
    document
      .querySelector('[data-canvas-action="zoom-in"]')
      ?.addEventListener('click', () => this.zoomByFactor(ZOOM_FACTOR));
    document
      .querySelector('[data-canvas-action="zoom-out"]')
      ?.addEventListener('click', () => this.zoomByFactor(1 / ZOOM_FACTOR));
    document
      .querySelector('[data-canvas-action="reset"]')
      ?.addEventListener('click', () => this.reset());
    this.document?.querySelectorAll('[data-post-read-toggle]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        const postElement = button.closest('.canvas-post');
        const postId = postElement?.getAttribute('data-post-id');
        if (!postId) return;
        const post = this.findPost(postId);
        if (post) this.changePostsReadState([postId], !post.read);
      });
    });
    document.querySelectorAll('[data-canvas-read-all]').forEach((button) => {
      button.addEventListener('click', () => {
        const read = button.getAttribute('data-canvas-read-all') === 'true';
        const postIds = this.posts
          .filter((post) => post.read !== read)
          .map((post) => String(post.post_id || ''))
          .filter(Boolean);
        this.changePostsReadState(postIds, read);
      });
    });
    window.addEventListener('keydown', (event) => this.handleKeyDown(event));
    window.addEventListener('pointerdown', (event) => {
      if (!this.contextMenu?.contains(event.target)) this.closeContextMenu();
    });
    const invalidateRootRect = () => {
      this.rootRect = null;
    };
    window.addEventListener('resize', () => {
      invalidateRootRect();
      window.clearTimeout(this.resizeTimer);
      this.resizeTimer = window.setTimeout(() => {
        this.sentenceMetrics.clear();
        this.layoutTopics();
      }, 100);
    });
    // The canvas is `position: fixed`, so page scrolling leaves its rect alone.
    // The one thing that moves it is syncGlobalToolsOffset rewriting `top` when
    // the toolbar shows or hides, which it announces here. That runs on a
    // timeout after the scroll, so listening to scroll itself would invalidate
    // too early and re-cache the pre-move rect.
    this.root?.addEventListener(CANVAS_OFFSET_EVENT, invalidateRootRect);
    if (typeof window.ResizeObserver !== 'undefined' && this.root) {
      new window.ResizeObserver(invalidateRootRect).observe(this.root);
    }
  }

  /**
   * The canvas is `position: fixed`, so its rect only moves on resize or when
   * the toolbar shows/hides. Caching it keeps the zoom path from forcing a
   * synchronous reflow on every wheel event.
   *
   * @returns {DOMRect|null}
   */
  getRootRect() {
    if (!this.rootRect && this.root) this.rootRect = this.root.getBoundingClientRect();
    return this.rootRect;
  }

  /**
   * Collapse the wheel events that arrive within one frame into a single zoom.
   * Trackpads emit far more than one per frame, and each one would otherwise
   * read layout and write the transform.
   *
   * @param {number} factor
   * @param {number} clientX
   * @param {number} clientY
   */
  queueZoom(factor, clientX, clientY) {
    if (this.pendingZoom) {
      this.pendingZoom.factor *= factor;
      this.pendingZoom.clientX = clientX;
      this.pendingZoom.clientY = clientY;
    } else {
      this.pendingZoom = { factor, clientX, clientY };
    }
    if (this.zoomFrame) return;
    this.zoomFrame = window.requestAnimationFrame(() => {
      this.zoomFrame = 0;
      const pending = this.pendingZoom;
      this.pendingZoom = null;
      if (pending) this.zoomByFactor(pending.factor, pending.clientX, pending.clientY);
    });
  }

  /** @param {string} postId @returns {Record<string, unknown>|undefined} */
  findPost(postId) {
    return this.postsById.get(postId);
  }

  /** @param {string} message @param {boolean} [isError] */
  showStatus(message, isError = false) {
    const status = document.querySelector('[data-canvas-status]');
    if (!status) return;
    window.clearTimeout(this.statusTimer);
    status.textContent = message;
    status.classList.toggle('is-error', isError);
    this.statusTimer = window.setTimeout(() => {
      status.textContent = '';
      status.classList.remove('is-error');
    }, 5000);
  }

  /** @param {string} postId @param {boolean} read */
  renderPostReadState(postId, read) {
    const selector = `.canvas-post[data-post-id="${CSS.escape(postId)}"]`;
    const postElement = this.document?.querySelector(selector);
    const button = postElement?.querySelector('[data-post-read-toggle]');
    postElement?.classList.toggle('is-read', read);
    if (button) {
      button.textContent = read ? 'Mark unread' : 'Mark read';
      button.setAttribute('aria-pressed', String(read));
    }
  }

  /**
   * @param {string[]} postIds
   * @param {boolean} read
   * @returns {Promise<void>}
   */
  async changePostsReadState(postIds, read) {
    if (postIds.length === 0) {
      this.showStatus(`All posts are already ${read ? 'read' : 'unread'}.`);
      return;
    }
    const buttons = document.querySelectorAll('[data-post-read-toggle], [data-canvas-read-all]');
    buttons.forEach((button) => button.setAttribute('disabled', ''));
    try {
      const response = await fetch('/read/posts', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: postIds, readed: read }),
      });
      if (!response.ok) throw new Error(`Request failed with status ${response.status}.`);
      postIds.forEach((postId) => {
        const post = this.findPost(postId);
        if (post) post.read = read;
        this.renderPostReadState(postId, read);
      });
      const noun = postIds.length === 1 ? 'post' : 'posts';
      this.showStatus(`${postIds.length} ${noun} marked ${read ? 'read' : 'unread'}.`);
    } catch (error) {
      console.error('Unable to update canvas post read state.', error);
      this.showStatus('Unable to update read status. Please try again.', true);
    } finally {
      buttons.forEach((button) => button.removeAttribute('disabled'));
    }
  }

  /** @param {number} factor @param {number|null} [clientX] @param {number|null} [clientY] */
  zoomByFactor(factor, clientX = null, clientY = null) {
    const rect = this.getRootRect();
    if (!rect) return;
    const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, this.scale * factor));
    if (nextScale === this.scale) return;
    const focusX = clientX ?? rect.left + rect.width / 2;
    const focusY = clientY ?? rect.top + rect.height / 2;
    const contentX = (focusX - rect.left - this.x) / this.scale;
    const contentY = (focusY - rect.top - this.y) / this.scale;
    this.x = focusX - rect.left - contentX * nextScale;
    this.y = focusY - rect.top - contentY * nextScale;
    this.scale = nextScale;
    this.applyTransform();
  }

  reset() {
    this.scale = 1;
    this.x = 40;
    this.y = 30;
    this.applyTransform();
  }

  /** @param {{top: number, height: number, left: number, width: number}} layout */
  zoomToLayout(layout) {
    const rect = this.getRootRect();
    if (!rect || !this.document) return;
    if (!this.savedView) this.savedView = { scale: this.scale, x: this.x, y: this.y };
    const targetScale = Math.min(MAX_SCALE, Math.max(this.savedView.scale, TOPIC_ZOOM_SCALE));
    const centerX = layout.left + layout.width / 2;
    const centerY = layout.top + layout.height / 2;
    this.scale = targetScale;
    this.x = rect.width / 2 - centerX * targetScale;
    this.y = rect.height / 2 - centerY * targetScale;
    this.applyTransform();
  }

  restoreView() {
    if (!this.savedView) return;
    this.scale = this.savedView.scale;
    this.x = this.savedView.x;
    this.y = this.savedView.y;
    this.savedView = null;
    this.applyTransform();
  }

  /** @param {number} dx @param {number} dy */
  panBy(dx, dy) {
    this.x += dx;
    this.y += dy;
    this.applyTransform();
  }

  /** @param {'top'|'bottom'|'prev'|'next'} position */
  navigate(position) {
    if (!this.root || !this.document) return;
    const pageStep = Math.max(120, this.root.clientHeight * PAGE_STEP_RATIO);
    if (position === 'top') {
      this.y = 30;
    } else if (position === 'bottom') {
      this.y = Math.min(30, this.root.clientHeight - this.document.offsetHeight * this.scale - 30);
    } else {
      this.y += position === 'prev' ? pageStep : -pageStep;
    }
    this.applyTransform();
  }

  /** @param {KeyboardEvent} event */
  handleKeyDown(event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.matches('input, textarea, select') || target.isContentEditable) return;
    /** @type {Record<string, () => void>} */
    const actions = {
      Home: () => this.navigate('top'),
      End: () => this.navigate('bottom'),
      PageUp: () => this.navigate('prev'),
      PageDown: () => this.navigate('next'),
      ArrowUp: () => this.panBy(0, ARROW_PAN_STEP),
      ArrowDown: () => this.panBy(0, -ARROW_PAN_STEP),
      ArrowLeft: () => this.panBy(ARROW_PAN_STEP, 0),
      ArrowRight: () => this.panBy(-ARROW_PAN_STEP, 0),
      '+': () => this.zoomByFactor(ZOOM_FACTOR),
      '=': () => this.zoomByFactor(ZOOM_FACTOR),
      '-': () => this.zoomByFactor(1 / ZOOM_FACTOR),
      0: () => this.reset(),
    };
    const action = actions[event.key];
    if (!action) return;
    event.preventDefault();
    action();
  }

  /**
   * Zoom is two style writes on one element. The topic rail counter-scales
   * itself from `--topic-inv-zoom` / `--topic-font-zoom` in CSS, so no card is
   * touched here. The zoom-only properties are inherited by the whole canvas
   * subtree, so skip them while panning to avoid invalidating it needlessly.
   *
   * @returns {void}
   */
  applyTransform() {
    const style = this.viewport?.style;
    if (!style) return;
    style.setProperty('--canvas-x', `${this.x}px`);
    style.setProperty('--canvas-y', `${this.y}px`);
    if (this.appliedScale !== this.scale) {
      this.appliedScale = this.scale;
      style.setProperty('--canvas-zoom', String(this.scale));
      style.setProperty('--topic-inv-zoom', String(Math.max(1, 1 / this.scale)));
      style.setProperty('--topic-font-zoom', String(Math.max(1, 1.25 / this.scale - 0.25)));
    }
    // Panning and zooming both change which cards are on screen.
    this.scheduleCull();
  }

  /**
   * Upper bound on a card's title font size, from the space the card has. It
   * depends only on the card height, so CSS can cap the zoom-driven size with
   * it without recomputing anything per zoom step.
   *
   * @param {number} cardHeight
   * @returns {number}
   */
  getTopicFontCap(cardHeight) {
    const titleLines = cardHeight < COMPACT_TOPIC_CARD_HEIGHT ? 1 : 2;
    const availableHeight = Math.max(1, cardHeight - TOPIC_CARD_CHROME_HEIGHT);
    return availableHeight / (titleLines * 1.25);
  }

  /** @param {string} postId @param {number} number @param {DOMRect} documentRect */
  getSentenceMetrics(postId, number, documentRect) {
    const key = `${postId}\u0000${number}`;
    const cached = this.sentenceMetrics.get(key);
    if (cached) return cached;
    const rect = this.getSentenceElement(postId, number)?.getBoundingClientRect();
    if (!rect) return null;
    const metrics = {
      top: (rect.top - documentRect.top) / this.scale,
      bottom: (rect.bottom - documentRect.top) / this.scale,
      left: (rect.left - documentRect.left) / this.scale,
      right: (rect.right - documentRect.left) / this.scale,
    };
    this.sentenceMetrics.set(key, metrics);
    return metrics;
  }

  layoutTopics() {
    if (!this.document || !this.rail || !this.cards) return;
    // The pool stays attached across re-layouts: `cardPool` holds references to
    // these nodes, so detaching them here would leave the pool full of orphans
    // and renderVisibleCards would never append anything again.
    const visibleNodes = this.nodes.filter((node) => node.depth <= this.selectedLevel);
    this.rail.style.setProperty('--rail-columns', String(this.selectedLevel + 1));
    this.rail.style.setProperty('--rail-gaps', String(this.selectedLevel));
    const documentRect = this.document.getBoundingClientRect();
    /** @type {Array<{node: ReturnType<typeof buildTopicNodes>[number], postId: string, run: number[], top: number, height: number}>} */
    const layouts = [];
    visibleNodes.forEach((node) => {
      node.posts.forEach((numbers, postId) => {
        splitRuns([...numbers]).forEach((run) => {
          const metrics = run
            .map((number) => this.getSentenceMetrics(postId, number, documentRect))
            .filter(Boolean);
          if (metrics.length === 0) return;
          const top = Math.min(...metrics.map((metric) => metric.top));
          const bottom = Math.max(...metrics.map((metric) => metric.bottom));
          const left = Math.min(...metrics.map((metric) => metric.left));
          const right = Math.max(...metrics.map((metric) => metric.right));
          layouts.push({
            node,
            postId,
            run,
            top,
            height: bottom - top,
            left,
            width: right - left,
          });
        });
      });
    });

    // Highlights hang off layouts that are about to be replaced.
    this.setSentenceHighlight(this.selectedLayout, false);
    this.setSentenceHighlight(this.hoverLayout, false);
    this.selectedLayout = null;
    this.hoverLayout = null;
    // Nothing is selected any more, so there is no view left to restore to.
    this.savedView = null;

    layouts.sort((left, right) => left.top - right.top);
    this.layouts = layouts;
    this.maxCardHeight = layouts.reduce(
      (maximum, layout) => Math.max(maximum, layout.height),
      0
    );
    this.focusedLayoutIndex = null;
    this.renderedIndices = [];
    this.cardPool.forEach((card) => {
      card.hidden = true;
      delete card.dataset.layoutIndex;
    });

    const postsHeight = document.getElementById('canvas_posts')?.offsetHeight || 0;
    const cardsHeight = layouts.reduce(
      (maximum, layout) => Math.max(maximum, layout.top + layout.height),
      0
    );
    this.cards.style.height = `${Math.max(postsHeight, cardsHeight) + 24}px`;
    this.renderVisibleCards();
  }

  /**
   * Content-space band on screen, padded by CARD_OVERSCAN screen px.
   *
   * @returns {{top: number, bottom: number}}
   */
  getVisibleBand() {
    const rect = this.getRootRect();
    const height = rect ? rect.height : window.innerHeight;
    return {
      top: (-this.y - CARD_OVERSCAN) / this.scale,
      bottom: (height - this.y + CARD_OVERSCAN) / this.scale,
    };
  }

  scheduleCull() {
    if (this.cullFrame) return;
    this.cullFrame = window.requestAnimationFrame(() => {
      this.cullFrame = 0;
      this.renderVisibleCards();
    });
  }

  /**
   * Give a DOM node only to the cards on screen, reusing the pool. The whole
   * rail is tens of thousands of cards; the viewport holds tens.
   *
   * @returns {void}
   */
  renderVisibleCards() {
    if (!this.cards) return;
    const band = this.getVisibleBand();
    const visible = visibleLayoutIndices(
      this.layouts,
      band.top,
      band.bottom,
      this.maxCardHeight
    );
    const activeCard = document.activeElement?.closest?.('.canvas-topic-card');
    const activeElement = document.activeElement;
    const activeLayoutAttribute = activeCard?.getAttribute('data-layout-index');
    const activeLayoutIndex =
      activeCard && this.cards.contains(activeCard) && activeLayoutAttribute !== null
        ? Number(activeLayoutAttribute)
        : null;
    [this.focusedLayoutIndex, activeLayoutIndex]
      .filter((index) => Number.isInteger(index) && index >= 0 && index < this.layouts.length)
      .forEach((index) => {
        if (!visible.includes(index)) visible.push(index);
      });
    visible.sort((left, right) => left - right);
    if (sameIndices(visible, this.renderedIndices)) return;
    this.renderedIndices = visible;
    if (!this.cardTemplate) this.cardTemplate = createCardTemplate();
    while (this.cardPool.length < visible.length) {
      const card = /** @type {HTMLDivElement} */ (this.cardTemplate.cloneNode(true));
      this.cardPool.push(card);
      this.cards.appendChild(card);
    }
    visible.forEach((layoutIndex, poolIndex) => {
      this.bindCard(this.cardPool[poolIndex], layoutIndex);
    });
    for (let index = visible.length; index < this.cardPool.length; index += 1) {
      this.cardPool[index].hidden = true;
    }
    if (activeLayoutIndex !== null) {
      const activeCardAfterRender = this.cardForLayoutIndex(activeLayoutIndex);
      if (activeCardAfterRender && activeCardAfterRender !== activeCard) {
        const focusTarget =
          activeElement?.classList?.contains('canvas-topic-card__menu')
            ? activeCardAfterRender.querySelector('.canvas-topic-card__menu')
            : activeCardAfterRender;
        focusTarget?.focus();
      }
    }
  }

  /** @param {HTMLDivElement} card @param {number} layoutIndex */
  bindCard(card, layoutIndex) {
    const layout = this.layouts[layoutIndex];
    // A pooled node may have belonged to a different layout while its
    // summary request was pending. Recompute all transient state below.
    card.classList.remove('is-summary-loading');
    card.dataset.layoutIndex = String(layoutIndex);
    card.style.top = `${layout.top}px`;
    card.style.height = `${layout.height}px`;
    // Width, horizontal offset and font size are derived in CSS from these and
    // the viewport's zoom scalars, so zooming never rewrites them.
    card.style.setProperty('--topic-depth', String(layout.node.depth));
    card.style.setProperty('--topic-font-cap', `${this.getTopicFontCap(layout.height)}px`);
    card.style.setProperty('--topic-color', topicColor(layout.node.path));
    card.style.setProperty(
      '--topic-title-lines',
      layout.height < COMPACT_TOPIC_CARD_HEIGHT ? '1' : '2'
    );
    card.title = layout.node.path;
    card.children[1].textContent = layout.node.name;
    card.children[2].textContent = `${layout.run.length} sent.`;
    card.hidden = false;
    this.refreshCardState(card, layout);
  }

  /** @param {HTMLElement} card @param {object} layout */
  refreshCardState(card, layout) {
    const selected = this.selectedLayout === layout;
    card.classList.toggle('is-selected', selected);
    card.classList.toggle('is-active', selected || this.hoverLayout === layout);
    card.classList.toggle('is-summary-loading', this.summaryLoadingKeys.has(this.summaryKey(layout)));
  }

  /** @param {number} layoutIndex @returns {HTMLDivElement|null} */
  cardForLayoutIndex(layoutIndex) {
    return (
      this.cardPool.find(
        (card) => !card.hidden && Number(card.getAttribute('data-layout-index')) === layoutIndex
      ) || null
    );
  }

  refreshVisibleCardStates() {
    this.renderedIndices.forEach((layoutIndex, poolIndex) => {
      this.refreshCardState(this.cardPool[poolIndex], this.layouts[layoutIndex]);
    });
  }

  /** @param {object|null} layout @param {boolean} active */
  setSentenceHighlight(layout, active) {
    if (!layout) return;
    layout.run.forEach((number) => {
      this.getSentenceElement(layout.postId, number)?.classList.toggle(
        'is-topic-active',
        active
      );
    });
  }

  /** @param {object|null} layout */
  setHoverLayout(layout) {
    if (this.hoverLayout === layout) return;
    const previous = this.hoverLayout;
    this.hoverLayout = layout;
    if (previous && previous !== this.selectedLayout) this.setSentenceHighlight(previous, false);
    if (layout) this.setSentenceHighlight(layout, true);
    this.refreshVisibleCardStates();
  }

  /** @param {object} layout */
  selectLayout(layout) {
    const previous = this.selectedLayout;
    if (previous) this.setSentenceHighlight(previous, previous === this.hoverLayout);
    this.selectedLayout = previous === layout ? null : layout;
    if (this.selectedLayout) {
      this.setSentenceHighlight(this.selectedLayout, true);
      this.zoomToLayout(this.selectedLayout);
    } else {
      this.restoreView();
    }
    this.refreshVisibleCardStates();
  }

  /** @param {Element|null} card @returns {object|null} */
  layoutForCard(card) {
    const index = card instanceof Element ? card.getAttribute('data-layout-index') : null;
    return index === null ? null : this.layouts[Number(index)] || null;
  }

  /**
   * One listener set for the whole rail. Per-card listeners are impossible once
   * cards recycle, and there were five per card across all of them.
   *
   * @returns {void}
   */
  bindCardEvents() {
    if (!this.cards) return;
    this.cards.addEventListener('click', (event) => {
      const card = event.target.closest?.('.canvas-topic-card');
      const layout = this.layoutForCard(card);
      if (!layout) return;
      const menu = event.target.closest('.canvas-topic-card__menu');
      if (menu) {
        event.stopPropagation();
        this.openContextMenu(menu, layout, card);
        return;
      }
      this.selectLayout(layout);
    });
    this.cards.addEventListener('keydown', (event) => {
      const card = event.target.closest?.('.canvas-topic-card');
      if (event.key === 'Tab' && card) {
        const currentIndex = Number(card.getAttribute('data-layout-index'));
        const menu = card.querySelector('.canvas-topic-card__menu');
        const targetIsCard = event.target === card;
        const targetIsMenu = event.target === menu;
        // Preserve the card's own menu in the tab order before moving to the
        // next topic, but materialize that topic while the card is focused.
        if (!event.shiftKey && targetIsCard && menu) {
          const nextIndex = currentIndex + 1;
          if (nextIndex < this.layouts.length) {
            this.focusedLayoutIndex = nextIndex;
            this.renderVisibleCards();
          }
          return;
        }
        // Let Shift+Tab return from the menu to its card.
        if (event.shiftKey && targetIsMenu) {
          return;
        }
        const nextIndex = currentIndex + (event.shiftKey ? -1 : 1);
        if (
          !Number.isInteger(currentIndex) ||
          nextIndex < 0 ||
          nextIndex >= this.layouts.length
        ) {
          return;
        }
        event.preventDefault();
        this.focusedLayoutIndex = nextIndex;
        this.renderVisibleCards();
        this.cardForLayoutIndex(nextIndex)?.focus();
        return;
      }
      if (event.key !== 'Enter' && event.key !== ' ') return;
      const layout = this.layoutForCard(event.target.closest?.('.canvas-topic-card'));
      if (!layout) return;
      event.preventDefault();
      this.selectLayout(layout);
    });
    this.cards.addEventListener('focusin', (event) => {
      const card = event.target.closest?.('.canvas-topic-card');
      if (!card || !this.cards.contains(card)) return;
      const layoutIndex = Number(card.getAttribute('data-layout-index'));
      this.focusedLayoutIndex = Number.isInteger(layoutIndex) ? layoutIndex : null;
    });
    this.cards.addEventListener('focusout', (event) => {
      const card = event.target.closest?.('.canvas-topic-card');
      if (!card || card.contains(event.relatedTarget)) return;
      this.focusedLayoutIndex = null;
    });
    // mouseenter/mouseleave do not bubble, so delegation needs the over/out
    // pair plus a relatedTarget check to ignore moves inside the same card.
    this.cards.addEventListener('mouseover', (event) => {
      const card = event.target.closest?.('.canvas-topic-card');
      if (!card || card.contains(event.relatedTarget)) return;
      this.setHoverLayout(this.layoutForCard(card));
    });
    this.cards.addEventListener('mouseout', (event) => {
      const card = event.target.closest?.('.canvas-topic-card');
      if (!card || card.contains(event.relatedTarget)) return;
      this.setHoverLayout(null);
    });
  }

  closeContextMenu() {
    this.contextMenu?.remove();
    this.contextMenu = null;
  }

  /** @param {Element} anchor @param {object} layout @param {HTMLElement} card */
  openContextMenu(anchor, layout, card) {
    this.closeContextMenu();
    const menu = document.createElement('div');
    menu.className = 'canvas-topic-menu';
    menu.setAttribute('role', 'menu');
    const summaryButton = document.createElement('button');
    summaryButton.type = 'button';
    summaryButton.textContent = this.summaries.has(this.summaryKey(layout))
      ? 'Show summary'
      : 'Summary';
    summaryButton.addEventListener('click', () => {
      this.closeContextMenu();
      this.requestSummary(layout, card);
    });
    menu.appendChild(summaryButton);
    document.body.appendChild(menu);
    const rect = anchor.getBoundingClientRect();
    menu.style.left = `${Math.min(rect.left, window.innerWidth - menu.offsetWidth - 8)}px`;
    menu.style.top = `${Math.min(rect.bottom + 4, window.innerHeight - menu.offsetHeight - 8)}px`;
    this.contextMenu = menu;
    summaryButton.focus();
  }

  /** @param {object} layout @returns {string} */
  summaryKey(layout) {
    return `${layout.node.path}\u0000${layout.postId}\u0000${layout.run.join(',')}`;
  }

  /**
   * Sentence text comes from the rendered spans rather than the JSON payload,
   * which no longer ships it. `run` is already ascending, so this keeps
   * document order.
   *
   * @param {object} layout
   * @returns {string[]}
   */
  summarySentences(layout) {
    return layout.run
      .map((number) => this.getSentenceElement(layout.postId, number)?.textContent.trim() || '')
      .filter(Boolean);
  }

  /** @param {object} layout @param {HTMLElement} card */
  async requestSummary(layout, card) {
    const key = this.summaryKey(layout);
    const cached = this.summaries.get(key);
    if (cached) {
      this.showSummary(layout.node.path, cached);
      return;
    }
    if (this.summaryLoadingKeys.has(key)) return;
    this.summaryLoadingKeys.add(key);
    this.refreshCardState(card, layout);
    try {
      const response = await fetch('/openai/summary', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: layout.node.path, sentences: this.summarySentences(layout) }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.data)
        throw new Error(payload.error || 'Unable to generate summary.');
      const summary = String(payload.data).trim();
      this.summaries.set(key, summary);
      this.showSummary(layout.node.path, summary);
    } catch (error) {
      this.showSummary(
        layout.node.path,
        error instanceof Error ? error.message : 'Unable to generate summary.',
        true
      );
    } finally {
      this.summaryLoadingKeys.delete(key);
      if (this.layoutForCard(card) === layout) this.refreshCardState(card, layout);
    }
  }

  createSummaryDialog() {
    const dialog = document.createElement('dialog');
    dialog.className = 'canvas-summary-dialog';
    dialog.innerHTML = `<button type="button" class="canvas-summary-dialog__close" aria-label="Close">×</button><p class="canvas-summary-dialog__kicker">Summary</p><h2></h2><div class="canvas-summary-dialog__text"></div>`;
    dialog
      .querySelector('.canvas-summary-dialog__close')
      ?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });
    document.body.appendChild(dialog);
    this.summaryDialog = dialog;
  }

  /** @param {string} topic @param {string} text @param {boolean} [isError] */
  showSummary(topic, text, isError = false) {
    if (!this.summaryDialog) return;
    const title = this.summaryDialog.querySelector('h2');
    const body = this.summaryDialog.querySelector('.canvas-summary-dialog__text');
    if (title) title.textContent = topic;
    if (body) {
      body.textContent = text;
      body.classList.toggle('is-error', isError);
    }
    this.summaryDialog.showModal();
  }
}

export { FeedCanvas };
