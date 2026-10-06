import * as d3 from 'd3';

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
  const width = last ? last.x + Math.max(radius(last.word.count), labelWidth(last.word) / 2) - left : 0;
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

export class TagNgramChart {
  constructor(container, details, rows) {
    this.container = container;
    this.details = details;
    this.rows = rows || [];
    this.pageByRow = new Map();
  }

  init() {
    if (!this.container || !this.rows.length) return;
    this.render();
    globalThis.addEventListener('resize', () => this.render());
  }

  render() {
    const width = Math.max(this.container.clientWidth, 640);
    const height = MARGIN.top + this.rows.length * ROW_HEIGHT + MARGIN.bottom;
    const maxCount = d3.max(this.rows, (row) => d3.max(row.words, (word) => word.count)) || 1;
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
      this.renderRow(svg, row, index, MARGIN.top + (index + 1) * ROW_HEIGHT - 20)
    );
  }

  renderRow(svg, row, index, baseline) {
    const group = svg.append('g').attr('class', 'tag-ngram__row');
    group
      .append('text')
      .attr('class', 'tag-ngram__bigram')
      .attr('x', this.left)
      .attr('y', baseline)
      .text(row.bigram);
    group
      .append('line')
      .attr('class', 'tag-ngram__baseline')
      .attr('x1', this.left)
      .attr('x2', this.right)
      .attr('y1', baseline)
      .attr('y2', baseline);
    const pages = paginateRow(row.words, this.r, this.left, this.right);
    const page = Math.min(this.pageByRow.get(index) || 0, pages.length - 1);
    this.renderCircles(group, pages[page], baseline);
    this.renderLabels(group, pages[page], baseline);
    this.renderPager(group, pages, page, index, baseline);
  }

  renderCircles(group, placed, baseline) {
    group
      .append('g')
      .selectAll('circle')
      .data(placed)
      .join('circle')
      .attr('class', 'tag-ngram__word')
      .attr('cx', (item) => item.x)
      .attr('cy', (item) => baseline - this.r(item.word.count))
      .attr('r', (item) => this.r(item.word.count))
      .attr('tabindex', 0)
      .on('click keydown', (event, item) => {
        if (event.type === 'keydown' && event.key !== 'Enter') return;
        this.showDetails(item.word);
      })
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

  renderPager(group, pages, page, index, baseline) {
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
          this.pageByRow.set(index, control.page);
          this.render();
        });
    });
  }

  showDetails(word) {
    if (!this.details) return;
    const document = globalThis.document;
    const title = document.createElement('h2');
    title.textContent = `${word.trigram} · ${word.count} in ${word.posts_count} posts`;
    const list = document.createElement('ul');
    word.snippets.forEach((snippet) => {
      const item = document.createElement('li');
      item.textContent = snippet;
      list.append(item);
    });
    const link = document.createElement('a');
    link.href = `/posts/${word.post_ids.join('_')}`;
    link.textContent = 'Open posts';
    this.details.replaceChildren(title, list, link);
    this.details.hidden = false;
  }
}

/** Mount the chart on /tag-ngram-chart and keep the scope on the hierarchy link. */
export function initTagNgramChartPage() {
  const document = globalThis.document;
  const switchLink = document.getElementById('ngram_hierarchy_switch');
  if (switchLink) switchLink.search = globalThis.location.search;
  new TagNgramChart(
    document.getElementById('tag_ngram_chart_canvas'),
    document.getElementById('tag_ngram_details'),
    globalThis.tagNgramRows
  ).init();
}
