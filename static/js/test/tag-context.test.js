import { describe, it, expect, beforeEach } from 'vitest';
import {
  assignLabelLevels,
  closeDetails,
  formatLift,
  liftScale,
  liftTicks,
  openDetails,
  showWordDetails,
} from '../components/tag-context-shared.js';
import { TagWordsChart, visibleWords } from '../components/tag-context-words.js';
import { TagFeedsChart, filterFeedRows, labelCandidates } from '../components/tag-context-feeds.js';

function word(name, { lift = 2, z = 3, articles = 3 } = {}) {
  return {
    word: name,
    sentences: 4,
    reference_sentences: 1,
    articles,
    post_ids: ['p1', 'p2'],
    feeds: [{ title: 'One', count: 3 }],
    feed_count: 1,
    top_feed_share: 0.75,
    lift,
    lift_low: lift / 2,
    lift_high: lift * 2,
    z,
    examples: [{ text: 'the <b>codex</b> cli', url: 'https://example.com/p1', title: 'P1' }],
  };
}

beforeEach(() => {
  document.body.innerHTML =
    '<div id="controls"></div><div id="chart"></div><aside id="details" hidden></aside>';
  globalThis.history.replaceState(null, '', '/tag-ngram-chart?tag=codex');
});

const el = (id) => document.getElementById(id);

