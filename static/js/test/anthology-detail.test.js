import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildKeywordRegex,
  clusterOrder,
  defaultSelection,
  filterSnippets,
  formatDateRange,
  highlightText,
  keywordPattern,
  OTHER_THEME_ID,
  parseHash,
  renderClusterHead,
  renderClusterStats,
  renderHeader,
  renderSnippetCard,
  renderSnippetList,
  renderThemeOverview,
  renderTree,
  resolveSelection,
  scoreDots,
  selectionHash,
  sortSnippets,
  stepCluster,
  summarizeRead,
  themeForCluster,
  themesWithOrphans,
  unreadBadge,
  visibleSentences,
} from '../anthology-detail.js';
import {
  escapeHtml,
  formatPercent,
  isActive,
  renderStepper,
  scopeLabel,
  stepStates,
} from '../libs/anthology-common.js';
import { buildCreatePayload, needsPolling, renderCard, renderList } from '../anthologies-list.js';

function makeResult() {
  return {
    themes: [
      {
        id: 't0',
        label: 'Launch',
        keywords: ['launch'],
        size: 3,
        cluster_ids: ['c1', 'c2'],
        read: { unread: 2, total: 5 },
      },
      {
        id: 't1',
        label: 'Prices',
        keywords: [],
        size: 1,
        cluster_ids: ['c3'],
        read: { unread: 0, total: 2 },
      },
    ],
    clusters: {
      c1: {
        id: 'c1',
        label: 'Date',
        kind: 'event',
        score: 4,
        intruder_ok: true,
        keywords: ['date'],
        snippet_ids: ['s1', 's2'],
        start_snippet_id: 's2',
        feed_ids: ['f1'],
        read: { unread: 1, total: 3 },
      },
      c2: {
        id: 'c2',
        label: 'Rumors <b>',
        kind: 'opinion',
        score: 2,
        intruder_ok: false,
        keywords: [],
        snippet_ids: ['s3'],
        feed_ids: [],
        read: { unread: 1, total: 2 },
      },
      c3: {
        id: 'c3',
        label: 'Cut',
        kind: 'release',
        score: 5,
        intruder_ok: null,
        keywords: [],
        snippet_ids: ['s4'],
        feed_ids: [],
        read: { unread: 0, total: 2 },
      },
      c9: {
        id: 'c9',
        label: 'Orphan',
        kind: 'other',
        score: 1,
        keywords: [],
        snippet_ids: ['s5', 's6'],
        feed_ids: [],
      },
    },
    unsorted: ['s7'],
    unsorted_read: { unread: 1, total: 1 },
  };
}

function snippet(id, date, sentences, extra = {}) {
  return {
    id,
    post_id: `p-${id}`,
    title: `Title ${id}`,
    date,
    topic_path: 'A > B',
    sentences,
    read: sentences.length > 0 && sentences.every((s) => s.read),
    ...extra,
  };
}

const s1 = snippet('s1', 100, [
  { number: 0, text: 'First one', read: false },
  { number: 1, text: 'Second one', read: true },
]);
const s2 = snippet('s2', 300, [{ number: 0, text: 'Read', read: true }]);
const s3 = snippet('s3', null, [{ number: 4, text: 'Undated', read: false }]);

// ============================================================
// Common helpers
// ============================================================

test('escapeHtml escapes all special characters', () => {
  assert.equal(
    escapeHtml(`<a href="x">'&'</a>`),
    '&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;'
  );
  assert.equal(escapeHtml(null), '');
});

test('stepStates marks done / current / failed', () => {
  const states = stepStates('processing', 'merge').map((s) => s.state);
  assert.deepEqual(states, ['done', 'done', 'current', 'todo', 'todo', 'todo', 'todo']);
  assert.equal(stepStates('failed', 'label')[3].state, 'failed');
  assert.ok(stepStates('done', 'done').every((s) => s.state === 'done'));
  assert.ok(stepStates('pending', null).every((s) => s.state === 'todo'));
  assert.match(renderStepper('processing', 'units'), /anth-stepper__step--current/);
  assert.equal((renderStepper('pending', null).match(/<li/g) || []).length, 7);
});

test('format helpers', () => {
  assert.equal(formatPercent(0.756), '76%');
  assert.equal(formatPercent(null), '—');
  assert.equal(scopeLabel({ mode: 'posts', post_ids: ['a'] }), '1 post');
  assert.equal(scopeLabel({ mode: 'feeds', feed_ids: ['a', 'b'] }), '2 feeds');
  assert.equal(scopeLabel(null), 'All feeds');
  assert.equal(formatDateRange(0, 0), '');
  assert.equal(formatDateRange(86400, 86400), '1970-01-02');
  assert.equal(formatDateRange(86400, 86400 * 3), '1970-01-02 – 1970-01-04');
  assert.ok(isActive({ status: 'processing' }));
  assert.ok(!isActive({ status: 'done' }));
});

