import * as d3 from 'd3';
import {
  asButton,
  createMoreButton,
  formatPercent,
  openDetails,
  postsLink,
  selectControl,
  updateMoreButton,
  urlOption,
} from './tag-context-shared.js';
import { TagFeedsChart } from './tag-context-feeds.js';
import { TagWordsChart } from './tag-context-words.js';

const ROW_HEIGHT = 190;
const MARGIN = { top: 16, right: 32, bottom: 24, left: 32 };
const MAX_RADIUS = 36;
const MIN_RADIUS = 4;
const CIRCLE_GAP = 6;
const LABEL_GAP = 10;
const LEADER_GAP = 4;
const LABEL_LEVELS = 3;
const LEVEL_HEIGHT = 20;
const LABEL_CHAR_WIDTH = 7.8;
const NAV_WIDTH = 110;
const ROWS_PAGE = 12;
const GAUGE_WIDTH = 64;
// Fixedness of pairs seen fewer times than this is too noisy to rank by.
const MIN_RANKED_COUNT = 3;
export const PHRASE_SORTS = {
  frequency: { label: 'Frequency', compare: (a, b) => b.count - a.count },
  fixed: { label: 'Most fixed', compare: (a, b) => b.fixedness - a.fixedness || b.count - a.count },
  open: { label: 'Most open', compare: (a, b) => a.fixedness - b.fixedness || b.count - a.count },
};

/** Label shown above each circle: the trigram's outer word and its count. */
export function wordLabel(word) {
  return `${word.word} ${word.count}`;
}

function labelWidth(word) {
  return wordLabel(word).length * LABEL_CHAR_WIDTH;
}

/** Leftmost x where a label fits on `level` without covering earlier labels or leaders. */
function levelX(ends, level, halfLabel) {
  let x = ends[level] + LABEL_GAP + halfLabel;
  for (let lower = 0; lower < level; lower += 1) {
    x = Math.max(x, ends[lower] + LEADER_GAP);
  }
  return x;
}

/**
 * Pack words left to right with circles nearly touching. Each label goes on
 * the lowest of several stacked levels where it collides with neither another
 * label nor the leader line of a higher label, so neighbours can sit close.
 */
export function packWords(words, radius, left) {
  const ends = Array(LABEL_LEVELS).fill(-Infinity);
  const placed = [];
  let previous = null;
  for (const word of words) {
    const r = radius(word.count);
    const halfLabel = labelWidth(word) / 2;
    const circleX = previous
      ? previous.x + radius(previous.word.count) + r + CIRCLE_GAP
      : left + Math.max(r, halfLabel);
    let best = null;
    for (let level = 0; level < LABEL_LEVELS; level += 1) {
      const x = Math.max(circleX, levelX(ends, level, halfLabel));
      if (!best || x < best.x) best = { x, level };
    }
    ends[best.level] = best.x + halfLabel;
    for (let lower = 0; lower < best.level; lower += 1) {
      ends[lower] = Math.max(ends[lower], best.x);
    }
    previous = { word, x: best.x, level: best.level };
    placed.push(previous);
  }
  const last = placed[placed.length - 1];
  const width = last
    ? last.x + Math.max(radius(last.word.count), labelWidth(last.word) / 2) - left
    : 0;
  return { placed, width };
}

/** Most frequent first; ties alphabetical. */
function byCount(a, b) {
  return b.count - a.count || a.word.localeCompare(b.word);
}

/** Pack `words` most frequent first, spread evenly over [left, right]. */
export function layoutPage(words, radius, left, right) {
  const { placed, width } = packWords([...words].sort(byCount), radius, left);
  const extra = placed.length ? Math.max(0, right - left - width) / placed.length : 0;
  return placed.map((item, index) => ({ ...item, x: item.x + extra * (index + 0.5) }));
}

/**
 * Split a row into pages: each page takes the most frequent remaining words
 * that still pack into the available width.
 */
export function paginateRow(words, radius, left, right) {
  const sorted = [...words].sort(byCount);
  if (packWords(sorted, radius, left).width <= right - left) {
    return [layoutPage(sorted, radius, left, right)];
  }
  const pageRight = right - NAV_WIDTH;
  const pages = [];
  let start = 0;
  while (start < sorted.length) {
    let end = start + 1;
    while (
      end < sorted.length &&
      packWords(sorted.slice(start, end + 1), radius, left).width <= pageRight - left
    ) {
      end += 1;
    }
    pages.push(layoutPage(sorted.slice(start, end), radius, left, pageRight));
    start = end;
  }
  return pages;
}

