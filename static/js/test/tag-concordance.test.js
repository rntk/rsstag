import { describe, it, expect, vi } from 'vitest';
import { initConcordance, initContextWall, initInsights, initColoring } from '../tag-concordance.js';

function setup(request) {
  const root = document.createElement('div');
  root.innerHTML = `<button data-detail-key="one">Before</button><button data-detail-key="one">After</button>
    <article class="tag-concordance__row" data-post-id="p1" data-sentence-number="1">
    <button class="tag-concordance__read" data-post-id="p1" data-sentence-number="1" data-read="0">Mark Read</button></article>
    <dialog id="concordance-dialog"><button class="tag-concordance__close">Close</button>
    <a class="tag-concordance__article"></a><p class="tag-concordance__metadata"></p><div class="tag-concordance__sentences"></div>
    <p class="tag-concordance__status"></p></dialog><script id="concordance-details" type="application/json"></script>`;
  const post = {
    title: 'Article',
    url: '/posts/p1',
    metadata: { source: '<img src=x>', provider: 'rss', category: 'News' },
    sentences: [
      { number: 1, text: 'Matching sentence.', read: false },
      { number: 2, text: '<img src=x> Full read context.', read: true },
      { number: null, text: 'Unaddressable sentence.' },
    ],
    groups: { '<img src=x>': [1, 2], 'Other topic': [1] },
  };
  root.querySelector('script').textContent = JSON.stringify({
    posts: { p1: post },
    entries: {
      one: { pid: 'p1', number: 1, topics: ['<img src=x>', 'Other topic'], sentence_index: 0 },
      fallback: { pid: 'p1', number: null, topics: [], sentence_index: 2 },
    },
  });
  initConcordance(root, request);
  return root;
}

