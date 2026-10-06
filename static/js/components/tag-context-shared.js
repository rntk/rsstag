import * as d3 from 'd3';

export const Z_SIGNIFICANT = 1.96;
export const LABEL_CHAR_WIDTH = 7.2;
const LABEL_GAP = 8;

/** Format a lift ratio for axes and details: 0.5×, 1×, 2.4×, 16×. */
export function formatLift(value) {
  if (!Number.isFinite(value)) return '–';
  if (value >= 10) return `${Math.round(value)}×`;
  if (value >= 1) return `${value.toFixed(1).replace(/\.0$/, '')}×`;
  return `${value.toFixed(2).replace(/0$/, '')}×`;
}

export function formatPercent(value) {
  return `${Math.round(value * 100)}%`;
}

export function isSignificant(item) {
  return Math.abs(item.z) >= Z_SIGNIFICANT;
}

/** Base-2 log lift scale over every item's interval, always including 1×. */
export function liftScale(items, range, withInterval = true) {
  const low = d3.min(items, (item) => (withInterval ? item.lift_low : item.lift)) ?? 1;
  const high = d3.max(items, (item) => (withInterval ? item.lift_high : item.lift)) ?? 2;
  const domain = [Math.min(low, 0.5), Math.max(high, 2)];
  return d3.scaleLog().base(2).domain(domain).range(range).clamp(true);
}

/** Powers of two inside the scale domain, thinned to at most `count` ticks. */
export function liftTicks(scale, count = 8) {
  const [low, high] = scale.domain();
  const ticks = [];
  for (let power = Math.ceil(Math.log2(low)); 2 ** power <= high; power += 1)
    ticks.push(2 ** power);
  const step = Math.ceil(ticks.length / count);
  return ticks.filter((tick, index) => tick === 1 || index % step === 0);
}

/** Vertical grid, tick labels and a dashed 1× reference across [top, bottom]. */
export function renderLiftAxis(svg, scale, top, bottom) {
  const axis = svg.append('g').attr('class', 'tag-context__axis');
  liftTicks(scale).forEach((tick) => {
    const x = scale(tick);
    axis
      .append('line')
      .attr('class', tick === 1 ? 'tag-context__reference' : 'tag-context__grid')
      .attr('x1', x)
      .attr('x2', x)
      .attr('y1', top)
      .attr('y2', bottom);
    axis
      .append('text')
      .attr('class', 'tag-context__tick')
      .attr('x', x)
      .attr('y', bottom + 16)
      .text(formatLift(tick));
  });
  return axis;
}

/** Article-count radius scale starting at zero so area stays proportional. */
export function articleRadius(items, maxRadius) {
  const max = d3.max(items, (item) => item.articles) || 1;
  return d3.scaleSqrt().domain([0, max]).range([0, maxRadius]);
}

/**
 * Put each label on the lowest of `levels` rows where it does not overlap an
 * earlier label. Items are visited left to right; unplaceable labels are dropped.
 */
export function assignLabelLevels(items, levels, widthOf) {
  const ends = Array(levels).fill(-Infinity);
  const placed = [];
  [...items]
    .sort((a, b) => a.x - b.x)
    .forEach((item) => {
      const half = widthOf(item) / 2;
      const level = ends.findIndex((end) => end + LABEL_GAP <= item.x - half);
      if (level < 0) return;
      ends[level] = item.x + half;
      placed.push({ ...item, level });
    });
  return placed;
}

/** Make an SVG element act as a button for mouse, Enter and Space. */
export function asButton(selection, onActivate) {
  return selection
    .attr('tabindex', 0)
    .attr('role', 'button')
    .on('click', (event, datum) => onActivate(datum))
    .on('keydown', (event, datum) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      onActivate(datum);
    });
}

