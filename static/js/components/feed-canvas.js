/* global CSS, Element, console, document, fetch, window */

const CARD_WIDTH = 220;
const CARD_GAP = 14;
const RAIL_PADDING = 20;
const MIN_TOPIC_FONT_SIZE = 8;
const MIN_SCALE = 0.45;
const MAX_SCALE = 1.8;
const ZOOM_FACTOR = 1.1;
const TOPIC_ZOOM_SCALE = 1.6;
const ARROW_PAN_STEP = 80;
const PAGE_STEP_RATIO = 0.8;
const BASE_TOPIC_FONT_SIZE = 13;
const TOPIC_CARD_CHROME_HEIGHT = 30;
const COMPACT_TOPIC_CARD_HEIGHT = 70;

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
    this.contextMenu = null;
    this.summaryDialog = null;
    this.statusTimer = 0;
    /** @type {Map<string, {top: number, bottom: number, left: number, right: number}>} */
    this.sentenceMetrics = new Map();
    /** @type {Array<{layout: {node: ReturnType<typeof buildTopicNodes>[number], postId: string, run: number[], top: number, height: number, left: number, width: number}, card: HTMLDivElement}>} */
    this.topicCards = [];
    this.topicCardUpdateFrame = 0;
    /** @type {{scale: number, x: number, y: number}|null} */
    this.savedView = null;
  }

  init() {
    if (!this.root || !this.viewport || !this.document || !this.rail || !this.cards) return;
    this.renderLevelButtons();
    this.bindEvents();
    this.applyTransform();
    this.layoutTopics();
    this.createSummaryDialog();
    document.fonts?.ready.then(() => {
      this.sentenceMetrics.clear();
      this.layoutTopics();
    });
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
        this.zoomByFactor(factor, event.clientX, event.clientY);
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
    window.addEventListener('resize', () => {
      window.clearTimeout(this.resizeTimer);
      this.resizeTimer = window.setTimeout(() => {
        this.sentenceMetrics.clear();
        this.layoutTopics();
      }, 100);
    });
  }

  /** @param {string} postId @returns {Record<string, unknown>|undefined} */
  findPost(postId) {
    return this.posts.find((post) => String(post.post_id || '') === postId);
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
    if (!this.root) return;
    const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, this.scale * factor));
    if (nextScale === this.scale) return;
    const rect = this.root.getBoundingClientRect();
    const focusX = clientX ?? rect.left + rect.width / 2;
    const focusY = clientY ?? rect.top + rect.height / 2;
    const contentX = (focusX - rect.left - this.x) / this.scale;
    const contentY = (focusY - rect.top - this.y) / this.scale;
    this.x = focusX - rect.left - contentX * nextScale;
    this.y = focusY - rect.top - contentY * nextScale;
    this.scale = nextScale;
    this.applyTransform();
    this.scheduleTopicCardUpdate();
  }

  reset() {
    this.scale = 1;
    this.x = 40;
    this.y = 30;
    this.applyTransform();
    this.scheduleTopicCardUpdate();
  }

  /** @param {{top: number, height: number, left: number, width: number}} layout */
  zoomToLayout(layout) {
    if (!this.root || !this.document) return;
    if (!this.savedView) this.savedView = { scale: this.scale, x: this.x, y: this.y };
    const targetScale = Math.min(MAX_SCALE, Math.max(this.savedView.scale, TOPIC_ZOOM_SCALE));
    const rect = this.root.getBoundingClientRect();
    const centerX = layout.left + layout.width / 2;
    const centerY = layout.top + layout.height / 2;
    this.scale = targetScale;
    this.x = rect.width / 2 - centerX * targetScale;
    this.y = rect.height / 2 - centerY * targetScale;
    this.applyTransform();
    this.scheduleTopicCardUpdate();
  }

  restoreView() {
    if (!this.savedView) return;
    this.scale = this.savedView.scale;
    this.x = this.savedView.x;
    this.y = this.savedView.y;
    this.savedView = null;
    this.applyTransform();
    this.scheduleTopicCardUpdate();
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

  applyTransform() {
    this.viewport?.style.setProperty('--canvas-x', `${this.x}px`);
    this.viewport?.style.setProperty('--canvas-y', `${this.y}px`);
    this.viewport?.style.setProperty('--canvas-zoom', String(this.scale));
  }

  /** @returns {number} */
  getTopicCardWidth() {
    return CARD_WIDTH * Math.max(1, 1 / this.scale);
  }

  /** @param {number} cardHeight @returns {number} */
  getTopicFontSize(cardHeight) {
    const zoomAdjusted = BASE_TOPIC_FONT_SIZE * Math.max(1, 1.25 / this.scale - 0.25);
    const titleLines = cardHeight < COMPACT_TOPIC_CARD_HEIGHT ? 1 : 2;
    const availableHeight = Math.max(1, cardHeight - TOPIC_CARD_CHROME_HEIGHT);
    return Math.max(
      MIN_TOPIC_FONT_SIZE,
      Math.min(zoomAdjusted, availableHeight / (titleLines * 1.25))
    );
  }

  scheduleTopicCardUpdate() {
    if (this.topicCardUpdateFrame) return;
    this.topicCardUpdateFrame = window.requestAnimationFrame(() => {
      this.topicCardUpdateFrame = 0;
      this.updateTopicCards();
    });
  }

  updateTopicCards() {
    const cardWidth = this.getTopicCardWidth();
    if (this.rail) {
      const railWidth =
        (this.selectedLevel + 1) * cardWidth + this.selectedLevel * CARD_GAP + RAIL_PADDING * 2;
      this.rail.style.width = `${railWidth}px`;
    }
    this.topicCards.forEach(({ layout, card }) => {
      this.updateTopicCardMetrics(card, layout, cardWidth);
    });
  }

  /**
   * @param {HTMLDivElement} card
   * @param {{node: ReturnType<typeof buildTopicNodes>[number], height: number}} layout
   * @param {number} cardWidth
   */
  updateTopicCardMetrics(card, layout, cardWidth) {
    card.style.width = `${cardWidth}px`;
    card.style.right = `${RAIL_PADDING + layout.node.depth * (cardWidth + CARD_GAP)}px`;
    card.style.setProperty('--topic-font-size', `${this.getTopicFontSize(layout.height)}px`);
  }

  /** @param {string} postId @param {number} number @param {DOMRect} documentRect */
  getSentenceMetrics(postId, number, documentRect) {
    const key = `${postId}\u0000${number}`;
    const cached = this.sentenceMetrics.get(key);
    if (cached) return cached;
    const selector = `.canvas-post[data-post-id="${CSS.escape(postId)}"] .canvas-sentence[data-sentence-number="${number}"]`;
    const rect = this.document?.querySelector(selector)?.getBoundingClientRect();
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
    if (this.topicCardUpdateFrame) {
      window.cancelAnimationFrame(this.topicCardUpdateFrame);
      this.topicCardUpdateFrame = 0;
    }
    this.cards.replaceChildren();
    this.topicCards = [];
    const visibleNodes = this.nodes.filter((node) => node.depth <= this.selectedLevel);
    const cardWidth = this.getTopicCardWidth();
    const railWidth =
      (this.selectedLevel + 1) * cardWidth + this.selectedLevel * CARD_GAP + RAIL_PADDING * 2;
    this.rail.style.width = `${railWidth}px`;
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

    const fragment = document.createDocumentFragment();
    layouts.forEach((layout) => {
      const card = this.createCard(layout, cardWidth);
      this.topicCards.push({ layout, card });
      fragment.appendChild(card);
    });
    this.cards.appendChild(fragment);
    const postsHeight = document.getElementById('canvas_posts')?.offsetHeight || 0;
    const cardsHeight = layouts.reduce(
      (maximum, layout) => Math.max(maximum, layout.top + layout.height),
      0
    );
    this.cards.style.height = `${Math.max(postsHeight, cardsHeight) + 24}px`;
  }

  /**
   * @param {{node: ReturnType<typeof buildTopicNodes>[number], postId: string, run: number[], top: number, height: number}} layout
   * @param {number} cardWidth
   * @returns {HTMLDivElement}
   */
  createCard(layout, cardWidth) {
    const card = document.createElement('div');
    card.className = 'canvas-topic-card';
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.style.top = `${layout.top}px`;
    card.style.height = `${layout.height}px`;
    this.updateTopicCardMetrics(card, layout, cardWidth);
    card.style.setProperty('--topic-color', topicColor(layout.node.path));
    card.style.setProperty(
      '--topic-title-lines',
      layout.height < COMPACT_TOPIC_CARD_HEIGHT ? '1' : '2'
    );
    card.innerHTML = `<button type="button" class="canvas-topic-card__menu" aria-label="Topic actions" title="Topic actions">⋮</button><span class="canvas-topic-card__name"></span><span class="canvas-topic-card__meta">${layout.run.length} sent.</span>`;
    const name = card.querySelector('.canvas-topic-card__name');
    if (name) name.textContent = layout.node.name;
    card.title = layout.node.path;
    const toggleHighlight = (active) => {
      layout.run.forEach((number) => {
        const selector = `.canvas-post[data-post-id="${CSS.escape(layout.postId)}"] .canvas-sentence[data-sentence-number="${number}"]`;
        this.document?.querySelector(selector)?.classList.toggle('is-topic-active', active);
      });
      card.classList.toggle('is-active', active);
    };
    card.addEventListener('mouseenter', () => toggleHighlight(true));
    card.addEventListener('mouseleave', () => {
      if (!card.classList.contains('is-selected')) toggleHighlight(false);
    });
    const selectCard = () => {
      const selected = !card.classList.contains('is-selected');
      this.cards?.querySelectorAll('.is-selected').forEach((item) => {
        item.classList.remove('is-selected', 'is-active');
      });
      this.document
        ?.querySelectorAll('.canvas-sentence.is-topic-active')
        .forEach((item) => item.classList.remove('is-topic-active'));
      card.classList.toggle('is-selected', selected);
      if (selected) {
        toggleHighlight(true);
        this.zoomToLayout(layout);
      } else {
        this.restoreView();
      }
    };
    card.addEventListener('click', (event) => {
      if (!event.target.closest('.canvas-topic-card__menu')) selectCard();
    });
    card.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectCard();
      }
    });
    card.querySelector('.canvas-topic-card__menu')?.addEventListener('click', (event) => {
      event.stopPropagation();
      this.openContextMenu(event.currentTarget, layout, card);
    });
    return card;
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

  /** @param {object} layout @returns {string[]} */
  summarySentences(layout) {
    const post = this.posts.find((item) => String(item.post_id || '') === layout.postId);
    if (!post || !Array.isArray(post.sentences)) return [];
    const numbers = new Set(layout.run);
    return post.sentences
      .filter((sentence) => numbers.has(sentence.number))
      .map((sentence) => String(sentence.text || '').trim())
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
    card.classList.add('is-summary-loading');
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
      card.classList.remove('is-summary-loading');
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

document.addEventListener('DOMContentLoaded', () => new FeedCanvas().init());