describe('concordance sentences', () => {
  it('centers the tag when opening a horizontally scrollable wall', () => {
    const root = document.createElement('div');
    root.innerHTML = '<section class="tag-context-wall__scroll"><strong class="tag-context-wall__match">Tag</strong></section>';
    const viewport = root.querySelector('section');
    Object.defineProperties(viewport, {
      clientWidth: { value: 600 },
      scrollWidth: { value: 2000 },
    });
    vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue({ left: 16 });
    vi.spyOn(root.querySelector('strong'), 'getBoundingClientRect').mockReturnValue({
      left: 1116, width: 80,
    });
    initContextWall(root);
    expect(viewport.scrollLeft).toBe(840);
  });

  it('highlights the hovered word in every row, ignoring case and punctuation', () => {
    const root = document.createElement('div');
    root.innerHTML = `<section class="tag-context-wall__scroll"><strong class="tag-context-wall__match">Tag</strong>
      <span class="tag-context-wall__word">… Hello,</span><span class="tag-context-wall__word">world</span>
      <span class="tag-context-wall__word">hello!</span><span class="tag-context-wall__word"></span></section>`;
    const viewport = root.querySelector('section');
    const [first, other, second, empty] = viewport.querySelectorAll('.tag-context-wall__word');
    initContextWall(root);
    first.dispatchEvent(new globalThis.MouseEvent('mouseover', { bubbles: true }));
    expect(first.classList.contains('is-word-match')).toBe(true);
    expect(second.classList.contains('is-word-match')).toBe(true);
    expect(other.classList.contains('is-word-match')).toBe(false);
    other.dispatchEvent(new globalThis.MouseEvent('mouseover', { bubbles: true }));
    expect(first.classList.contains('is-word-match')).toBe(false);
    expect(other.classList.contains('is-word-match')).toBe(true);
    empty.dispatchEvent(new globalThis.MouseEvent('mouseover', { bubbles: true }));
    viewport.dispatchEvent(new globalThis.MouseEvent('mouseleave'));
    expect(viewport.querySelectorAll('.is-word-match')).toHaveLength(0);
  });

  it('leaves empty context walls alone', () => {
    const root = document.createElement('div');
    root.innerHTML = '<section class="tag-context-wall__scroll">No matching sentences.</section>';
    expect(() => initContextWall(root)).not.toThrow();
    expect(root.querySelector('section').scrollLeft).toBe(0);
  });

  it('opens both sides with full topic sentences and safe text', () => {
    const root = setup(vi.fn());
    for (const button of root.querySelectorAll('[data-detail-key]')) {
      button.click();
      expect(root.querySelector('dialog').open).toBe(true);
      expect(root.querySelectorAll('li')).toHaveLength(3);
      expect(root.querySelectorAll('li button')).toHaveLength(3);
      expect(root.querySelector('img')).toBeNull();
      expect(root.querySelector('.tag-concordance__metadata').textContent).toBe(
        'Source: <img src=x> · Provider: rss · Category: News'
      );
      expect(root.querySelector('.is-read p').textContent).toContain('Full read context.');
      root.querySelector('.tag-concordance__close').click();
      expect(root.querySelector('dialog').open).toBe(false);
    }
  });

  it('opens ungrouped full sentences without read controls', () => {
    const root = setup(vi.fn());
    const button = root.querySelector('[data-detail-key]');
    button.dataset.detailKey = 'fallback';
    button.click();
    expect(root.querySelector('li p').textContent).toBe('Unaddressable sentence.');
    expect(root.querySelectorAll('li button')).toHaveLength(0);
  });

  it('keeps padding and content clicks open but closes on backdrop clicks', () => {
    const root = setup(vi.fn());
    root.querySelector('[data-detail-key]').click();
    const dialog = root.querySelector('dialog');
    vi.spyOn(dialog, 'getBoundingClientRect').mockReturnValue({
      left: 100,
      right: 700,
      top: 100,
      bottom: 600,
    });
    dialog.dispatchEvent(
      new globalThis.MouseEvent('click', { bubbles: true, clientX: 105, clientY: 105 })
    );
    expect(dialog.open).toBe(true);
    root.querySelector('li p').click();
    expect(dialog.open).toBe(true);
    dialog.dispatchEvent(
      new globalThis.MouseEvent('click', { bubbles: true, clientX: 99, clientY: 105 })
    );
    expect(dialog.open).toBe(false);
  });

  it('persists read and unread and synchronizes rows and reopened modal', async () => {
    const request = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: 'ok' }) });
    const root = setup(request);
    root.querySelector('[data-detail-key]').click();
    root.querySelector('li button').click();
    await vi.waitFor(() =>
      expect(root.querySelector('article').classList.contains('is-read')).toBe(true)
    );
    expect(JSON.parse(request.mock.calls[0][1].body)).toEqual({
      readed: true,
      selections: [{ post_id: 'p1', sentence_indices: [1] }],
    });
    root.querySelector('.tag-concordance__close').click();
    root.querySelector('[data-detail-key]').click();
    expect(root.querySelector('li button').textContent).toBe('Mark Unread');
    root.querySelector('article button').click();
    await vi.waitFor(() => expect(root.querySelector('li button').textContent).toBe('Mark Read'));
    expect(JSON.parse(request.mock.calls[1][1].body).readed).toBe(false);
  });

  it('retains state and restores controls after failure', async () => {
    const root = setup(vi.fn().mockRejectedValue(new Error('offline')));
    const button = root.querySelector('article button');
    button.click();
    await vi.waitFor(() =>
      expect(root.querySelector('.tag-concordance__status').textContent).toContain(
        'Please try again'
      )
    );
    expect(button.disabled).toBe(false);
    expect(button.dataset.read).toBe('0');
  });

  it('preserves a clickable wall row while synchronizing its read state', async () => {
    const request = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: 'ok' }) });
    const root = setup(request);
    const row = document.createElement('button');
    row.className = 'tag-context-wall__line';
    row.dataset.postId = 'p1';
    row.dataset.sentenceNumber = '1';
    row.dataset.detailKey = 'one';
    row.innerHTML = '<span>Before</span><strong>Matching</strong><span>After</span>';
    root.appendChild(row);
    row.click();
    root.querySelector('li button').click();
    await vi.waitFor(() => expect(row.classList.contains('is-read')).toBe(true));
    expect(row.querySelectorAll('span')).toHaveLength(2);
    expect(row.textContent).toBe('BeforeMatchingAfter');
    expect(row.disabled).toBe(false);
  });
});

