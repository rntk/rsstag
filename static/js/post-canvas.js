import {
  buildNavigationList,
  buildSummaryRequest,
  buildTopicCards,
  findNavigationTarget,
  formatSentenceRange,
  getCardTitleFit,
  getMaxTopicLevel,
  getRailWidth,
  getZoomCardWidth,
  getZoomSummaryWidth,
  getZoomTitleFontSize,
  layoutCards,
  topicAccentColor,
  topicHighlightColor,
  unionRects,
} from './libs/post-canvas.js';
import { createViewport } from './libs/post-canvas-viewport.js';
import { createSummaryStore } from './libs/post-canvas-summaries.js';
import { initTopicGrouping } from './libs/post-canvas-grouping.js';

const TOP_MARGIN = 40;
const SIDE_MARGIN = 20;
const FOCUS_SCALE = 1;
const ZOOM_STEP = 1.2;
const ARROW_PAN_STEP = 80;
const PREVIEW_CHARS = 280;
const FIT_ITERATIONS = 6;

/** @param {string} tag @param {string} [className] @param {string} [text] @returns {HTMLElement} */
function element(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

/** @param {string} label @param {string} action @param {string} [className] @returns {HTMLButtonElement} */
function button(label, action, className = 'post-canvas__text-btn') {
  const node = /** @type {HTMLButtonElement} */ (element('button', className, label));
  node.type = 'button';
  node.dataset.cardAction = action;
  return node;
}

/** @returns {Object<string, HTMLElement>} */
function collectDom() {
  const byId = (id) => document.getElementById(`post-canvas-${id}`);
  return {
    area: byId('area'),
    viewport: byId('viewport'),
    stage: byId('stage'),
    column: byId('column'),
    articles: byId('articles'),
    summaries: byId('summaries'),
    railBody: byId('rail-body'),
    currentSummary: byId('current-summary'),
    levels: byId('levels'),
    zoom: byId('zoom'),
    status: byId('status'),
    controls: document.querySelector('.post-canvas__controls'),
  };
}

/** @param {HTMLElement} articles @returns {Map<number, HTMLElement[]>} */
function indexSentenceSpans(articles) {
  const spans = new Map();
  for (const span of articles.querySelectorAll('[data-sentence]')) {
    const number = Number(span.dataset.sentence);
    if (!spans.has(number)) spans.set(number, []);
    spans.get(number).push(span);
  }
  return spans;
}

/** @param {object} data @param {Object<string, HTMLElement>} dom @returns {object} */
function createContext(data, dom) {
  const maxLevel = getMaxTopicLevel(data.groups);
  return {
    data,
    dom,
    sentencesByNumber: new Map((data.sentences || []).map((s) => [s.number, s])),
    spans: indexSentenceSpans(dom.articles),
    maxLevel,
    level: maxLevel,
    summaryMode: false,
    showRail: true,
    cards: [],
    cardsByKey: new Map(),
    navList: [],
    layoutByKey: new Map(),
    railNodes: new Map(),
    summaryNodes: new Map(),
    selectedKey: null,
    hoveredKey: null,
    highlighted: { selected: [], hovered: [] },
    returnView: null,
    layoutFrame: 0,
    viewport: null,
    store: null,
    observer: null,
  };
}

// ── Cards & rail ───────────────────────────────────────────────────────────

/** @param {object} ctx @param {number} level */
function setLevel(ctx, level) {
  ctx.level = level;
  ctx.cards = buildTopicCards(ctx.data, level);
  ctx.cardsByKey = new Map(ctx.cards.map((card) => [card.key, card]));
  ctx.navList = buildNavigationList(ctx.cards);
  ctx.selectedKey = null;
  ctx.hoveredKey = null;
  renderRail(ctx);
  if (ctx.summaryMode) renderSummaryView(ctx);
  renderLevels(ctx);
  applyZoomVars(ctx);
  layout(ctx);
  refreshActive(ctx);
}

/** @param {object} ctx */
function renderRail(ctx) {
  ctx.railNodes = new Map(ctx.cards.map((card) => [card.key, createRailCard(ctx, card)]));
  ctx.dom.railBody.replaceChildren(...ctx.railNodes.values());
  if (!ctx.cards.length) {
    ctx.dom.railBody.append(element('p', 'post-canvas__rail-empty', 'No topics at this level.'));
  }
}

/** @param {object} ctx @param {object} card @returns {HTMLElement} */
function createRailCard(ctx, card) {
  const node = element('div', `post-canvas__card post-canvas__card--level-${card.depth}`);
  node.dataset.cardKey = card.key;
  node.style.setProperty('--card-level', String(card.depth));
  node.style.setProperty('--topic-accent-color', topicAccentColor(card.path, card.depth));
  const main = button('', 'select', 'post-canvas__card-main');
  main.setAttribute('aria-pressed', 'false');
  main.title = `${card.path}: ${formatSentenceRange(card, ctx.sentencesByNumber)}`;
  const content = element('span', 'post-canvas__card-content');
  content.append(
    element('span', 'post-canvas__card-name', card.name),
    element('span', 'post-canvas__card-meta', `${card.sentences.length} sent.`)
  );
  main.append(content);
  node.append(main);
  bindCardEvents(ctx, node, card);
  return node;
}

/** @param {object} ctx @param {HTMLElement} node @param {object} card */
function bindCardEvents(ctx, node, card) {
  node.addEventListener('mouseenter', () => setHovered(ctx, card.key));
  node.addEventListener('mouseleave', () => setHovered(ctx, null));
  node.addEventListener('click', (event) => {
    if (event.target.closest('a')) return;
    const action = event.target.closest('[data-card-action]')?.dataset.cardAction;
    if (action === 'source') showSource(ctx, card);
    else if (action === 'summarize') ctx.store.request(card);
    else toggleCard(ctx, card);
  });
}

/** @param {object} ctx */
function renderLevels(ctx) {
  const buttons = [];
  for (let level = 0; level <= ctx.maxLevel; level += 1) {
    const node = button(`L${level + 1}`, '', 'post-canvas__btn');
    node.dataset.level = String(level);
    node.title = `Show topics down to level ${level + 1}`;
    node.setAttribute('aria-pressed', String(level === ctx.level));
    node.classList.toggle('is-active', level === ctx.level);
    buttons.push(node);
  }
  ctx.dom.levels.replaceChildren(...buttons);
  ctx.dom.levels.hidden = ctx.maxLevel === 0;
}

// ── Measurement & layout ───────────────────────────────────────────────────

/** @param {object} ctx */
function scheduleLayout(ctx) {
  if (ctx.layoutFrame) return;
  ctx.layoutFrame = window.requestAnimationFrame(() => {
    ctx.layoutFrame = 0;
    layout(ctx);
  });
}

/** @param {object} ctx */
function layout(ctx) {
  const measure = ctx.summaryMode ? createSummaryMeasure(ctx) : createSentenceMeasure(ctx);
  const placed = layoutCards(ctx.cards, measure);
  ctx.layoutByKey = new Map(placed.map((card) => [card.key, card]));
  placed.forEach((card, index) => positionRailCard(ctx.railNodes.get(card.key), card, index));
  const bottom = placed.reduce((max, card) => Math.max(max, card.top + card.height), 0);
  ctx.dom.railBody.style.height = `${bottom + 20}px`;
  renderCurrentSummary(ctx);
}

/** @param {HTMLElement} node @param {object} card @param {number} index */
function positionRailCard(node, card, index) {
  if (!node) return;
  const fit = getCardTitleFit(card.height);
  node.style.setProperty('--topic-card-top', `${card.top}px`);
  node.style.setProperty('--topic-card-height', `${card.height}px`);
  node.style.setProperty('--card-title-max-size', `${fit.maxFontSize}px`);
  node.style.setProperty('--card-title-lines', String(fit.lines));
  node.classList.toggle('is-compact', fit.lines === 1);
  node.style.setProperty('--card-z', String(10 + index));
}

/**
 * Converts client rects to unscaled px relative to the rail. The scale is read
 * from the rendered column, so it stays right while a jump is still animating.
 */
function createMeasureFrame(ctx) {
  const { column, railBody } = ctx.dom;
  const columnWidth = column.getBoundingClientRect().width;
  const scale =
    column.offsetWidth > 0 && columnWidth > 0
      ? columnWidth / column.offsetWidth
      : ctx.viewport.getScale();
  const originTop = railBody.getBoundingClientRect().top;
  return (rect) => ({
    top: (rect.top - originTop) / scale,
    bottom: (rect.bottom - originTop) / scale,
  });
}

/** Rects of a card's sentences, relative to the rail, in unscaled px. */
function createSentenceMeasure(ctx) {
  const toLocal = createMeasureFrame(ctx);
  const cache = new Map();
  const measureSentence = (number) => {
    if (!cache.has(number)) cache.set(number, measureSpans(toLocal, ctx.spans.get(number)));
    return cache.get(number);
  };
  return (card) => unionRects(card.sentences.map(measureSentence));
}

/** Word spans flow in reading order: the first and last bound the sentence. */
function measureSpans(toLocal, spans) {
  if (!spans?.length) return null;
  return unionRects([
    toLocal(spans[0].getBoundingClientRect()),
    toLocal(spans.at(-1).getBoundingClientRect()),
  ]);
}

/** In summary mode, rail cards span the summary cards inside their range. */
function createSummaryMeasure(ctx) {
  const toLocal = createMeasureFrame(ctx);
  const rects = new Map();
  for (const [key, node] of ctx.summaryNodes) {
    rects.set(key, toLocal(node.getBoundingClientRect()));
  }
  return (card) =>
    unionRects(
      ctx.navList
        .filter(
          (nav) => nav.postId === card.postId && nav.start >= card.start && nav.start <= card.end
        )
        .map((nav) => rects.get(nav.key))
    );
}

/** @param {object} ctx @param {number} [scale] */
function applyZoomVars(ctx, scale = ctx.viewport.getScale()) {
  const cardWidth = getZoomCardWidth(scale);
  const { stage } = ctx.dom;
  stage.style.setProperty('--card-w', `${cardWidth}px`);
  stage.style.setProperty('--rail-w', `${getRailWidth(ctx.level + 1, cardWidth)}px`);
  stage.style.setProperty('--summary-w', `${getZoomSummaryWidth(scale)}px`);
  stage.style.setProperty('--card-title-size', `${getZoomTitleFontSize(scale)}px`);
  stage.classList.toggle('is-zoomed-out', scale < 1);
  ctx.dom.zoom.textContent = `${Math.round(scale * 100)}%`;
}

// ── Selection, hover & highlights ──────────────────────────────────────────

/** @param {object} ctx @param {?string} key */
function setHovered(ctx, key) {
  if (ctx.hoveredKey === key) return;
  ctx.hoveredKey = key;
  refreshActive(ctx);
}

/** @param {object} ctx @param {object} card */
function toggleCard(ctx, card) {
  if (ctx.selectedKey === card.key) {
    clearSelection(ctx);
    return;
  }
  selectCard(ctx, card);
  zoomToCard(ctx, card);
}

/** Select a card and fetch its summary for the floating card. */
function selectCard(ctx, card) {
  ctx.selectedKey = card.key;
  ctx.store.request(card);
  refreshActive(ctx);
}

/** @param {object} ctx */
function clearSelection(ctx) {
  ctx.selectedKey = null;
  ctx.hoveredKey = null;
  refreshActive(ctx);
}

/** @param {object} ctx @returns {?object} */
function getActiveCard(ctx) {
  return ctx.cardsByKey.get(ctx.hoveredKey) || ctx.cardsByKey.get(ctx.selectedKey) || null;
}

/** @param {object} ctx */
function refreshActive(ctx) {
  for (const nodes of [ctx.railNodes, ctx.summaryNodes]) {
    for (const [key, node] of nodes) {
      node.classList.toggle('is-active', key === ctx.hoveredKey);
      node.classList.toggle('is-selected', key === ctx.selectedKey);
      node
        .querySelector('.post-canvas__card-main')
        ?.setAttribute('aria-pressed', String(key === ctx.selectedKey));
    }
  }
  highlightSentences(ctx, 'selected', ctx.cardsByKey.get(ctx.selectedKey));
  highlightSentences(ctx, 'hovered', ctx.cardsByKey.get(ctx.hoveredKey));
  renderCurrentSummary(ctx);
}

/** @param {object} ctx @param {'selected'|'hovered'} kind @param {?object} card */
function highlightSentences(ctx, kind, card) {
  const className = `is-${kind}`;
  ctx.highlighted[kind].forEach((span) => span.classList.remove(className));
  ctx.highlighted[kind] = card ? card.sentences.flatMap((n) => ctx.spans.get(n) || []) : [];
  ctx.highlighted[kind].forEach((span) => span.classList.add(className));
  if (card) {
    ctx.dom.stage.style.setProperty(
      `--highlight-${kind}`,
      topicHighlightColor(card.path, card.depth)
    );
  }
}

// ── Floating current-topic summary ─────────────────────────────────────────

/** @param {object} ctx */
function renderCurrentSummary(ctx) {
  const aside = ctx.dom.currentSummary;
  const card = getActiveCard(ctx);
  const position = card && ctx.layoutByKey.get(card.key);
  if (!position || ctx.summaryMode || !ctx.showRail) {
    aside.hidden = true;
    return;
  }
  aside.hidden = false;
  aside.style.setProperty('--current-summary-top', `${position.top}px`);
  aside.replaceChildren(buildSummaryCard(ctx, card, 'post-canvas__summary-card is-floating'));
  aside.style.setProperty('--current-summary-height', `${aside.offsetHeight}px`);
}

/** @param {object} ctx @param {object} card @param {string} className @returns {HTMLElement} */
function buildSummaryCard(ctx, card, className) {
  const node = element('article', className);
  node.style.setProperty('--topic-accent-color', topicAccentColor(card.path, card.depth));
  const header = element('header', 'post-canvas__summary-header');
  header.append(
    element('span', 'post-canvas__summary-kicker', 'Summary'),
    element('span', 'post-canvas__summary-path', card.path),
    element('span', 'post-canvas__summary-meta', formatSentenceRange(card, ctx.sentencesByNumber))
  );
  node.append(header, buildSummaryBody(ctx, card));
  return node;
}

/** @param {object} ctx @param {object} card @returns {HTMLElement} */
function buildSummaryBody(ctx, card) {
  const entry = ctx.store.get(card.key);
  const body = element('div', 'post-canvas__summary-body');
  if (entry.status === 'done') {
    body.append(element('p', 'post-canvas__summary-text', entry.text));
  } else if (entry.status === 'queued' || entry.status === 'loading') {
    body.append(element('p', 'post-canvas__summary-pending', 'Summarizing…'));
  } else {
    const message = entry.status === 'error' ? entry.error : previewText(ctx, card);
    const kind = entry.status === 'error' ? 'error' : 'preview';
    body.append(element('p', `post-canvas__summary-${kind}`, message));
    body.append(button(entry.status === 'error' ? 'Retry' : 'Summarize', 'summarize'));
  }
  return body;
}

/** @param {object} ctx @param {object} card @returns {string} */
function previewText(ctx, card) {
  const text = card.sentences
    .map((number) => ctx.sentencesByNumber.get(number)?.text || '')
    .join(' ')
    .trim();
  return text.length > PREVIEW_CHARS ? `${text.slice(0, PREVIEW_CHARS).trimEnd()}…` : text;
}

/** @param {object} ctx @param {string} key */
function handleSummaryUpdate(ctx, key) {
  const card = ctx.cardsByKey.get(key);
  const node = ctx.summaryNodes.get(key);
  if (card && node)
    node.querySelector('.post-canvas__summary-body').replaceWith(buildSummaryBody(ctx, card));
  if (getActiveCard(ctx)?.key === key) renderCurrentSummary(ctx);
}

// ── Summary mode ───────────────────────────────────────────────────────────

/** @param {object} ctx */
function renderSummaryView(ctx) {
  ctx.observer?.disconnect();
  ctx.observer = createLazySummaryObserver(ctx);
  ctx.summaryNodes = new Map();
  const sections = ctx.data.posts.map((post) => renderPostSummaries(ctx, post)).filter(Boolean);
  ctx.dom.summaries.replaceChildren(...sections);
}

/** @param {object} ctx @param {object} post @returns {?HTMLElement} */
function renderPostSummaries(ctx, post) {
  const cards = ctx.navList.filter((card) => card.postId === post.post_id);
  if (!cards.length) return null;
  const section = element('section', 'post-canvas__summary-section');
  section.append(element('h2', 'post-canvas__summary-post', post.feed_title || post.post_id));
  for (const card of cards) {
    const node = buildSummaryCard(ctx, card, 'post-canvas__summary-card');
    node.dataset.cardKey = card.key;
    node.tabIndex = 0;
    node.querySelector('.post-canvas__summary-header').append(button('Source', 'source'));
    bindCardEvents(ctx, node, card);
    ctx.observer?.observe(node);
    ctx.summaryNodes.set(card.key, node);
    section.append(node);
  }
  return section;
}

/** Request summaries as their cards scroll into view. */
function createLazySummaryObserver(ctx) {
  if (typeof window.IntersectionObserver === 'undefined') return null;
  const observer = new window.IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        observer.unobserve(entry.target);
        const card = ctx.cardsByKey.get(entry.target.dataset.cardKey);
        if (card) ctx.store.request(card);
      }
    },
    { root: ctx.dom.area, rootMargin: '200px' }
  );
  return observer;
}