// ============================================================
// Selection / navigation
// ============================================================

test('parseHash and selectionHash round-trip', () => {
  assert.equal(parseHash('#c3'), 'c3');
  assert.equal(parseHash(''), '');
  assert.equal(parseHash('#a%20b'), 'a b');
  assert.equal(parseHash('#%E0%A4%A'), '%E0%A4%A');
  assert.equal(selectionHash({ kind: 'cluster', id: 'c3' }), '#c3');
  assert.equal(selectionHash(null), '');
});

test('resolveSelection recognises clusters, themes and unsorted', () => {
  const result = makeResult();
  assert.deepEqual(resolveSelection('c1', result), { kind: 'cluster', id: 'c1' });
  assert.deepEqual(resolveSelection('t1', result), { kind: 'theme', id: 't1' });
  assert.deepEqual(resolveSelection('unsorted', result), { kind: 'unsorted', id: 'unsorted' });
  assert.deepEqual(resolveSelection(OTHER_THEME_ID, result), { kind: 'theme', id: OTHER_THEME_ID });
  assert.equal(resolveSelection('nope', result), null);
  assert.equal(resolveSelection('c1', null), null);
  assert.equal(resolveSelection('unsorted', { ...result, unsorted: [] }), null);
});

test('themesWithOrphans adds a virtual theme for unclaimed clusters', () => {
  const themes = themesWithOrphans(makeResult());
  assert.equal(themes.length, 3);
  assert.deepEqual(themes[2].cluster_ids, ['c9']);
  assert.equal(themes[2].size, 2);
  assert.ok(themes[2].virtual);
  assert.equal(themesWithOrphans(null).length, 0);
});

test('defaultSelection prefers first theme, then unsorted', () => {
  assert.deepEqual(defaultSelection(makeResult()), { kind: 'theme', id: 't0' });
  assert.deepEqual(defaultSelection({ themes: [], clusters: {}, unsorted: ['x'] }), {
    kind: 'unsorted',
    id: 'unsorted',
  });
  assert.equal(defaultSelection({ themes: [], clusters: {}, unsorted: [] }), null);
});

test('clusterOrder / stepCluster / themeForCluster', () => {
  const result = makeResult();
  const order = clusterOrder(result);
  assert.deepEqual(order, ['c1', 'c2', 'c3', 'c9']);
  assert.equal(stepCluster(order, 'c1', 1), 'c2');
  assert.equal(stepCluster(order, 'c1', -1), 'c1');
  assert.equal(stepCluster(order, 'c9', 1), 'c9');
  assert.equal(stepCluster(order, null, 1), 'c1');
  assert.equal(stepCluster(order, null, -1), 'c9');
  assert.equal(stepCluster([], 'c1', 1), null);
  assert.equal(themeForCluster(result, 'c3'), 't1');
  assert.equal(themeForCluster(result, 'c9'), OTHER_THEME_ID);
  assert.equal(themeForCluster(result, 'zz'), null);
});

// ============================================================
// Snippet operations
// ============================================================

test('summarizeRead rolls sentences up', () => {
  assert.deepEqual(summarizeRead([s1, s2, s3]), { unread: 2, total: 4 });
  assert.deepEqual(summarizeRead(null), { unread: 0, total: 0 });
});

test('filterSnippets keeps unread only when asked', () => {
  assert.deepEqual(
    filterSnippets([s1, s2, s3], true).map((s) => s.id),
    ['s1', 's3']
  );
  assert.equal(filterSnippets([s1, s2], false).length, 2);
});

test('sortSnippets supports relevance, newest, oldest', () => {
  const list = [s1, s2, s3];
  assert.deepEqual(
    sortSnippets(list, 'relevance', 's2').map((s) => s.id),
    ['s2', 's1', 's3']
  );
  assert.deepEqual(
    sortSnippets(list, 'relevance', null).map((s) => s.id),
    ['s1', 's2', 's3']
  );
  assert.deepEqual(
    sortSnippets(list, 'newest').map((s) => s.id),
    ['s2', 's1', 's3']
  );
  assert.deepEqual(
    sortSnippets(list, 'oldest').map((s) => s.id),
    ['s1', 's2', 's3']
  );
  assert.deepEqual(
    list.map((s) => s.id),
    ['s1', 's2', 's3'],
    'input not mutated'
  );
});

test('visibleSentences trims non-start snippets in skim mode', () => {
  assert.equal(visibleSentences(s1, { skim: false }).sentences.length, 2);
  assert.deepEqual(visibleSentences(s1, { skim: true, isStart: false }), {
    sentences: [s1.sentences[0]],
    truncated: true,
  });
  assert.equal(visibleSentences(s1, { skim: true, isStart: true }).truncated, false);
  assert.equal(visibleSentences(s1, { skim: true, expanded: true }).sentences.length, 2);
  assert.equal(visibleSentences(s2, { skim: true }).truncated, false);
});

