import { describe, it, expect, beforeEach } from 'vitest';
import {
  TagNgramChart,
  layoutPage,
  packWords,
  paginateRow,
  phraseSummary,
  sortPhraseRows,
  syncTabs,
  wordLabel,
} from '../components/tag-ngram-chart.js';

function word(name, count) {
  return {
    word: name,
    trigram: `codex cli ${name}`,
    count,
    posts_count: count,
    post_ids: ['p1', 'p3'],
    snippets: [`codex cli ${name}`],
  };
}

function row(bigram, count, fixedness, words = [word('tool', 2), word('app', 1)]) {
  return {
    bigram,
    count,
    posts_count: count,
    distinct: words.length,
    top_share: 0.5,
    fixedness,
    entropy: 1,
    words,
  };
}

const rows = [row('codex cli', 3, 0.08)];
const radius = () => 10;
const CHAR = 7.8;

function labelBox(item) {
  const half = (wordLabel(item.word).length * CHAR) / 2;
  return [item.x - half, item.x + half];
}

beforeEach(() => {
  document.body.innerHTML = '<div id="chart"></div><aside id="details" hidden></aside>';
});

describe('tag n-gram chart', () => {
  it('renders bigram backgrounds with a labelled circle for every word', () => {
    new TagNgramChart(
      document.getElementById('chart'),
      document.getElementById('details'),
      rows
    ).init();
    expect(document.querySelector('.tag-ngram__bigram').textContent).toBe('codex cli');
    expect(document.querySelectorAll('.tag-ngram__word')).toHaveLength(2);
    const labels = [...document.querySelectorAll('.tag-ngram__label')];
    expect(labels.map((el) => el.querySelector('.tag-ngram__label-word').textContent)).toEqual([
      'tool',
      'app',
    ]);
    expect(labels.map((el) => el.querySelector('.tag-ngram__label-count').textContent)).toEqual([
      '2',
      '1',
    ]);
    expect(document.querySelector('.tag-ngram__more')).toBeNull();
  });

  it('shows snippets and a posts link when a circle is clicked', () => {
    new TagNgramChart(
      document.getElementById('chart'),
      document.getElementById('details'),
      rows
    ).init();
    const tool = [...document.querySelectorAll('.tag-ngram__word')].find((el) =>
      el.textContent.startsWith('codex cli tool')
    );
    tool.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }));
    const details = document.getElementById('details');
    expect(details.hidden).toBe(false);
    expect(details.querySelector('a').getAttribute('href')).toBe('/posts/p1_p3');
  });

  it('packs circles closer than labels by stacking labels on levels', () => {
    const words = ['alpha', 'bravo', 'charlie', 'delta'].map((name) => word(name, 1));
    const { placed } = packWords(words, radius, 0);
    expect(new Set(placed.map((item) => item.level)).size).toBeGreaterThan(1);
    expect(placed[1].x - placed[0].x).toBeLessThan(wordLabel(words[0]).length * CHAR);
    placed.forEach((a, i) =>
      placed.slice(i + 1).forEach((b) => {
        if (a.level !== b.level) return;
        expect(labelBox(a)[1]).toBeLessThan(labelBox(b)[0]);
      })
    );
  });

  it('keeps leaders of higher labels clear of lower labels', () => {
    const words = Array.from({ length: 12 }, (_, i) => word(`word${i}`, 1));
    const placed = layoutPage(words, radius, 0, 2000);
    placed.forEach((high) =>
      placed
        .filter((low) => low.level < high.level && low !== high)
        .forEach((low) => {
          const [from, to] = labelBox(low);
          expect(high.x < from || high.x > to).toBe(true);
        })
    );
  });

  it('splits crowded rows into pages ordered by frequency', () => {
    const words = Array.from({ length: 40 }, (_, i) =>
      word(`w${String(i).padStart(2, '0')}`, 40 - i)
    );
    const pages = paginateRow(words, radius, 0, 600);
    expect(pages.length).toBeGreaterThan(1);
    expect(pages.flat()).toHaveLength(40);
    expect(pages[0].some((item) => item.word.word === 'w00')).toBe(true);
    expect(pages.at(-1).some((item) => item.word.word === 'w39')).toBe(true);
  });

  it('switches pages with the clickable "more" and "prev" controls', () => {
    const words = Array.from({ length: 40 }, (_, i) => word(`w${i}`, 40 - i));
    new TagNgramChart(document.getElementById('chart'), null, [
      row('codex cli', 40, 0.1, words),
    ]).init();
    const firstPage = document.querySelectorAll('.tag-ngram__word').length;
    const more = document.querySelector('.tag-ngram__more');
    expect(more.textContent).toBe(`+${40 - firstPage} more ›`);
    more.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }));
    expect(document.querySelector('.tag-ngram__page').textContent).toMatch(/^2 \//);
    const prev = [...document.querySelectorAll('.tag-ngram__more')].find(
      (el) => el.textContent === '‹ prev'
    );
    prev.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }));
    expect(document.querySelector('.tag-ngram__page').textContent).toMatch(/^1 \//);
  });

  it('shows the fixedness gauge and summary for every pair', () => {
    new TagNgramChart(document.getElementById('chart'), null, rows).init();
    expect(document.querySelector('.tag-ngram__summary-text').textContent).toBe(
      'codex cli · 3 mentions · 3 articles · 2 completions · top 50% · fixedness 8%'
    );
    expect(
      Number(document.querySelector('.tag-ngram__gauge-fill').getAttribute('width'))
    ).toBeCloseTo(64 * 0.08);
    expect(phraseSummary({ ...rows[0], distinct: 1 })).toContain('1 completion ·');
  });

  it('orders pairs by fixedness and keeps rare pairs last', () => {
    const data = [row('a', 10, 0.2), row('b', 5, 0.9), row('rare', 1, 1), row('c', 8, 0.5)];
    expect(sortPhraseRows(data, 'fixed').map((r) => r.bigram)).toEqual(['b', 'c', 'a', 'rare']);
    expect(sortPhraseRows(data, 'open').map((r) => r.bigram)).toEqual(['a', 'c', 'b', 'rare']);
    expect(sortPhraseRows(data, 'frequency').map((r) => r.bigram)).toEqual(['a', 'c', 'b', 'rare']);
  });

  it('shows twelve pairs, then reveals more with the button', () => {
    const many = Array.from({ length: 15 }, (_, i) => row(`pair ${i}`, 30 - i, 0.5));
    new TagNgramChart(document.getElementById('chart'), null, many).init();
    expect(document.querySelectorAll('.tag-ngram__row')).toHaveLength(12);
    const more = document.querySelector('.tag-context__more');
    expect(more.textContent).toBe('Show 3 more pairs (3 hidden)');
    more.click();
    expect(document.querySelectorAll('.tag-ngram__row')).toHaveLength(15);
    expect(more.hidden).toBe(true);
  });

  it('keeps scope on view tabs and drops view-specific options', () => {
    document.body.innerHTML =
      '<a class="tag-ngram__tab" data-view="words" href="?tag=x&view=words"></a>';
    syncTabs(document, '?tag=codex&feed=one&view=phrases&sort=fixed');
    const params = new globalThis.URLSearchParams(document.querySelector('a').search);
    expect(Object.fromEntries(params)).toEqual({ tag: 'codex', feed: 'one', view: 'words' });
  });
});