/** @param {object} ctx @param {boolean} enabled */
function setSummaryMode(ctx, enabled) {
  if (!ctx.cards.length) return;
  ctx.summaryMode = enabled;
  ctx.dom.articles.hidden = enabled;
  ctx.dom.summaries.hidden = !enabled;
  ctx.dom.stage.classList.toggle('is-summary-mode', enabled);
  if (enabled) renderSummaryView(ctx);
  else {
    ctx.observer?.disconnect();
    ctx.summaryNodes = new Map();
    ctx.dom.summaries.replaceChildren();
  }
  syncToggle(ctx, 'summary-mode', enabled, enabled ? 'Show article text' : 'Show summary view');
  layout(ctx);
  refreshActive(ctx);
  // Content swaps wholesale, so restart at the top like the extension does.
  ctx.viewport.setTransform(ctx.viewport.getScale(), {
    x: ctx.viewport.getTranslate().x,
    y: TOP_MARGIN,
  });
}

/** Leave summary mode and jump to a card's source sentences. */
function showSource(ctx, card) {
  captureReturnView(ctx);
  setSummaryMode(ctx, false);
  selectCard(ctx, card);
  zoomToCard(ctx, card, { capture: false });
}

/** @param {object} ctx @param {boolean} visible */
function setRailVisible(ctx, visible) {
  ctx.showRail = visible;
  ctx.dom.stage.classList.toggle('has-rail', visible);
  syncToggle(ctx, 'rail', visible, visible ? 'Hide topic rail' : 'Show topic rail');
  layout(ctx);
}