// ============================================================
// Highlighting
// ============================================================

test('buildKeywordRegex matches whole words and stems', () => {
  const re = buildKeywordRegex(['sony', 'ps', 'price cut']);
  const marks = (text) => highlightText(text, re).match(/<mark>[^<]*<\/mark>/g) || [];
  assert.deepEqual(marks('Sony and Sonys: PS vs PSN'), [
    '<mark>Sony</mark>',
    '<mark>Sonys</mark>',
    '<mark>PS</mark>',
  ]);
  assert.deepEqual(marks('a price  cut today'), ['<mark>price  cut</mark>']);
  assert.equal(buildKeywordRegex([]), null);
  assert.equal(buildKeywordRegex(['', '  ']), null);
});

test('buildKeywordRegex handles non-latin words and regex characters', () => {
  const re = buildKeywordRegex(['приставка', 'c++']);
  assert.equal(
    highlightText('Новая приставки и c++', re),
    'Новая <mark>приставки</mark> и <mark>c++</mark>'
  );
});

test('keywordPattern trims endings of long single words only', () => {
  assert.equal(keywordPattern('ps'), 'ps');
  assert.equal(keywordPattern('sony'), 'sony[\\p{L}\\p{N}]*');
  assert.equal(keywordPattern('launch'), 'launc[\\p{L}\\p{N}]*');
  assert.equal(keywordPattern('приставка'), 'пристав[\\p{L}\\p{N}]*');
  assert.equal(keywordPattern('price cut'), 'price\\s+cut[\\p{L}\\p{N}]*');
});

test('highlightText escapes text and matches', () => {
  const re = buildKeywordRegex(['tag']);
  assert.equal(
    highlightText('<b>tag</b> & tag', re),
    '&lt;b&gt;<mark>tag</mark>&lt;/b&gt; &amp; <mark>tag</mark>'
  );
  assert.equal(highlightText('<i>', null), '&lt;i&gt;');
});

// ============================================================
// Rendering
// ============================================================

test('scoreDots and unreadBadge', () => {
  assert.match(scoreDots(3), /●●●<span class="anth-dots__off">○○<\/span>/);
  assert.match(scoreDots(9), /Quality 5\/5/);
  assert.match(scoreDots(undefined), /Quality 0\/5/);
  assert.equal(unreadBadge({ unread: 0, total: 0 }), '');
  assert.match(unreadBadge({ unread: 0, total: 3 }), /anth-count--done/);
  assert.match(unreadBadge({ unread: 2, total: 3 }), />2</);
});