describe('tag insights', () => {
  function setupInsights() {
    const root = document.createElement('div');
    root.innerHTML = `<main class="tag-context-wall"><section class="tag-insights">
      <button class="tag-insights__term" data-filter-words="recall recalls" data-filter-label="recall" aria-pressed="false">recall</button>
      <input type="checkbox" class="tag-insights__show-duplicates">
      <p class="tag-insights__filter" hidden><span></span><button class="tag-insights__clear">Clear</button></p>
      </section>
      <button class="tag-context-wall__line" id="a"><span class="tag-context-wall__word">Recalls,</span></button>
      <button class="tag-context-wall__line is-duplicate" id="b"><span class="tag-context-wall__word">other</span></button>
      </main>`;
    document.body.replaceChildren(root);
    initInsights(root);
    return root;
  }

  it('filters rows by any spelling of a clicked word and clears again', () => {
    const root = setupInsights();
    const chip = root.querySelector('.tag-insights__term');
    const status = root.querySelector('.tag-insights__filter');
    chip.click();
    expect(chip.getAttribute('aria-pressed')).toBe('true');
    expect(root.querySelector('#a').classList.contains('is-filtered-out')).toBe(false);
    expect(root.querySelector('#b').classList.contains('is-filtered-out')).toBe(true);
    expect(status.hidden).toBe(false);
    expect(status.textContent).toContain('“recall”');
    root.querySelector('.tag-insights__clear').click();
    expect(chip.getAttribute('aria-pressed')).toBe('false');
    expect(root.querySelector('#b').classList.contains('is-filtered-out')).toBe(false);
    expect(status.hidden).toBe(true);
    chip.click();
    chip.click();
    expect(root.querySelector('#b').classList.contains('is-filtered-out')).toBe(false);
  });

  it('toggles near-duplicate rows', () => {
    const root = setupInsights();
    const toggle = root.querySelector('.tag-insights__show-duplicates');
    toggle.click();
    expect(root.querySelector('.tag-context-wall').classList.contains('show-duplicates')).toBe(true);
    toggle.click();
    expect(root.querySelector('.tag-context-wall').classList.contains('show-duplicates')).toBe(false);
  });
});