/** @param {object} ctx @param {string} action @param {boolean} active @param {string} title */
function syncToggle(ctx, action, active, title) {
  const node = ctx.dom.controls.querySelector(`[data-action="${action}"]`);
  node.classList.toggle('is-active', active);
  node.setAttribute('aria-pressed', String(active));
  node.title = title;
}

// ── Viewport movement ──────────────────────────────────────────────────────

/** @param {object} ctx */
function captureReturnView(ctx) {
  ctx.returnView = {
    scale: ctx.viewport.getScale(),
    translate: ctx.viewport.getTranslate(),
    summaryMode: ctx.summaryMode,
  };
  ctx.dom.controls.querySelector('[data-action="return"]').hidden = false;
}

/** Swap with the remembered view so one more press jumps back again. */
function returnToView(ctx) {
  const target = ctx.returnView;
  if (!target) return;
  const current = {
    scale: ctx.viewport.getScale(),
    translate: ctx.viewport.getTranslate(),
    summaryMode: ctx.summaryMode,
  };
  if (target.summaryMode !== ctx.summaryMode) setSummaryMode(ctx, target.summaryMode);
  ctx.viewport.setTransform(target.scale, target.translate, { animate: true });
  ctx.returnView = current;
}

/** Client rect of what a card covers in the current mode. */
function getCardTargetRect(ctx, card) {
  if (ctx.summaryMode) {
    const node = ctx.summaryNodes.get(card.key);
    return node ? node.getBoundingClientRect() : null;
  }
  const rects = card.sentences
    .flatMap((n) => ctx.spans.get(n) || [])
    .map((s) => s.getBoundingClientRect());
  return rects.length ? { top: Math.min(...rects.map((r) => r.top)) } : null;
}