function element(tag, text, className) {
  const node = globalThis.document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

export function postsLink(postIds, text) {
  const link = element('a', text);
  link.href = `/posts/${postIds.join('_')}`;
  return link;
}

function statsList(word) {
  const list = element('dl', undefined, 'tag-context__stats');
  const feeds = word.feeds.map((feed) => `${feed.title} (${feed.count})`).join(', ');
  [
    [
      'Lift',
      `${formatLift(word.lift)} (95% ${formatLift(word.lift_low)}–${formatLift(word.lift_high)})`,
    ],
    ['z-score', `${word.z.toFixed(2)}${isSignificant(word) ? '' : ' · not significant'}`],
    ['Tag sentences', `${word.sentences}`],
    ['Other sentences', `${word.reference_sentences}`],
    ['Articles', `${word.articles}`],
    [
      'Feeds',
      `${word.feed_count} · largest ${formatPercent(word.top_feed_share)}${feeds ? ` · ${feeds}` : ''}`,
    ],
  ].forEach(([term, value]) => list.append(element('dt', term), element('dd', value)));
  return list;
}

function exampleList(examples) {
  const list = element('ul');
  examples.forEach((example) => {
    const item = element('li');
    item.append(element('span', example.text));
    if (example.url) {
      const link = element('a', example.title || 'Open article', 'tag-context__source');
      link.href = example.url;
      link.target = '_blank';
      link.rel = 'noopener';
      item.append(' — ', link);
    }
    list.append(item);
  });
  return list;
}

function ensureOverlay(panel) {
  const document = globalThis.document;
  let overlay = document.getElementById('tag_ngram_overlay');
  if (!overlay) overlay = panel.previousElementSibling;
  if (!overlay || !overlay.classList?.contains('tag-ngram__overlay')) {
    overlay = document.createElement('div');
    overlay.className = 'tag-ngram__overlay';
    overlay.hidden = true;
    panel.before(overlay);
  }
  return overlay;
}

/** Hide the modal details, its overlay and restore page scroll. */
export function closeDetails(panel) {
  if (!panel || panel.hidden) return;
  panel.hidden = true;
  const overlay = globalThis.document.querySelector('.tag-ngram__overlay');
  if (overlay) overlay.hidden = true;
  if (globalThis.document.body) globalThis.document.body.style.overflow = '';
  panel.onkeydown = null;
}

/** Fill the details modal with nodes, show it centered and move focus to it. */
export function openDetails(panel, title, nodes) {
  if (!panel) return;
  const close = element('button', 'Close', 'tag-context__close');
  close.type = 'button';
  close.addEventListener('click', () => closeDetails(panel));
  panel.replaceChildren(close, element('h2', title), ...nodes);
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-modal', 'true');
  const overlay = ensureOverlay(panel);
  overlay.hidden = false;
  overlay.onclick = () => closeDetails(panel);
  panel.onkeydown = (event) => {
    if (event.key === 'Escape') closeDetails(panel);
  };
  if (globalThis.document.body) globalThis.document.body.style.overflow = 'hidden';
  panel.hidden = false;
  panel.focus?.();
}

/** Details for a contrast word: statistics, linked examples and all articles. */
export function showWordDetails(panel, word, context = '') {
  openDetails(panel, `${word.word}${context ? ` · ${context}` : ''}`, [
    statsList(word),
    exampleList(word.examples),
    postsLink(word.post_ids, `Open all ${word.articles} articles`),
  ]);
}

/** Read an option from the URL, falling back when it is not allowed. */
export function urlOption(name, allowed, fallback) {
  const value = new globalThis.URLSearchParams(globalThis.location?.search || '').get(name);
  return allowed.map(String).includes(value) ? value : String(fallback);
}

export function setUrlOption(name, value) {
  const url = new globalThis.URL(globalThis.location.href);
  url.searchParams.set(name, value);
  globalThis.history?.replaceState(null, '', url);
}

/** A labelled <select> that reports changes and keeps the URL in sync. */
export function selectControl(container, { name, label, options, value, onChange }) {
  if (!container) return null;
  const wrapper = element('label', undefined, 'tag-context__control');
  wrapper.append(element('span', label));
  const select = element('select');
  select.name = name;
  options.forEach(([optionValue, text]) => {
    const option = element('option', text);
    option.value = String(optionValue);
    select.append(option);
  });
  select.value = String(value);
  select.addEventListener('change', () => {
    setUrlOption(name, select.value);
    onChange(select.value);
  });
  wrapper.append(select);
  container.append(wrapper);
  return select;
}

/** A "show more" button placed after the chart; update it on every render. */
export function createMoreButton(container, onClick) {
  const button = element('button', '', 'tag-context__more');
  button.type = 'button';
  button.hidden = true;
  button.addEventListener('click', onClick);
  container.after(button);
  return button;
}

export function updateMoreButton(button, remaining, step, noun) {
  button.hidden = remaining <= 0;
  button.textContent = `Show ${Math.min(step, remaining)} more ${noun} (${remaining} hidden)`;
}