describe('tag context helpers', () => {
  it('formats lift and builds a log2 scale that always contains 1×', () => {
    expect([0.5, 1, 2.4, 16].map(formatLift)).toEqual(['0.5×', '1×', '2.4×', '16×']);
    const scale = liftScale([word('a', { lift: 4 })], [0, 100]);
    expect(scale.domain()).toEqual([0.5, 8]);
    expect(liftTicks(scale)).toEqual([0.5, 1, 2, 4, 8]);
  });

  it('stacks overlapping labels and drops ones that do not fit', () => {
    const items = [0, 10, 20, 30].map((x) => ({ x }));
    const placed = assignLabelLevels(items, 3, () => 40);
    expect(placed.map((item) => item.level)).toEqual([0, 1, 2]);
  });

  it('renders details with text nodes, statistics and article links', () => {
    showWordDetails(el('details'), word('cli'), 'One');
    const details = el('details');
    expect(details.hidden).toBe(false);
    expect(details.querySelector('h2').textContent).toBe('cli · One');
    expect(details.querySelector('li span').textContent).toBe('the <b>codex</b> cli');
    expect(details.querySelector('b')).toBeNull();
    expect(details.querySelector('.tag-context__source').href).toBe('https://example.com/p1');
    expect([...details.querySelectorAll('a')].at(-1).getAttribute('href')).toBe('/posts/p1_p2');
    details.querySelector('.tag-context__close').click();
    expect(details.hidden).toBe(true);
  });

  it('shows details as a centered modal with overlay, Escape and overlay close', () => {
    const details = el('details');
    openDetails(details, 'cli', [document.createElement('ul')]);
    expect(details.hidden).toBe(false);
    expect(details.getAttribute('role')).toBe('dialog');
    expect(details.getAttribute('aria-modal')).toBe('true');
    const overlay = document.querySelector('.tag-ngram__overlay');
    expect(overlay.hidden).toBe(false);
    expect(document.body.style.overflow).toBe('hidden');
    details.dispatchEvent(new globalThis.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(details.hidden).toBe(true);
    expect(overlay.hidden).toBe(true);
    expect(document.body.style.overflow).toBe('');
    openDetails(details, 'cli', [document.createElement('ul')]);
    overlay.onclick();
    expect(details.hidden).toBe(true);
    openDetails(details, 'cli', [document.createElement('ul')]);
    closeDetails(details);
    expect(details.hidden).toBe(true);
    expect(document.querySelector('.tag-ngram__overlay').hidden).toBe(true);
  });
});

describe('distinctive words chart', () => {
  const words = [
    word('cli', { lift: 3, z: 5, articles: 3 }),
    word('rare', { lift: 20, z: 1, articles: 1 }),
    word('tool', { lift: 2, z: 4, articles: 6 }),
  ];

  it('filters by support and sorts by the chosen statistic', () => {
    expect(visibleWords(words, 'z', 2).map((w) => w.word)).toEqual(['cli', 'tool']);
    expect(visibleWords(words, 'lift', 1).map((w) => w.word)).toEqual(['rare', 'cli', 'tool']);
    expect(visibleWords(words, 'articles', 1).map((w) => w.word)).toEqual(['tool', 'cli', 'rare']);
  });

  it('draws a row per word with interval, fades weak words and opens details', () => {
    new TagWordsChart(el('chart'), el('details'), el('controls'), { words }).init();
    const rows = [...document.querySelectorAll('.tag-context__row')];
    expect(rows.map((row) => row.querySelector('.tag-context__word').textContent)).toEqual([
      'cli',
      'tool',
    ]);
    expect(document.querySelectorAll('.tag-context__interval')).toHaveLength(2);
    expect(document.querySelector('.tag-context__reference')).not.toBeNull();
    rows[0].dispatchEvent(new globalThis.KeyboardEvent('keydown', { key: 'Enter' }));
    expect(el('details').querySelector('h2').textContent).toBe('cli');
  });

  it('changes support from the control and records it in the URL', () => {
    new TagWordsChart(el('chart'), el('details'), el('controls'), { words }).init();
    const select = document.querySelector('select[name="min"]');
    select.value = '1';
    select.dispatchEvent(new globalThis.Event('change'));
    expect(document.querySelectorAll('.tag-context__row')).toHaveLength(3);
    expect(document.querySelector('.tag-context__row--weak .tag-context__word').textContent).toBe(
      'rare'
    );
    expect(new globalThis.URLSearchParams(globalThis.location.search).get('min')).toBe('1');
  });
});

describe('feed framing chart', () => {
  const rows = [
    {
      feed_id: 'one',
      title: 'One',
      sentences: 6,
      articles: 3,
      share: 0.6,
      words: [word('cli'), word('tool', { articles: 1, z: 1 })],
    },
    {
      feed_id: 'two',
      title: 'Two',
      sentences: 4,
      articles: 1,
      share: 0.4,
      words: [word('pricing', { articles: 1 })],
    },
  ];

  it('keeps every feed row while filtering words by support', () => {
    const filtered = filterFeedRows(rows, 2);
    expect(filtered.map((row) => row.words.map((w) => w.word))).toEqual([['cli'], []]);
  });

  it('labels significant words before weak ones', () => {
    const labelled = labelCandidates([word('weak', { z: 1 }), word('strong', { z: 2 })], 1);
    expect(labelled.map((w) => w.word)).toEqual(['strong']);
  });

  it('draws a strip per feed with watermark, subtitle and clickable bubbles', () => {
    new TagFeedsChart(el('chart'), el('details'), el('controls'), { rows }).init();
    expect(
      [...document.querySelectorAll('.tag-context__watermark')].map((n) => n.textContent)
    ).toEqual(['One', 'Two']);
    expect(document.querySelector('.tag-context__subtitle').textContent).toBe(
      'One · 3 articles · 6 sentences · 60% of tag sentences'
    );
    expect(document.querySelectorAll('.tag-context__bubble')).toHaveLength(3);
    expect(document.querySelectorAll('.tag-context__bubble--weak')).toHaveLength(1);
    document
      .querySelector('.tag-context__bubble')
      .dispatchEvent(new globalThis.MouseEvent('click'));
    expect(el('details').querySelector('h2').textContent).toMatch(/· One$/);
  });

  it('notes feeds left without words at a higher support level', () => {
    new TagFeedsChart(el('chart'), el('details'), el('controls'), { rows }).init();
    const select = document.querySelector('select[name="min"]');
    select.value = '2';
    select.dispatchEvent(new globalThis.Event('change'));
    expect(document.querySelector('.tag-context__note').textContent).toBe(
      'No distinctive words at this support level'
    );
  });
});