/**
 * Bring a card's text near the top of the view while keeping the reading
 * column and rail visible.
 */
function zoomToCard(ctx, card, { capture = true } = {}) {
  const rect = getCardTargetRect(ctx, card) || ctx.railNodes.get(card.key)?.getBoundingClientRect();
  if (!rect) return;
  if (capture) captureReturnView(ctx);
  const nextScale = Math.max(ctx.viewport.getScale(), FOCUS_SCALE);
  const toLocal = createMeasureFrame(ctx);
  const localTop = toLocal(rect).top + ctx.dom.railBody.offsetTop + ctx.dom.stage.offsetTop;
  const y = ctx.dom.area.clientHeight * 0.2 - localTop * nextScale;
  // Gutters widen with zoom-out; size them for the target scale before reading.
  applyZoomVars(ctx, nextScale);
  ctx.viewport.setTransform(nextScale, { x: getFocusX(ctx, nextScale), y }, { animate: true });
}

/** @param {object} ctx @param {number} scale @returns {number} */
function getFocusX(ctx, scale) {
  const { area, stage, column } = ctx.dom;
  const width = area.clientWidth;
  const stageWidth = stage.offsetWidth;
  if (stageWidth * scale <= width) return (width - stageWidth * scale) / 2;
  const readingWidth = stageWidth - column.offsetLeft;
  if (readingWidth * scale <= width - SIDE_MARGIN * 2) {
    return width - SIDE_MARGIN - stageWidth * scale;
  }
  return width / 2 - (column.offsetLeft + column.offsetWidth / 2) * scale;
}

