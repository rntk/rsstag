import * as d3 from 'd3';
import {
  LABEL_CHAR_WIDTH,
  articleRadius,
  asButton,
  assignLabelLevels,
  formatPercent,
  isSignificant,
  liftScale,
  renderLiftAxis,
  selectControl,
  showWordDetails,
  urlOption,
} from './tag-context-shared.js';

const MARGIN = { top: 8, right: 40, bottom: 32, left: 32 };
const MAX_RADIUS = 16;
const LEVELS = 3;
const LEVEL_HEIGHT = 18;
const ROW_HEIGHT = 2 * MAX_RADIUS + LEVELS * LEVEL_HEIGHT + 64;
const LABELS = [3, 6, 10];
const SUPPORT = [1, 2, 3];

/** Feed rows with words meeting the support threshold; empty rows are kept. */
export function filterFeedRows(rows, minArticles) {
  return rows.map((row) => ({
    ...row,
    words: row.words.filter((word) => word.articles >= minArticles),
  }));
}

/** The `count` strongest words of a row, significant words first. */
export function labelCandidates(words, count) {
  return [...words]
    .sort((a, b) => Number(isSignificant(b)) - Number(isSignificant(a)) || b.z - a.z)
    .slice(0, count);
}

function labelWidth(item) {
  return item.word.word.length * LABEL_CHAR_WIDTH + 6;
}

/** Strip plot: one row per feed, its distinctive words placed by lift against other feeds. */
export class TagFeedsChart {
  constructor(container, details, controls, data) {
    this.container = container;
    this.details = details;
    this.controls = controls;
    this.rows = data.rows || [];
    this.minArticles = Number(urlOption('min', SUPPORT, 1));
    this.labels = Number(urlOption('labels', LABELS, 6));
  }

  init() {
    if (!this.container) return;
    this.renderControls();
    this.render();
    globalThis.addEventListener('resize', () => this.render());
  }

  renderControls() {
    selectControl(this.controls, {
      name: 'min',
      label: 'Minimum articles',
      options: SUPPORT.map((value) => [value, `${value}+`]),
      value: this.minArticles,
      onChange: (value) => {
        this.minArticles = Number(value);
        this.render();
      },
    });
    selectControl(this.controls, {
      name: 'labels',
      label: 'Labels per feed',
      options: LABELS.map((value) => [value, `${value}`]),
      value: this.labels,
      onChange: (value) => {
        this.labels = Number(value);
        this.render();
      },
    });
  }

  render() {
    const rows = filterFeedRows(this.rows, this.minArticles);
    const words = rows.flatMap((row) => row.words);
    const width = Math.max(this.container.clientWidth, 640);
    const height = MARGIN.top + rows.length * ROW_HEIGHT + MARGIN.bottom;
    this.x = liftScale(words, [MARGIN.left + MAX_RADIUS, width - MARGIN.right], false);
    this.r = articleRadius(words, MAX_RADIUS);
    this.container.replaceChildren();
    const svg = d3
      .select(this.container)
      .append('svg')
      .attr('class', 'tag-ngram__svg')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('width', width)
      .attr('height', height);
    renderLiftAxis(svg, this.x, MARGIN.top, height - MARGIN.bottom);
    rows.forEach((row, index) => this.renderRow(svg, row, MARGIN.top + index * ROW_HEIGHT, width));
  }

  renderRow(svg, row, top, width) {
    const baseline = top + ROW_HEIGHT - 20;
    const group = svg.append('g').attr('class', 'tag-context__feed');
    group
      .append('text')
      .attr('class', 'tag-context__watermark')
      .attr('x', MARGIN.left)
      .attr('y', baseline)
      .text(row.title);
    group
      .append('text')
      .attr('class', 'tag-context__subtitle')
      .attr('x', MARGIN.left)
      .attr('y', top + 18)
      .text(
        `${row.title} · ${row.articles} articles · ${row.sentences} sentences · ${formatPercent(row.share)} of tag sentences`
      );
    group
      .append('line')
      .attr('class', 'tag-ngram__baseline')
      .attr('x1', MARGIN.left)
      .attr('x2', width - MARGIN.right)
      .attr('y1', baseline)
      .attr('y2', baseline);
    if (!row.words.length) {
      group
        .append('text')
        .attr('class', 'tag-context__note')
        .attr('x', MARGIN.left)
        .attr('y', baseline - 8)
        .text('No distinctive words at this support level');
      return;
    }
    this.renderDots(group, row, baseline);
    this.renderLabels(group, row, baseline);
  }

  renderDots(group, row, baseline) {
    // Larger circles first so small ones stay clickable on top.
    const words = [...row.words].sort((a, b) => b.articles - a.articles);
    const dots = group
      .append('g')
      .selectAll('circle')
      .data(words)
      .join('circle')
      .attr(
        'class',
        (word) => `tag-context__bubble${isSignificant(word) ? '' : ' tag-context__bubble--weak'}`
      )
      .attr('cx', (word) => this.x(word.lift))
      .attr('cy', (word) => baseline - Math.max(3, this.r(word.articles)))
      .attr('r', (word) => Math.max(3, this.r(word.articles)))
      .attr('aria-label', (word) => `${word.word} in ${row.title}`);
    asButton(dots, (word) => showWordDetails(this.details, word, row.title));
    dots.append('title').text((word) => `${word.word} · ${word.articles} articles`);
  }

  renderLabels(group, row, baseline) {
    const candidates = labelCandidates(row.words, this.labels).map((word) => ({
      word,
      x: this.x(word.lift),
    }));
    const lowest = baseline - 2 * MAX_RADIUS - 8;
    assignLabelLevels(candidates, LEVELS, labelWidth).forEach(({ word, x, level }) => {
      const y = lowest - level * LEVEL_HEIGHT;
      group
        .append('line')
        .attr('class', 'tag-ngram__leader')
        .attr('x1', x)
        .attr('x2', x)
        .attr('y1', y + 4)
        .attr('y2', baseline - 2 * Math.max(3, this.r(word.articles)));
      const label = group
        .append('text')
        .attr('class', 'tag-ngram__label')
        .attr('x', x)
        .attr('y', y)
        .text(word.word);
      asButton(label, () => showWordDetails(this.details, word, row.title));
    });
  }
}