test('renderTree shows themes, expanded clusters, warnings and unsorted', () => {
  const result = makeResult();
  const html = renderTree(result, { kind: 'cluster', id: 'c2' }, new Set(['t0']));
  assert.match(html, /Launch/);
  assert.match(html, /Rumors &lt;b&gt;/);
  assert.doesNotMatch(html, /Rumors <b>/);
  assert.match(html, /⚠/);
  assert.match(html, /anth-tree__cluster is-active" data-action="select" data-id="c2"/);
  assert.doesNotMatch(html, /data-id="c3"/, 'collapsed theme hides clusters');
  assert.match(html, /Other clusters/);
  assert.match(html, /data-id="unsorted"/);
  assert.match(renderTree(null, null, new Set()), /appear when the build finishes/);
});

test('renderThemeOverview lists cluster cards and theme action', () => {
  const result = makeResult();
  const html = renderThemeOverview(result.themes[0], result);
  assert.equal((html.match(/anth-cluster-card"/g) || []).length, 2);
  assert.match(html, /data-kind="theme" data-id="t0" data-readed="true"/);
  const virtual = renderThemeOverview(themesWithOrphans(result)[2], result);
  assert.doesNotMatch(virtual, /data-action="mark"/);
});

test('renderClusterHead covers clusters and unsorted', () => {
  const cluster = makeResult().clusters.c1;
  const html = renderClusterHead(cluster, { unread: 0, total: 3 }, 1);
  assert.match(html, /1 feed</);
  assert.match(html, /Mark cluster unread/);
  assert.match(html, /data-readed="false"/);
  const unsorted = renderClusterHead(null, { unread: 1, total: 1 }, 0);
  assert.match(unsorted, /Unsorted/);
  assert.match(unsorted, /data-kind="unsorted"/);
});

test('renderSnippetCard marks start, read sentences and escapes', () => {
  const evil = snippet('s9', 0, [{ number: 0, text: '<img src=x onerror=1> tag', read: true }], {
    title: '<script>',
  });
  const html = renderSnippetCard(evil, { isStart: true, re: buildKeywordRegex(['tag']) });
  assert.match(html, /Start here/);
  assert.match(html, /anth-sentence--read/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /&lt;img src=x onerror=1&gt; <mark>tag<\/mark>/);
  assert.match(html, /href="\/post-grouped\/p-s9"/);
  assert.match(html, /Mark unread/);
  assert.match(html, /A › B/);
  const preview = renderSnippetCard(snippet('s8', 0, [], { preview: 'Fallback' }), {});
  assert.match(preview, /Fallback/);
  const skim = renderSnippetCard(s1, { skim: true });
  assert.match(skim, /data-action="expand" data-id="s1"/);
});

test('renderSnippetList orders, filters and reports empties', () => {
  const data = { cluster: { start_snippet_id: 's2', keywords: [] }, snippets: [s1, s2, s3] };
  const view = { unreadOnly: false, sort: 'relevance', skim: false };
  const html = renderSnippetList(data, view, new Set());
  assert.ok(html.indexOf('data-snippet-id="s2"') < html.indexOf('data-snippet-id="s1"'));
  const unread = renderSnippetList(data, { ...view, unreadOnly: true }, new Set());
  assert.doesNotMatch(unread, /data-snippet-id="s2"/);
  const empty = renderSnippetList(
    { cluster: null, snippets: [s2] },
    { ...view, unreadOnly: true },
    new Set()
  );
  assert.match(empty, /Everything here is read/);
});

test('renderClusterStats and renderHeader', () => {
  const cluster = { ...makeResult().clusters.c2, cohesion: 0.4567, feed_ids: ['f1', 'f2'] };
  const stats = renderClusterStats(cluster, { f1: 'Feed <One>' });
  assert.match(stats, /0\.46/);
  assert.match(stats, /failed/);
  assert.match(stats, /Feed &lt;One&gt;/);
  assert.match(stats, /<li>f2<\/li>/);

  const processing = renderHeader({
    seed_value: '<x>',
    status: 'processing',
    stage: 'label',
    scope: { mode: 'all' },
  });
  assert.match(processing, /&lt;x&gt;/);
  assert.match(processing, /anth-stepper/);
  const stuck = renderHeader({ seed_value: 'x', status: 'processing', stuck: true });
  assert.match(stuck, /No progress for an hour/);
  assert.match(stuck, /data-action="retry"/);
  assert.doesNotMatch(processing, /data-action="retry"/);
  const failed = renderHeader({ seed_value: 'x', status: 'failed', error: 'boom', result: null });
  assert.match(failed, /boom/);
  assert.match(failed, /data-action="retry"/);
  const done = renderHeader({
    seed_value: 'x',
    status: 'done',
    stale: true,
    result: { metrics: { snippets_total: 7, coverage: 0.5, llm_calls: 2, llm_cached: 1 } },
  });
  assert.match(done, /stale/);
  assert.match(done, /50%/);
  assert.match(done, /2 \(\+1 cached\)/);
});

// ============================================================
// List page
// ============================================================

test('buildCreatePayload builds scope from feed', () => {
  assert.deepEqual(buildCreatePayload({ seed_type: 'tag', seed_value: ' ps5 ', feed_id: 'f1' }), {
    seed_type: 'tag',
    seed_value: 'ps5',
    scope: { mode: 'feeds', feed_ids: ['f1'] },
  });
  assert.deepEqual(buildCreatePayload({ seed_value: 'x' }).scope, { mode: 'all' });
});

test('needsPolling and list rendering', () => {
  assert.ok(needsPolling([{ status: 'done' }, { status: 'pending' }]));
  assert.ok(!needsPolling([{ status: 'done' }]));
  assert.ok(!needsPolling(null));
  assert.match(renderList([]), /No anthologies yet/);

  const processing = renderCard({
    id: 'a1',
    seed_value: '<t>',
    status: 'processing',
    stage: 'merge',
    scope: { mode: 'all' },
  });
  assert.match(processing, /&lt;t&gt;/);
  assert.match(processing, /anth-stepper/);
  assert.doesNotMatch(processing, /data-action="retry"/);

  const stuck = renderCard({ id: 'stuck', seed_value: 't', status: 'processing', stuck: true });
  assert.match(stuck, /No progress for an hour/);
  assert.match(stuck, /data-action="retry"/);

  const done = renderCard({
    id: 'a2',
    seed_value: 't',
    status: 'done',
    stale: true,
    has_result: true,
    themes_count: 3,
    metrics: { snippets_total: 9, coverage: 0.5 },
  });
  assert.match(done, /Rebuild/);
  assert.match(done, /stale/);
  assert.match(done, /<dd>9<\/dd>/);

  const failed = renderCard({ id: 'a3', seed_value: 't', status: 'failed', error: 'oops' });
  assert.match(failed, /oops/);
  assert.match(failed, />Retry</);
});