/**
 * Fit the stage width at the top. Gutters widen as the canvas zooms out, so
 * iterate the fit toward its fixed point instead of solving it once.
 */
function fitWidth(ctx) {
  const { area, stage } = ctx.dom;
  const available = Math.max(1, area.clientWidth - SIDE_MARGIN * 2);
  let scale = ctx.viewport.getScale();
  for (let step = 0; step < FIT_ITERATIONS; step += 1) {
    applyZoomVars(ctx, scale);
    scale = Math.min(1, available / Math.max(1, stage.offsetWidth));
  }
  applyZoomVars(ctx, scale);
  const x = Math.max(SIDE_MARGIN, (area.clientWidth - stage.offsetWidth * scale) / 2);
  ctx.viewport.setTransform(scale, { x, y: TOP_MARGIN });
}

/** @param {object} ctx @param {'top'|'bottom'|'prev-page'|'next-page'} pos */
function scrollCanvas(ctx, pos) {
  const scale = ctx.viewport.getScale();
  const { x, y } = ctx.viewport.getTranslate();
  const height = ctx.dom.area.clientHeight;
  const step = Math.max(120, height * 0.8);
  const bottom = Math.min(TOP_MARGIN, height - ctx.dom.stage.offsetHeight * scale - TOP_MARGIN);
  const nextY = { top: TOP_MARGIN, bottom, 'prev-page': y + step, 'next-page': y - step }[pos];
  ctx.viewport.setTransform(scale, { x, y: nextY }, { animate: true });
}