/** Order pairs; fixedness sorts push rarely seen pairs to the end. */
export function sortPhraseRows(rows, sort) {
  const compare = (PHRASE_SORTS[sort] || PHRASE_SORTS.frequency).compare;
  const ranked = (row) => sort === 'frequency' || row.count >= MIN_RANKED_COUNT;
  return [...rows].sort(
    (a, b) =>
      Number(ranked(b)) - Number(ranked(a)) || compare(a, b) || a.bigram.localeCompare(b.bigram)
  );
}

/** Row subtitle: support and how predictable the next word is. */
export function phraseSummary(row) {
  const completions = row.distinct === 1 ? '1 completion' : `${row.distinct} completions`;
  return `${row.count} mentions · ${row.posts_count} articles · ${completions} · top ${formatPercent(row.top_share)} · fixedness ${formatPercent(row.fixedness)}`;
}

export class TagNgramChart {
  constructor(container, details, rows, controls = null) {
    this.container = container;
    this.details = details;
    this.controls = controls;
    this.allRows = rows || [];
    this.pageByRow = new Map();
    this.sort = urlOption('sort', Object.keys(PHRASE_SORTS), 'frequency');
    this.limit = ROWS_PAGE;
  }

  init() {
    if (!this.container || !this.allRows.length) return;
    selectControl(this.controls, {
      name: 'sort',
      label: 'Order pairs by',
      options: Object.entries(PHRASE_SORTS).map(([key, sort]) => [key, sort.label]),
      value: this.sort,
      onChange: (value) => {
        this.sort = value;
        this.pageByRow.clear();
        this.render();
      },
    });
    this.more = createMoreButton(this.container, () => {
      this.limit += ROWS_PAGE;
      this.render();
    });
    this.render();
    globalThis.addEventListener('resize', () => this.render());
  }

  render() {
    const sorted = sortPhraseRows(this.allRows, this.sort);
    this.rows = sorted.slice(0, this.limit);
    updateMoreButton(this.more, sorted.length - this.rows.length, ROWS_PAGE, 'pairs');
    const width = Math.max(this.container.clientWidth, 640);
    const height = MARGIN.top + this.rows.length * ROW_HEIGHT + MARGIN.bottom;
    // The radius scale spans every pair so revealing more keeps sizes comparable.
    const maxCount = d3.max(this.allRows, (row) => d3.max(row.words, (word) => word.count)) || 1;
    this.left = MARGIN.left;
    this.right = width - MARGIN.right;
    this.r = d3.scaleSqrt().domain([1, maxCount]).range([MIN_RADIUS, MAX_RADIUS]);
    this.container.replaceChildren();
    const svg = d3
      .select(this.container)
      .append('svg')
      .attr('class', 'tag-ngram__svg')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('width', width)
      .attr('height', height);
    this.rows.forEach((row, index) =>
      this.renderRow(svg, row, row.bigram, MARGIN.top + (index + 1) * ROW_HEIGHT - 20)
    );
  }

  renderRow(svg, row, key, baseline) {
    const group = svg.append('g').attr('class', 'tag-ngram__row');
    group
      .append('text')
      .attr('class', 'tag-ngram__bigram')
      .attr('x', this.left)
      .attr('y', baseline)
      .text(row.bigram);
    this.renderSummary(group, row, baseline - ROW_HEIGHT + 34);
    group
      .append('line')
      .attr('class', 'tag-ngram__baseline')
      .attr('x1', this.left)
      .attr('x2', this.right)
      .attr('y1', baseline)
      .attr('y2', baseline);
    const pages = paginateRow(row.words, this.r, this.left, this.right);
    const page = Math.min(this.pageByRow.get(key) || 0, pages.length - 1);
    this.renderCircles(group, pages[page], baseline);
    this.renderLabels(group, pages[page], baseline);
    this.renderPager(group, pages, page, key, baseline);
  }

