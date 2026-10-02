import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

import {
  buildNavigationList,
  buildSummaryRequest,
  buildTopicCards,
  cursorAnchoredTranslate,
  findNavigationTarget,
  getMaxTopicLevel,
  getRailWidth,
  getZoomCardWidth,
  layoutCards,
  splitSentenceRuns,
} from '../libs/post-canvas.js';
import { createSummaryStore, fetchTopicSummary } from '../libs/post-canvas-summaries.js';

const { JSDOM } = createRequire(import.meta.url)('jsdom');

const sentence = (number, post_id = 'post-1') => ({
  number,
  post_id,
  post_sentence_number: number,
  text: `Sentence ${number}.`,
});

const byNumber = (sentences) => new Map(sentences.map((s) => [s.number, s]));

test('splitSentenceRuns sorts, dedupes, skips unknown and splits at gaps and posts', () => {
  const sentences = byNumber([sentence(1), sentence(2), sentence(3, 'post-2'), sentence(5)]);

  assert.deepEqual(splitSentenceRuns([5, 2, 1, 1, 3, 4], sentences), [[1, 2], [3], [5]]);
});

test('buildTopicCards rolls paths up per level and keeps chronological runs', () => {
  const data = {
    sentences: [1, 2, 3, 4, 5].map((n) => sentence(n)),
    groups: { 'Tech > AI': [1, 2], 'Tech > Chips': [4], Sport: [3, 5] },
  };

  const level0 = buildTopicCards(data, 0).map((card) => [card.path, card.sentences]);
  assert.deepEqual(level0, [
    ['Tech', [1, 2]],
    ['Sport', [3]],
    ['Tech', [4]],
    ['Sport', [5]],
  ]);

  const level1 = buildTopicCards(data, 1);
  assert.deepEqual(
    level1.filter((card) => card.depth === 1).map((card) => [card.path, card.start, card.end]),
    [
      ['Tech > AI', 1, 2],
      ['Tech > Chips', 4, 4],
    ]
  );
  assert.equal(new Set(level1.map((card) => card.key)).size, level1.length);
  assert.equal(getMaxTopicLevel(data.groups), 1);
});

test('buildNavigationList keeps the deepest card of each branch in source order', () => {
  const data = {
    sentences: [1, 2, 3, 4].map((n) => sentence(n)),
    groups: { 'Tech > AI': [1], Tech: [2], Sport: [3, 4] },
  };

  const list = buildNavigationList(buildTopicCards(data, 1));
  assert.deepEqual(
    list.map((card) => card.path),
    ['Tech > AI', 'Sport']
  );
  assert.equal(findNavigationTarget(list, null, 'next').path, 'Tech > AI');
  assert.equal(findNavigationTarget(list, list[0], 'next').path, 'Sport');
  assert.equal(findNavigationTarget(list, list[1], 'next').path, 'Sport');
  assert.equal(findNavigationTarget(list, list[1], 'first').path, 'Tech > AI');
  assert.equal(findNavigationTarget([], null, 'next'), null);
});

test('layoutCards aligns with measurements, resolves overlaps and keeps children in parents', () => {
  const data = {
    sentences: [1, 2, 3].map((n) => sentence(n)),
    groups: { 'A > B': [1], 'A > C': [2], D: [3] },
  };
  const cards = buildTopicCards(data, 1);
  const tops = { 1: 0, 2: 10, 3: 400 };
  const placed = layoutCards(cards, (card) => ({
    top: tops[card.start],
    bottom: tops[card.end] + 30,
  }));
  const byPath = new Map(placed.map((card) => [card.path, card]));

  assert.equal(byPath.get('D').top, 400);
  const b = byPath.get('A > B');
  const c = byPath.get('A > C');
  assert.ok(c.top >= b.top + b.height || c.top - 10 <= 18, 'pushed by at most the max push');
  const parent = byPath.get('A');
  assert.ok(b.top >= parent.top && c.top + c.height <= parent.top + parent.height + 56);
});