/** @param {object} ctx @param {'first'|'prev'|'next'|'last'} direction */
function navigateTopic(ctx, direction) {
  const current = ctx.cardsByKey.get(ctx.selectedKey) || null;
  const target = findNavigationTarget(ctx.navList, current, direction);
  if (!target) return;
  selectCard(ctx, target);
  zoomToCard(ctx, target);
}

// ── Controls & keyboard ────────────────────────────────────────────────────

const TOPIC_ACTIONS = {
  'first-topic': 'first',
  'prev-topic': 'prev',
  'next-topic': 'next',
  'last-topic': 'last',
};

/** @param {object} ctx @param {string} action */
function runAction(ctx, action) {
  if (TOPIC_ACTIONS[action]) return navigateTopic(ctx, TOPIC_ACTIONS[action]);
  if (['top', 'bottom', 'prev-page', 'next-page'].includes(action))
    return scrollCanvas(ctx, action);
  const actions = {
    'zoom-in': () => ctx.viewport.zoomFromCenter(ZOOM_STEP),
    'zoom-out': () => ctx.viewport.zoomFromCenter(1 / ZOOM_STEP),
    fit: () => fitWidth(ctx),
    reset: () => ctx.viewport.setTransform(1, { x: TOP_MARGIN, y: TOP_MARGIN }),
    'summary-mode': () => setSummaryMode(ctx, !ctx.summaryMode),
    rail: () => setRailVisible(ctx, !ctx.showRail),
    return: () => returnToView(ctx),
  };
  return actions[action]?.();
}

