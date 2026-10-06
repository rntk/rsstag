import * as d3 from 'd3';
import {
  articleRadius,
  asButton,
  createMoreButton,
  formatLift,
  isSignificant,
  liftScale,
  renderLiftAxis,
  selectControl,
  showWordDetails,
  updateMoreButton,
  urlOption,
} from './tag-context-shared.js';

const ROW_HEIGHT = 26;
const MARGIN = { top: 12, right: 96, bottom: 32, left: 170 };
const MAX_RADIUS = 10;
const PAGE = 40;
const SUPPORT = [1, 2, 3, 5];
export const WORD_SORTS = {
  z: { label: 'Confidence (z-score)', compare: (a, b) => b.z - a.z },
  lift: { label: 'Lift', compare: (a, b) => b.lift - a.lift || b.z - a.z },
  articles: { label: 'Articles', compare: (a, b) => b.articles - a.articles || b.z - a.z },
};

/** Words meeting the support threshold, ordered by the selected sort. */
export function visibleWords(words, sort, minArticles) {
  const compare = (WORD_SORTS[sort] || WORD_SORTS.z).compare;
  return words
    .filter((word) => word.articles >= minArticles)
    .sort((a, b) => compare(a, b) || a.word.localeCompare(b.word));
}

/** Forest plot: one row per word with its lift, 95% interval and article support. */
export class TagWordsChart {
  constructor(container, details, controls, data) {
    this.container = container;
    this.details = details;
    this.controls = controls;
    this.words = data.words || [];
    this.sort = urlOption('sort', Object.keys(WORD_SORTS), 'z');
    this.minArticles = Number(urlOption('min', SUPPORT, 2));
    this.limit = PAGE;
  }

  init() {
    if (!this.container) return;
    this.renderControls();
    this.more = createMoreButton(this.container, () => {
      this.limit += PAGE;
      this.render();
    });
    this.render();
    globalThis.addEventListener('resize', () => this.render());
  }

  renderControls() {
    selectControl(this.controls, {
      name: 'sort',
      label: 'Order by',
      options: Object.entries(WORD_SORTS).map(([key, sort]) => [key, sort.label]),
      value: this.sort,
      onChange: (value) => {
        this.sort = value;
        this.render();
      },
    });
    selectControl(this.controls, {
      name: 'min',
      label: 'Minimum articles',
      options: SUPPORT.map((value) => [value, `${value}+`]),
      value: this.minArticles,
      onChange: (value) => {
        this.minArticles = Number(value);
        this.limit = PAGE;
        this.render();
      },
    });
  }

  render() {
    const all = visibleWords(this.words, this.sort, this.minArticles);
    const shown = all.slice(0, this.limit);
    updateMoreButton(this.more, all.length - shown.length, PAGE, 'words');
    this.container.replaceChildren();
    if (!shown.length) {
      const empty = globalThis.document.createElement('p');
      empty.className = 'tag-ngram__empty';
      empty.textContent = 'No words have this much article support. Lower the minimum.';
      this.container.append(empty);
      return;
    }
    const width = Math.max(this.container.clientWidth, 640);
    const height = MARGIN.top + shown.length * ROW_HEIGHT + MARGIN.bottom;
    // Scales use every word passing the filter so "show more" keeps them fixed.
    this.x = liftScale(all, [MARGIN.left, width - MARGIN.right]);
    this.r = articleRadius(all, MAX_RADIUS);
    const svg = d3
      .select(this.container)
      .append('svg')
      .attr('class', 'tag-ngram__svg')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('width', width)
      .attr('height', height);
    renderLiftAxis(svg, this.x, MARGIN.top, height - MARGIN.bottom);
    this.renderRows(svg, shown, width);
  }

  renderRows(svg, words, width) {
    const rows = svg
      .append('g')
      .selectAll('g')
      .data(words)
      .join('g')
      .attr(
        'class',
        (word) => `tag-context__row${isSignificant(word) ? '' : ' tag-context__row--weak'}`
      )
      .attr('transform', (_, index) => `translate(0, ${MARGIN.top + (index + 0.5) * ROW_HEIGHT})`)
      .attr(
        'aria-label',
        (word) => `${word.word}: ${formatLift(word.lift)} lift, ${word.articles} articles`
      );
    asButton(rows, (word) => showWordDetails(this.details, word));
    rows
      .append('rect')
      .attr('class', 'tag-context__hit')
      .attr('x', 0)
      .attr('y', -ROW_HEIGHT / 2)
      .attr('width', width)
      .attr('height', ROW_HEIGHT);
    rows
      .append('text')
      .attr('class', 'tag-context__word')
      .attr('x', MARGIN.left - 14)
      .attr('dy', '0.35em')
      .text((word) => word.word);
    rows
      .append('line')
      .attr('class', 'tag-context__interval')
      .attr('x1', (word) => this.x(word.lift_low))
      .attr('x2', (word) => this.x(word.lift_high));
    rows
      .append('circle')
      .attr('class', 'tag-context__dot')
      .attr('cx', (word) => this.x(word.lift))
      .attr('r', (word) => Math.max(2.5, this.r(word.articles)));
    rows
      .append('text')
      .attr('class', 'tag-context__value')
      .attr('x', width - MARGIN.right + 12)
      .attr('dy', '0.35em')
      .text((word) => `${formatLift(word.lift)} · ${word.articles} art.`);
  }
}