test('layoutCards stacks cards without measurements', () => {
  const data = { sentences: [sentence(1), sentence(3)], groups: { A: [1], B: [3] } };
  const placed = layoutCards(buildTopicCards(data, 0), () => null);

  assert.equal(placed[0].top, 0);
  assert.ok(placed[1].top >= placed[0].top + placed[0].height);
});

test('zoom helpers widen cards on zoom-out and anchor the cursor', () => {
  assert.equal(getZoomCardWidth(1), 240);
  assert.equal(getZoomCardWidth(0.5), 480);
  assert.equal(getRailWidth(2, 240), 2 * 240 + 18 + 48);
  assert.deepEqual(
    cursorAnchoredTranslate({
      cursor: { x: 100, y: 100 },
      translate: { x: 0, y: 0 },
      scale: 1,
      nextScale: 2,
    }),
    { x: -100, y: -100 }
  );
});

test('buildSummaryRequest sends the topic path and non-empty sentence texts', () => {
  const sentences = byNumber([sentence(1), { ...sentence(2), text: ' ' }]);

  assert.deepEqual(buildSummaryRequest({ path: 'A > B', sentences: [1, 2] }, sentences), {
    topic: 'A > B',
    sentences: ['Sentence 1.'],
  });
});

test('fetchTopicSummary surfaces server errors', async () => {
  const failing = async () => ({ ok: false, json: async () => ({ error: 'Quota exceeded.' }) });
  await assert.rejects(fetchTopicSummary({ topic: 'A', sentences: ['x'] }, failing), /Quota/);
  await assert.rejects(fetchTopicSummary({ topic: 'A', sentences: [] }, failing), /no text/);
});

test('summary store caches results, limits concurrency and retries errors', async () => {
  let running = 0;
  let peak = 0;
  let calls = 0;
  const updates = [];
  const store = createSummaryStore({
    buildRequest: (card) => ({ topic: card.key, sentences: ['x'] }),
    onUpdate: (key, entry) => updates.push([key, entry.status]),
    concurrency: 2,
    fetchSummary: async ({ topic }) => {
      calls += 1;
      running += 1;
      peak = Math.max(peak, running);
      await new Promise((resolve) => setTimeout(resolve, 5));
      running -= 1;
      if (topic === 'bad') throw new Error('Nope.');
      return `summary ${topic}`;
    },
  });

  ['a', 'b', 'c', 'bad'].forEach((key) => store.request({ key }));
  store.request({ key: 'a' });
  await new Promise((resolve) => setTimeout(resolve, 40));

  assert.equal(peak, 2);
  assert.equal(calls, 4);
  assert.deepEqual(store.get('a'), { status: 'done', text: 'summary a' });
  assert.equal(store.get('bad').status, 'error');
  store.request({ key: 'bad' });
  assert.equal(store.get('bad').status, 'loading');
  assert.ok(updates.some(([key, status]) => key === 'c' && status === 'done'));
});

const PAGE = `
  <main id="post-canvas">
    <div id="post-canvas-area"><div id="post-canvas-viewport"><div id="post-canvas-stage" class="has-rail">
      <aside id="post-canvas-current-summary" hidden></aside>
      <div id="post-canvas-column"><div id="post-canvas-articles">
        <article><div>
          <span class="sentence-group" data-sentence="1">One.</span>
          <span class="sentence-group" data-sentence="2">Two.</span>
          <span class="sentence-group" data-sentence="3">Three.</span>
        </div></article>
      </div><div id="post-canvas-summaries" hidden></div></div>
      <aside><div id="post-canvas-rail-body"></div></aside>
    </div></div></div>
    <nav class="post-canvas__controls">
      <button data-action="return" hidden></button>
      <button data-action="next-topic"></button><button data-action="zoom-in"></button>
      <button data-action="summary-mode"></button><button data-action="rail"></button>
      <output id="post-canvas-zoom"></output><div id="post-canvas-levels"></div>
    </nav>
    <p id="post-canvas-status"></p>
  </main>
  <script id="post-canvas-data" type="application/json">${JSON.stringify({
    posts: [{ post_id: 'post-1', feed_title: 'Feed', url: '' }],
    sentences: [1, 2, 3].map((n) => sentence(n)),
    groups: { 'Tech > AI': [1, 2], Sport: [3] },
  })}</script>
`;