/** @param {object} ctx */
function bindControls(ctx) {
  ctx.dom.controls.addEventListener('click', (event) => {
    const levelButton = event.target.closest('[data-level]');
    if (levelButton) {
      const level = Number(levelButton.dataset.level);
      if (level !== ctx.level) setLevel(ctx, level);
      return;
    }
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action) runAction(ctx, action);
  });
  ctx.dom.currentSummary.addEventListener('click', (event) => {
    if (event.target.closest('[data-card-action="summarize"]')) {
      const card = getActiveCard(ctx);
      if (card) ctx.store.request(card);
    }
  });
}

const KEY_ACTIONS = {
  ArrowDown: 'next-topic',
  ArrowUp: 'prev-topic',
  PageDown: 'next-page',
  PageUp: 'prev-page',
  Home: 'top',
  End: 'bottom',
  '+': 'zoom-in',
  '=': 'zoom-in',
  '-': 'zoom-out',
  Backspace: 'return',
};

/** @param {EventTarget} target @returns {boolean} */
function isTypingTarget(target) {
  return Boolean(target?.closest?.('input, textarea, select, [contenteditable="true"]'));
}

/** @param {object} ctx */
function bindKeyboard(ctx) {
  window.addEventListener('keydown', (event) => {
    if (isTypingTarget(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === 'Escape') {
      clearSelection(ctx);
      return;
    }
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      ctx.viewport.panBy(event.key === 'ArrowLeft' ? ARROW_PAN_STEP : -ARROW_PAN_STEP, 0);
      return;
    }
    const action = KEY_ACTIONS[event.key];
    if (!action) return;
    event.preventDefault();
    runAction(ctx, action);
  });
}

/** Re-align the rail when images, fonts or summaries change the layout. */
function bindRemeasure(ctx) {
  if (typeof window.ResizeObserver !== 'undefined') {
    new window.ResizeObserver(() => scheduleLayout(ctx)).observe(ctx.dom.column);
  }
  for (const image of ctx.dom.articles.querySelectorAll('img')) {
    image.addEventListener('load', () => scheduleLayout(ctx), { once: true });
  }
  document.fonts?.ready?.then(() => scheduleLayout(ctx));
}

/** @param {object} ctx */
function showEmptyState(ctx) {
  if (ctx.cards.length) return;
  setRailVisible(ctx, false);
  ctx.dom.controls
    .querySelectorAll('[data-action$="-topic"], [data-action="summary-mode"], [data-action="rail"]')
    .forEach((node) => {
      node.disabled = true;
    });
  ctx.dom.status.textContent =
    'No saved topics match this view yet. The posts are shown without the topic rail.';
}

/** @param {object} data @returns {object} */
export function initPostCanvas(data) {
  const dom = collectDom();
  const ctx = createContext(data, dom);
  ctx.viewport = createViewport({
    area: dom.area,
    viewport: dom.viewport,
    onChange: (scale) => applyZoomVars(ctx, scale),
  });
  ctx.store = createSummaryStore({
    buildRequest: (card) => buildSummaryRequest(card, ctx.sentencesByNumber),
    onUpdate: (key) => handleSummaryUpdate(ctx, key),
  });
  setLevel(ctx, ctx.maxLevel);
  bindControls(ctx);
  bindKeyboard(ctx);
  bindRemeasure(ctx);
  showEmptyState(ctx);
  initTopicGrouping(document);
  fitWidth(ctx);
  layout(ctx);
  dom.area.focus({ preventScroll: true });
  return ctx;
}

try {
  initPostCanvas(JSON.parse(document.getElementById('post-canvas-data').textContent));
} catch (error) {
  console.error('Unable to display the post canvas', error);
  const status = document.getElementById('post-canvas-status');
  if (status) status.textContent = 'The canvas could not be displayed. Please reload the page.';
}