describe('word coloring strategies', () => {
  function setupColoring() {
    const root = document.createElement('div');
    root.innerHTML = `<main class="tag-context-wall">
      <select id="wall-coloring-mode">
        <option value="important" data-description="Insight colors">Important words</option>
        <option value="tfidf" data-description="Relative article scores" data-threshold="0.8">TF-IDF</option>
        <option value="none" data-description="No word colors">No coloring</option>
        <option value="custom" data-description="New experiment" data-threshold="0.9">Custom</option>
      </select>
      <label class="tag-context-wall__threshold" hidden><input id="wall-coloring-threshold" type="number" min="0" max="1" step="0.05" value="0.8"></label>
      <p id="wall-coloring-description"></p>
      <button class="tag-context-wall__line is-filtered-out">
        <span id="high" class="tag-context-wall__word is-word-match">Rare!</span>
        <span id="boundary" class="tag-context-wall__word">Boundary</span>
        <span id="low" class="tag-context-wall__word">Ordinary</span>
        <span id="empty" class="tag-context-wall__word"></span>
      </button>
      <strong class="tag-context-wall__match">Root</strong>
    </main>`;
    document.body.replaceChildren(root);
    for (const [id, score] of [['high', 1], ['boundary', 0.8], ['low', 0.79]]) {
      root.querySelector(`#${id}`).dataset.colorings = JSON.stringify({
        important: id === 'high' ? { color: 'before', score: 1 } : null,
        tfidf: { color: 'tfidf', score }, none: null,
        custom: { color: 'after', score },
      });
    }
    root.querySelector('#empty').dataset.colorings = '{}';
    initColoring(root);
    const selector = root.querySelector('select');
    function select(mode) {
      selector.value = mode;
      selector.dispatchEvent(new globalThis.Event('change'));
    }
    return { root, select };
  }

  it('switches instantly with inclusive score boundaries and restores important colors', () => {
    const { root, select } = setupColoring();
    const high = root.querySelector('#high');
    expect(high.classList.contains('tag-context-wall__color-before')).toBe(true);
    expect(root.querySelector('.tag-context-wall__threshold').hidden).toBe(true);
    select('tfidf');
    expect(high.classList.contains('tag-context-wall__color-before')).toBe(false);
    expect(high.classList.contains('tag-context-wall__color-tfidf')).toBe(true);
    expect(root.querySelector('#boundary').classList.contains('tag-context-wall__color-tfidf')).toBe(true);
    expect(root.querySelector('#low').classList.contains('tag-context-wall__color-tfidf')).toBe(false);
    expect(root.querySelector('#empty').classList.length).toBe(1);
    expect(high.title).toBe('TF-IDF score: 1.000');
    expect(root.querySelector('#wall-coloring-description').textContent).toBe('Relative article scores');
    select('none');
    expect(high.classList.contains('tag-context-wall__color-tfidf')).toBe(false);
    expect(high.classList.contains('is-word-match')).toBe(true);
    expect(root.querySelector('.is-filtered-out')).not.toBeNull();
    expect(root.querySelector('.tag-context-wall__match').textContent).toBe('Root');
    expect(high.title).toBe('');
    select('important');
    expect(high.classList.contains('tag-context-wall__color-before')).toBe(true);
  });

  it('adjusts the cutoff, remembers it when switching, and rejects invalid cutoffs', () => {
    const { root, select } = setupColoring();
    select('tfidf');
    const input = root.querySelector('input');
    input.value = '0.75';
    input.dispatchEvent(new globalThis.Event('input'));
    expect(root.querySelector('#low').classList.contains('tag-context-wall__color-tfidf')).toBe(true);
    select('important');
    select('tfidf');
    expect(input.value).toBe('0.75');
    for (const invalid of ['-1', '1.5', '']) {
      input.value = invalid;
      input.dispatchEvent(new globalThis.Event('input'));
      expect(root.querySelector('#low').classList.contains('tag-context-wall__color-tfidf')).toBe(true);
    }
    input.value = '1';
    input.dispatchEvent(new globalThis.Event('input'));
    expect(root.querySelector('#boundary').classList.contains('tag-context-wall__color-tfidf')).toBe(false);
    expect(root.querySelector('#high').classList.contains('tag-context-wall__color-tfidf')).toBe(true);
  });

  it('renders an additional registered mode using the same controls', () => {
    const { root, select } = setupColoring();
    select('custom');
    expect(root.querySelector('input').value).toBe('0.9');
    expect(root.querySelector('#high').classList.contains('tag-context-wall__color-after')).toBe(true);
    expect(root.querySelector('#boundary').classList.contains('tag-context-wall__color-after')).toBe(false);
  });

  it('handles missing and malformed per-word results', () => {
    const { root } = setupColoring();
    root.querySelector('#high').dataset.colorings = 'invalid JSON';
    root.querySelector('#boundary').removeAttribute('data-colorings');
    expect(() => initColoring(root)).not.toThrow();
    expect(root.querySelector('#high').classList.contains('tag-context-wall__color-before')).toBe(false);
  });

  it('does nothing on concordance pages without coloring controls', () => {
    expect(() => initColoring(document.createElement('div'))).not.toThrow();
  });
});