/** Run `body` with the canvas page loaded into JSDOM globals. */
async function withCanvasPage(fetchImpl, body) {
  const dom = new JSDOM(PAGE);
  const previous = {
    document: globalThis.document,
    window: globalThis.window,
    fetch: globalThis.fetch,
  };
  globalThis.document = dom.window.document;
  globalThis.window = dom.window;
  globalThis.fetch = fetchImpl;
  try {
    await import(`../post-canvas.js?smoke=${Date.now()}-${Math.random()}`);
    await body(dom.window.document);
  } finally {
    dom.window.close();
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete globalThis[key];
      else globalThis[key] = value;
    }
  }
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test('canvas page renders the rail, selects topics and shows their summary', async () => {
  const requests = [];
  const fetchImpl = async (url, options) => {
    requests.push(JSON.parse(options.body));
    return { ok: true, json: async () => ({ data: 'Short summary.' }) };
  };

  await withCanvasPage(fetchImpl, async (doc) => {
    const railCards = doc.querySelectorAll('#post-canvas-rail-body [data-card-key]');
    assert.equal(railCards.length, 3, 'two level-0 runs and one level-1 run');
    assert.deepEqual(
      [...doc.querySelectorAll('#post-canvas-levels [data-level]')].map((b) => b.textContent),
      ['L1', 'L2']
    );

    doc.querySelector('[data-action="next-topic"]').click();
    await tick();
    assert.deepEqual(requests, [{ topic: 'Tech > AI', sentences: ['Sentence 1.', 'Sentence 2.'] }]);
    assert.equal(doc.querySelectorAll('.sentence-group.is-selected').length, 2);
    const floating = doc.getElementById('post-canvas-current-summary');
    assert.equal(floating.hidden, false);
    assert.match(floating.textContent, /Short summary\./);
    assert.equal(doc.querySelector('[data-action="return"]').hidden, false);

    doc.dispatchEvent(
      new doc.defaultView.KeyboardEvent('keydown', { key: 'Escape', bubbles: true })
    );
    assert.equal(doc.querySelectorAll('.sentence-group.is-selected').length, 0);
    assert.equal(floating.hidden, true);
  });
});

test('canvas page switches levels, summary mode and zoom', async () => {
  const fetchImpl = async () => ({
    ok: false,
    json: async () => ({ error: 'Summary unavailable.' }),
  });

  await withCanvasPage(fetchImpl, async (doc) => {
    doc.querySelector('#post-canvas-levels [data-level="0"]').click();
    assert.equal(doc.querySelectorAll('#post-canvas-rail-body [data-card-key]').length, 2);

    doc.querySelector('[data-action="summary-mode"]').click();
    const summaries = doc.getElementById('post-canvas-summaries');
    assert.equal(summaries.hidden, false);
    assert.equal(doc.getElementById('post-canvas-articles').hidden, true);
    assert.equal(summaries.querySelectorAll('[data-card-key]').length, 2);

    summaries.querySelector('[data-card-action="summarize"]').click();
    await tick();
    assert.match(summaries.textContent, /Summary unavailable\./);

    summaries.querySelector('[data-card-action="source"]').click();
    assert.equal(summaries.hidden, true);
    assert.equal(doc.querySelectorAll('.sentence-group.is-selected').length, 2);

    const zoom = doc.getElementById('post-canvas-zoom');
    const before = zoom.textContent;
    doc.querySelector('[data-action="zoom-in"]').click();
    assert.notEqual(zoom.textContent, before);
    // Showing the source retries the failed summary; let it settle in-page.
    await tick();
  });
});