  renderSummary(group, row, y) {
    const gauge = group.append('g').attr('class', 'tag-ngram__gauge');
    gauge
      .append('rect')
      .attr('class', 'tag-ngram__gauge-track')
      .attr('x', this.left)
      .attr('y', y - 9)
      .attr('width', GAUGE_WIDTH)
      .attr('height', 8)
      .attr('rx', 4);
    gauge
      .append('rect')
      .attr('class', 'tag-ngram__gauge-fill')
      .attr('x', this.left)
      .attr('y', y - 9)
      .attr('width', GAUGE_WIDTH * row.fixedness)
      .attr('height', 8)
      .attr('rx', 4);
    gauge
      .append('title')
      .text(`Fixedness ${formatPercent(row.fixedness)} · entropy ${row.entropy} bits`);
    group
      .append('text')
      .attr('class', 'tag-ngram__summary-text')
      .attr('x', this.left + GAUGE_WIDTH + 8)
      .attr('y', y)
      .text(`${row.bigram} · ${phraseSummary(row)}`);
  }
  renderCircles(group, placed, baseline) {
    const circles = group
      .append('g')
      .selectAll('circle')
      .data(placed)
      .join('circle')
      .attr('class', 'tag-ngram__word')
      .attr('cx', (item) => item.x)
      .attr('cy', (item) => baseline - this.r(item.word.count))
      .attr('r', (item) => this.r(item.word.count));
    asButton(circles, (item) => this.showDetails(item.word))
      .append('title')
      .text((item) => `${item.word.trigram} · ${item.word.count}`);
  }

  renderLabels(group, placed, baseline) {
    const lowest = baseline - 2 * MAX_RADIUS - 12;
    placed.forEach(({ word, x, level }) => {
      const y = lowest - level * LEVEL_HEIGHT;
      group
        .append('line')
        .attr('class', 'tag-ngram__leader')
        .attr('x1', x)
        .attr('x2', x)
        .attr('y1', y + 4)
        .attr('y2', baseline - 2 * this.r(word.count));
      const label = group
        .append('text')
        .attr('class', 'tag-ngram__label')
        .attr('x', x)
        .attr('y', y)
        .on('click', () => this.showDetails(word));
      label.append('tspan').attr('class', 'tag-ngram__label-word').text(word.word);
      label.append('tspan').attr('class', 'tag-ngram__label-count').attr('dx', 4).text(word.count);
      label.append('title').text(`${word.trigram}: ${word.count} occurrences`);
    });
  }

  renderPager(group, pages, page, key, baseline) {
    if (pages.length < 2) return;
    const x = this.right - NAV_WIDTH + 16;
    const remaining = d3.sum(pages.slice(page + 1), (items) => items.length);
    const controls = [
      { text: `${page + 1} / ${pages.length}`, y: baseline - 44 },
      page > 0 && { text: '‹ prev', y: baseline - 24, page: page - 1 },
      remaining && { text: `+${remaining} more ›`, y: baseline - 6, page: page + 1 },
    ].filter(Boolean);
    controls.forEach((control) => {
      const text = group
        .append('text')
        .attr('class', control.page === undefined ? 'tag-ngram__page' : 'tag-ngram__more')
        .attr('x', x)
        .attr('y', control.y)
        .text(control.text);
      if (control.page === undefined) return;
      text
        .attr('tabindex', 0)
        .attr('role', 'button')
        .on('click keydown', (event) => {
          if (event.type === 'keydown' && event.key !== 'Enter') return;
          this.pageByRow.set(key, control.page);
          this.render();
        });
    });
  }

  showDetails(word) {
    const list = globalThis.document.createElement('ul');
    word.snippets.forEach((snippet) => {
      const item = globalThis.document.createElement('li');
      item.textContent = snippet;
      list.append(item);
    });
    openDetails(this.details, `${word.trigram} · ${word.count} in ${word.posts_count} posts`, [
      list,
      postsLink(word.post_ids, 'Open posts'),
    ]);
  }
}

/** Point each view tab at the current URL with only the view swapped. */
export function syncTabs(document, search) {
  document.querySelectorAll('.tag-ngram__tab[data-view]').forEach((tab) => {
    const params = new globalThis.URLSearchParams(search);
    params.set('view', tab.dataset.view);
    params.delete('sort');
    params.delete('labels');
    tab.search = `?${params}`;
  });
}

const VIEW_CHARTS = {
  words: TagWordsChart,
  feeds: TagFeedsChart,
};

/** Mount the chart for the current view and keep the scope on links. */
export function initTagNgramChartPage() {
  const document = globalThis.document;
  const data = globalThis.tagNgramData || { view: 'phrases', rows: [] };
  const switchLink = document.getElementById('ngram_hierarchy_switch');
  if (switchLink) switchLink.search = globalThis.location.search;
  syncTabs(document, globalThis.location.search);
  const container = document.getElementById('tag_ngram_chart_canvas');
  const details = document.getElementById('tag_ngram_details');
  const controls = document.getElementById('tag_ngram_controls');
  const Chart = VIEW_CHARTS[data.view];
  if (Chart) new Chart(container, details, controls, data).init();
  else new TagNgramChart(container, details, data.rows, controls).init();
}
