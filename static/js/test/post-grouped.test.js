import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import PostGroupedPage from '../components/post-grouped.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'post-grouped.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// === Constructor ===
// ============================================================

test('constructor initializes topicState as empty object', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.topicState, {});
});

test('constructor initializes topicToSentences as empty object', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.topicToSentences, {});
});

test('constructor initializes topicElements as empty Map', () => {
  const page = new PostGroupedPage();
  assert.ok(page.topicElements instanceof Map);
  assert.equal(page.topicElements.size, 0);
});

test('constructor initializes isContentReady to false', () => {
  const page = new PostGroupedPage();
  assert.equal(page.isContentReady, false);
});

test('constructor initializes chartInitialized to false', () => {
  const page = new PostGroupedPage();
  assert.equal(page.chartInitialized, false);
});

test('constructor initializes topicFlowChart to null', () => {
  const page = new PostGroupedPage();
  assert.equal(page.topicFlowChart, null);
});

test('constructor initializes riverCharts as empty object', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.riverCharts, {});
});

test('constructor initializes sentencesByGlobalNumber as empty Map', () => {
  const page = new PostGroupedPage();
  assert.ok(page.sentencesByGlobalNumber instanceof Map);
  assert.equal(page.sentencesByGlobalNumber.size, 0);
});

// ============================================================
// === Source: class structure ===
// ============================================================

test('source exports PostGroupedPage as default class', () => {
  assert.ok(/export\s+default\s+class\s+PostGroupedPage/.test(source),
    'should export default class PostGroupedPage');
});

test('source imports TopicFlow', () => {
  assert.ok(/import\s+TopicFlow\s+from\s+['"]\.\/topic-flow\.js['"]/.test(source),
    'should import TopicFlow from topic-flow.js');
});

test('source imports TopicsRiverChart', () => {
  assert.ok(/import\s+TopicsRiverChart\s+from\s+['"]\.\/topics-river-chart\.js['"]/.test(source),
    'should import TopicsRiverChart from topics-river-chart.js');
});

// ============================================================
// === Source: init method ===
// ============================================================

test('init calls stripGlobalStyles', () => {
  assert.ok(/this\.stripGlobalStyles\(\)/.test(source),
    'init should call stripGlobalStyles');
});

test('init calls setupPostSections', () => {
  assert.ok(/this\.setupPostSections\(\)/.test(source),
    'init should call setupPostSections');
});

test('init calls indexSentences', () => {
  assert.ok(/this\.indexSentences\(\)/.test(source),
    'init should call indexSentences');
});

test('init calls addPostHoverEffects', () => {
  assert.ok(/this\.addPostHoverEffects\(\)/.test(source),
    'init should call addPostHoverEffects');
});

test('init sets isContentReady to true', () => {
  assert.ok(/this\.isContentReady\s*=\s*true/.test(source),
    'should set isContentReady to true');
});

test('init calls buildTopicsList', () => {
  assert.ok(/this\.buildTopicsList\(\)/.test(source),
    'init should call buildTopicsList');
});

test('init calls buildPostsList', () => {
  assert.ok(/this\.buildPostsList\(\)/.test(source),
    'init should call buildPostsList');
});

test('init calls attachSentenceGroupHandlers', () => {
  assert.ok(/this\.attachSentenceGroupHandlers\(\)/.test(source),
    'init should call attachSentenceGroupHandlers');
});

test('init calls attachReadButtonHandlers', () => {
  assert.ok(/this\.attachReadButtonHandlers\(\)/.test(source),
    'init should call attachReadButtonHandlers');
});

test('init calls initTabs', () => {
  assert.ok(/this\.initTabs\(\)/.test(source),
    'init should call initTabs');
});

test('init calls initZoomControls', () => {
  assert.ok(/this\.initZoomControls\(\)/.test(source),
    'init should call initZoomControls');
});

test('init calls handleHighlightSentenceFromUrl', () => {
  assert.ok(/this\.handleHighlightSentenceFromUrl\(\)/.test(source),
    'init should call handleHighlightSentenceFromUrl');
});

test('init calls setInitialReadStatus', () => {
  assert.ok(/this\.setInitialReadStatus\(\)/.test(source),
    'init should call setInitialReadStatus');
});

test('init calls bindGlobalEvents', () => {
  assert.ok(/this\.bindGlobalEvents\(\)/.test(source),
    'init should call bindGlobalEvents');
});

// ============================================================
// === splitTopicPath ===
// ============================================================

test('splitTopicPath returns empty array for null', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath(null), []);
});

test('splitTopicPath returns empty array for undefined', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath(undefined), []);
});

test('splitTopicPath returns empty array for empty string', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath(''), []);
});

test('splitTopicPath returns empty array for non-string input', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath(123), []);
});

test('splitTopicPath returns empty array for boolean input', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath(true), []);
});

test('splitTopicPath splits single-level topic', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath('Technology'), ['Technology']);
});

test('splitTopicPath splits multi-level topic with >', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath('Science > Physics'), ['Science', 'Physics']);
});

test('splitTopicPath trims whitespace around parts', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath('Science  >  Physics  >  Quantum'), ['Science', 'Physics', 'Quantum']);
});

test('splitTopicPath filters empty parts from consecutive >', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath('A>>B'), ['A', 'B']);
});

test('splitTopicPath handles leading/trailing >', () => {
  const page = new PostGroupedPage();
  assert.deepEqual(page.splitTopicPath('>A>B>'), ['A', 'B']);
});

// ============================================================
// === colorFromString ===
// ============================================================

test('colorFromString returns default #4a6baf for null', () => {
  const page = new PostGroupedPage();
  assert.equal(page.colorFromString(null), '#4a6baf');
});

test('colorFromString returns default #4a6baf for empty string', () => {
  const page = new PostGroupedPage();
  assert.equal(page.colorFromString(''), '#4a6baf');
});

test('colorFromString returns default #4a6baf for undefined', () => {
  const page = new PostGroupedPage();
  assert.equal(page.colorFromString(undefined), '#4a6baf');
});

test('colorFromString returns deterministic color for same input', () => {
  const page = new PostGroupedPage();
  const color1 = page.colorFromString('Technology');
  const color2 = page.colorFromString('Technology');
  assert.equal(color1, color2);
});

test('colorFromString returns hsl format string', () => {
  const page = new PostGroupedPage();
  const color = page.colorFromString('test');
  assert.ok(/^hsl\(\d+, 60%, 60%\)$/.test(color),
    `expected hsl format, got: ${color}`);
});

test('colorFromString produces different colors for different inputs', () => {
  const page = new PostGroupedPage();
  const color1 = page.colorFromString('Technology');
  const color2 = page.colorFromString('Science');
  assert.notEqual(color1, color2);
});

test('colorFromString hue is within valid range 0-359', () => {
  const page = new PostGroupedPage();
  const color = page.colorFromString('some long string with many characters');
  const hueMatch = color.match(/^hsl\((\d+)/);
  assert.ok(hueMatch, 'should match hsl hue');
  const hue = parseInt(hueMatch[1], 10);
  assert.ok(hue >= 0 && hue < 360, `hue ${hue} should be in 0-359`);
});

// ============================================================
// === getTopicColor ===
// ============================================================

test('getTopicColor uses window.group_colors when available', () => {
  const page = new PostGroupedPage();
  globalThis.window = { group_colors: { 'Science': '#ff0000' } };
  assert.equal(page.getTopicColor('Science'), '#ff0000');
});

test('getTopicColor falls back to colorFromString when group_colors missing', () => {
  const page = new PostGroupedPage();
  globalThis.window = { group_colors: {} };
  const color = page.getTopicColor('Unknown');
  assert.ok(color.startsWith('hsl('), 'should fall back to colorFromString');
});

test('getTopicColor falls back to colorFromString when group_colors is undefined', () => {
  const page = new PostGroupedPage();
  globalThis.window = {};
  const color = page.getTopicColor('Unknown');
  assert.ok(color.startsWith('hsl('), 'should fall back to colorFromString');
});

// ============================================================
// === getTopicLinks ===
// ============================================================

test('getTopicLinks returns 3 links', () => {
  const page = new PostGroupedPage();
  globalThis.window = { post_id: 42 };
  const links = page.getTopicLinks('Science');
  assert.equal(links.length, 3);
});

test('getTopicLinks includes Sentences, Compare, Snippets', () => {
  const page = new PostGroupedPage();
  globalThis.window = { post_id: 42 };
  const links = page.getTopicLinks('Science');
  const texts = links.map((l) => l.text);
  assert.deepEqual(texts, ['Sentences', 'Compare', 'Snippets']);
});

test('getTopicLinks encodes topic path in href', () => {
  const page = new PostGroupedPage();
  globalThis.window = { post_id: 42 };
  const links = page.getTopicLinks('Science > Physics');
  assert.ok(links[0].href.includes('topic=Science'),
    'href should contain topic parameter');
});

test('getTopicLinks uses correct CSS class names', () => {
  const page = new PostGroupedPage();
  globalThis.window = { post_id: 42 };
  const links = page.getTopicLinks('Science');
  const classNames = links.map((l) => l.className);
  assert.ok(classNames[0].includes('topic-link-grouped'));
  assert.ok(classNames[1].includes('topic-link-compare'));
  assert.ok(classNames[2].includes('topic-link-snippets'));
});

test('getTopicLinks uses window.post_id in hrefs', () => {
  const page = new PostGroupedPage();
  globalThis.window = { post_id: 99 };
  const links = page.getTopicLinks('Test');
  assert.ok(links[0].href.includes('/post-grouped/99?topic='));
  assert.ok(links[1].href.includes('/post-compare/99?topic='));
  assert.ok(links[2].href.includes('/post-grouped-snippets/99?topic='));
});

// ============================================================
// === handleTopicSelection ===
// ============================================================

test('handleTopicSelection calls setActiveTopic', () => {
  const page = new PostGroupedPage();
  page.topicState = { 'Science': { index: 5 } };
  let setActiveCalled = false;
  page.setActiveTopic = () => { setActiveCalled = true; };
  page.handleTopicSelection('Science');
  assert.equal(setActiveCalled, true);
});

test('handleTopicSelection resets index to 0', () => {
  const page = new PostGroupedPage();
  page.topicState = { 'Science': { index: 5 } };
  page.setActiveTopic = () => {};
  page.handleTopicSelection('Science');
  assert.equal(page.topicState['Science'].index, 0);
});

test('handleTopicSelection does nothing if topicState has no entry', () => {
  const page = new PostGroupedPage();
  page.topicState = {};
  page.setActiveTopic = () => {};
  page.handleTopicSelection('Unknown');
  // should not throw
  assert.ok(true);
});

// ============================================================
// === setActiveTopic (source inspection) ===
// ============================================================

test('setActiveTopic removes active class from .topic-tree-node.active', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.topic-tree-node\.active['"]/.test(source),
    'should query .topic-tree-node.active');
  assert.ok(/classList\.remove\s*\(\s*['"]active['"]/.test(source),
    'should remove active class');
});

test('setActiveTopic uses topicElements Map to get element', () => {
  assert.ok(/this\.topicElements\.get\s*\(\s*topicPath/.test(source),
    'should use topicElements.get(topicPath)');
});

test('setActiveTopic adds active class to topicElement', () => {
  assert.ok(/topicElement\.classList\.add\s*\(\s*['"]active['"]/.test(source),
    'should add active class');
});

// ============================================================
// === buildTopicsTree ===
// ============================================================

test('buildTopicsTree returns empty array when window.groups is empty', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: {} };
  const tree = page.buildTopicsTree();
  assert.deepEqual(tree, []);
});

test('buildTopicsTree returns empty array when window.groups is undefined', () => {
  const page = new PostGroupedPage();
  globalThis.window = {};
  const tree = page.buildTopicsTree();
  assert.deepEqual(tree, []);
});

test('buildTopicsTree creates root nodes for flat topics', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: { Technology: [1, 2, 3] } };
  const tree = page.buildTopicsTree();
  assert.equal(tree.length, 1);
  assert.equal(tree[0].name, 'Technology');
  assert.equal(tree[0].path, 'Technology');
});

test('buildTopicsTree creates nested nodes for hierarchical topics', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: { 'Science > Physics': [1, 2] } };
  const tree = page.buildTopicsTree();
  assert.equal(tree.length, 1);
  assert.equal(tree[0].name, 'Science');
  assert.equal(tree[0].children.length, 1);
  assert.equal(tree[0].children[0].name, 'Physics');
});

test('buildTopicsTree aggregates sentence numbers into sentenceSet', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: { Technology: [1, 2, 3] } };
  const tree = page.buildTopicsTree();
  assert.deepEqual(Array.from(tree[0].sentenceSet), [1, 2, 3]);
});

test('buildTopicsTree merges sentences from multiple groups into shared parent', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: {
    'Science > Physics': [1, 2],
    'Science > Chemistry': [3, 4],
  } };
  const tree = page.buildTopicsTree();
  assert.equal(tree.length, 1);
  assert.equal(tree[0].name, 'Science');
  // Science parent should not have its own sentenceSet from the code logic
  // but children should have their own sets
  const physics = tree[0].children.find((c) => c.name === 'Physics');
  const chemistry = tree[0].children.find((c) => c.name === 'Chemistry');
  assert.ok(physics, 'should have Physics child');
  assert.ok(chemistry, 'should have Chemistry child');
  assert.deepEqual(Array.from(physics.sentenceSet), [1, 2]);
  assert.deepEqual(Array.from(chemistry.sentenceSet), [3, 4]);
});

test('buildTopicsTree sorts nodes by sentenceSet size descending', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: {
    Small: [1],
    Big: [1, 2, 3, 4, 5],
    Medium: [1, 2, 3],
  } };
  const tree = page.buildTopicsTree();
  assert.equal(tree[0].name, 'Big');
  assert.equal(tree[1].name, 'Medium');
  assert.equal(tree[2].name, 'Small');
});

test('buildTopicsTree sorts nodes alphabetically when sentenceSet size is equal', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: {
    Beta: [1],
    Alpha: [2],
  } };
  const tree = page.buildTopicsTree();
  assert.equal(tree[0].name, 'Alpha');
  assert.equal(tree[1].name, 'Beta');
});

test('buildTopicsTree filters non-finite sentence numbers', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: { Tech: [1, 'bad', 2, NaN, 3] } };
  const tree = page.buildTopicsTree();
  assert.deepEqual(Array.from(tree[0].sentenceSet), [1, 2, 3]);
});

test('buildTopicsTree skips groups with invalid topic paths', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: {
    '': [1, 2],
    Valid: [3, 4],
  } };
  const tree = page.buildTopicsTree();
  assert.equal(tree.length, 1);
  assert.equal(tree[0].name, 'Valid');
});

test('buildTopicsTree assigns color via getTopicColor', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: { Technology: [1] } };
  const tree = page.buildTopicsTree();
  assert.ok(tree[0].color.startsWith('hsl(') || tree[0].color.startsWith('#'));
});

// ============================================================
// === buildTopicsList ===
// ============================================================

test('buildTopicsList returns early when topics_list element is missing', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: { Tech: [1] } };
  globalThis.document = { getElementById: () => null };
  // Should return early without throwing
  page.buildTopicsList();
  assert.ok(true); // should not throw
});

test('buildTopicsList resets topicState, topicToSentences, topicElements', () => {
  const page = new PostGroupedPage();
  page.topicState = { old: true };
  page.topicToSentences = { old: true };
  page.topicElements = new Map([['old', {}]]);
  globalThis.window = { groups: {} };
  globalThis.document = {
    getElementById(id) {
      if (id === 'topics_list') return { innerHTML: '' };
      return null;
    },
  };
  page.buildTopicsList();
  assert.deepEqual(page.topicState, {});
  assert.deepEqual(page.topicToSentences, {});
  assert.ok(page.topicElements instanceof Map);
  assert.equal(page.topicElements.size, 0);
});

test('buildTopicsList shows "No topics available" when groups is empty', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: {} };
  let capturedHTML = '';
  globalThis.document = {
    getElementById(id) {
      if (id === 'topics_list') {
        return {
          set innerHTML(val) { capturedHTML = val; },
        };
      }
      return null;
    },
  };
  page.buildTopicsList();
  assert.ok(capturedHTML.includes('No topics available'));
});

test('buildTopicsList calls buildTopicsTree and renderTopicNode when groups exist', () => {
  const page = new PostGroupedPage();
  globalThis.window = { groups: { Tech: [1, 2] } };
  let renderCallCount = 0;
  page.renderTopicNode = () => { renderCallCount += 1; };
  globalThis.document = {
    getElementById(id) {
      if (id === 'topics_list') return { appendChild: () => {} };
      return null;
    },
  };
  page.buildTopicsList();
  assert.equal(renderCallCount, 1);
});

// ============================================================
// === isTopicFullyRead ===
// ============================================================

test('isTopicFullyRead returns false for unknown topic', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [1, 2] };
  page.sentencesByGlobalNumber = new Map([[1, { read: true }], [2, { read: true }]]);
  assert.equal(page.isTopicFullyRead('Unknown'), false);
});

test('isTopicFullyRead returns false when any sentence is unread', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [1, 2, 3] };
  page.sentencesByGlobalNumber = new Map([
    [1, { read: true }],
    [2, { read: false }],
    [3, { read: true }],
  ]);
  assert.equal(page.isTopicFullyRead('Science'), false);
});

test('isTopicFullyRead returns true when all sentences are read', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [1, 2, 3] };
  page.sentencesByGlobalNumber = new Map([
    [1, { read: true }],
    [2, { read: true }],
    [3, { read: true }],
  ]);
  assert.equal(page.isTopicFullyRead('Science'), true);
});

test('isTopicFullyRead returns false when topic has no sentences', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [] };
  assert.equal(page.isTopicFullyRead('Science'), false);
});

test('isTopicFullyRead skips sentences not in sentencesByGlobalNumber', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [1, 99, 2] };
  page.sentencesByGlobalNumber = new Map([
    [1, { read: true }],
    [2, { read: true }],
  ]);
  // 99 is missing from sentencesByGlobalNumber, so it's skipped
  // 1 and 2 are both read => true
  assert.equal(page.isTopicFullyRead('Science'), true);
});

test('isTopicFullyRead returns false when all missing sentences are skipped but none remain', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [99, 100] };
  page.sentencesByGlobalNumber = new Map();
  assert.equal(page.isTopicFullyRead('Science'), false);
});

// ============================================================
// === getSelectionsForTopic ===
// ============================================================

test('getSelectionsForTopic returns empty array for unknown topic', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = {};
  page.sentencesByGlobalNumber = new Map();
  const result = page.getSelectionsForTopic('Unknown');
  assert.deepEqual(result, []);
});

test('getSelectionsForTopic groups sentences by post_id', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [1, 2, 3] };
  page.sentencesByGlobalNumber = new Map([
    [1, { postId: 'p1', postSentenceNumber: 10 }],
    [2, { postId: 'p1', postSentenceNumber: 20 }],
    [3, { postId: 'p2', postSentenceNumber: 5 }],
  ]);
  const result = page.getSelectionsForTopic('Science');
  assert.equal(result.length, 2);
  const p1 = result.find((r) => r.post_id === 'p1');
  const p2 = result.find((r) => r.post_id === 'p2');
  assert.ok(p1, 'should have p1');
  assert.ok(p2, 'should have p2');
  assert.deepEqual(p1.sentence_indices, [10, 20]);
  assert.deepEqual(p2.sentence_indices, [5]);
});

test('getSelectionsForTopic sorts sentence_indices ascending', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [1, 2] };
  page.sentencesByGlobalNumber = new Map([
    [1, { postId: 'p1', postSentenceNumber: 30 }],
    [2, { postId: 'p1', postSentenceNumber: 10 }],
  ]);
  const result = page.getSelectionsForTopic('Science');
  assert.deepEqual(result[0].sentence_indices, [10, 30]);
});

test('getSelectionsForTopic skips sentences with missing postId', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [1, 2] };
  page.sentencesByGlobalNumber = new Map([
    [1, { postId: null, postSentenceNumber: 10 }],
    [2, { postId: 'p1', postSentenceNumber: 20 }],
  ]);
  const result = page.getSelectionsForTopic('Science');
  assert.equal(result.length, 1);
  assert.equal(result[0].post_id, 'p1');
});

test('getSelectionsForTopic skips sentences with non-finite postSentenceNumber', () => {
  const page = new PostGroupedPage();
  page.topicToSentences = { Science: [1, 2] };
  page.sentencesByGlobalNumber = new Map([
    [1, { postId: 'p1', postSentenceNumber: NaN }],
    [2, { postId: 'p1', postSentenceNumber: 20 }],
  ]);
  const result = page.getSelectionsForTopic('Science');
  assert.equal(result.length, 1);
  assert.deepEqual(result[0].sentence_indices, [20]);
});

// ============================================================
// === moveTopicPointer ===
// ============================================================

test('moveTopicPointer does nothing when topicState has no entry', () => {
  const page = new PostGroupedPage();
  page.topicState = {};
  page.moveTopicPointer('Unknown', 1);
  assert.ok(true); // should not throw
});

test('moveTopicPointer increments index with positive delta', () => {
  const page = new PostGroupedPage();
  page.topicState = { Science: { sentences: [10, 20, 30], index: 0, color: '#fff' } };
  page.highlightSentences = () => {};
  globalThis.window = { has_grouped_data: true };
  page.moveTopicPointer('Science', 1);
  assert.equal(page.topicState.Science.index, 1);
});

test('moveTopicPointer decrements index with negative delta', () => {
  const page = new PostGroupedPage();
  page.topicState = { Science: { sentences: [10, 20, 30], index: 1, color: '#fff' } };
  page.highlightSentences = () => {};
  globalThis.window = { has_grouped_data: true };
  page.moveTopicPointer('Science', -1);
  assert.equal(page.topicState.Science.index, 0);
});

test('moveTopicPointer wraps index forward past end', () => {
  const page = new PostGroupedPage();
  page.topicState = { Science: { sentences: [10, 20, 30], index: 2, color: '#fff' } };
  page.highlightSentences = () => {};
  globalThis.window = { has_grouped_data: true };
  page.moveTopicPointer('Science', 1);
  assert.equal(page.topicState.Science.index, 0);
});

test('moveTopicPointer wraps index backward past start', () => {
  const page = new PostGroupedPage();
  page.topicState = { Science: { sentences: [10, 20, 30], index: 0, color: '#fff' } };
  page.highlightSentences = () => {};
  globalThis.window = { has_grouped_data: true };
  page.moveTopicPointer('Science', -1);
  assert.equal(page.topicState.Science.index, 2);
});

test('moveTopicPointer calls highlightSentences when has_grouped_data is true', () => {
  const page = new PostGroupedPage();
  let capturedArgs = null;
  page.topicState = { Science: { sentences: [10, 20, 30], index: 0, color: '#abc' } };
  page.highlightSentences = (sentences, color, index) => { capturedArgs = { sentences, color, index }; };
  globalThis.window = { has_grouped_data: true };
  page.moveTopicPointer('Science', 1);
  assert.deepEqual(capturedArgs.sentences, [10, 20, 30]);
  assert.equal(capturedArgs.color, '#abc');
  assert.equal(capturedArgs.index, 1);
});

test('moveTopicPointer calls highlightPosts when has_grouped_data is false', () => {
  const page = new PostGroupedPage();
  let capturedArgs = null;
  page.topicState = { Science: { sentences: [10, 20, 30], index: 0, color: '#abc' } };
  page.highlightPosts = (sentenceIndices, color) => { capturedArgs = { sentenceIndices, color }; };
  globalThis.window = { has_grouped_data: false, groups: {} };
  page.moveTopicPointer('Science', 1);
  assert.deepEqual(capturedArgs.sentenceIndices, [10, 20, 30]);
  assert.equal(capturedArgs.color, '#abc');
});

test('moveTopicPointer returns early when sentences array is empty and no window.groups fallback', () => {
  const page = new PostGroupedPage();
  page.topicState = { Science: { sentences: [], index: 0, color: '#abc' } };
  let highlightPostsCalled = false;
  let highlightSentencesCalled = false;
  page.highlightPosts = () => { highlightPostsCalled = true; };
  page.highlightSentences = () => { highlightSentencesCalled = true; };
  globalThis.window = { has_grouped_data: false, groups: {} };
  page.moveTopicPointer('Science', 1);
  assert.equal(highlightPostsCalled, false);
  assert.equal(highlightSentencesCalled, false);
});

// ============================================================
// === updateTopicReadButton ===
// ============================================================

test('updateTopicReadButton sets "Mark Unread" when isFullyRead is true', () => {
  const page = new PostGroupedPage();
  const button = { textContent: '', title: '', dataset: {}, classList: { toggle: () => {} } };
  page.updateTopicReadButton(button, true);
  assert.equal(button.textContent, 'Mark Unread');
});

test('updateTopicReadButton sets "Mark Read" when isFullyRead is false', () => {
  const page = new PostGroupedPage();
  const button = { textContent: '', title: '', dataset: {}, classList: { toggle: () => {} } };
  page.updateTopicReadButton(button, false);
  assert.equal(button.textContent, 'Mark Read');
});

test('updateTopicReadButton sets dataset.read to "1" when isFullyRead', () => {
  const page = new PostGroupedPage();
  const button = { textContent: '', title: '', dataset: {}, classList: { toggle: () => {} } };
  page.updateTopicReadButton(button, true);
  assert.equal(button.dataset.read, '1');
});

test('updateTopicReadButton sets dataset.read to "0" when not isFullyRead', () => {
  const page = new PostGroupedPage();
  const button = { textContent: '', title: '', dataset: {}, classList: { toggle: () => {} } };
  page.updateTopicReadButton(button, false);
  assert.equal(button.dataset.read, '0');
});

test('updateTopicReadButton toggles snippet-tag-read class', () => {
  const page = new PostGroupedPage();
  const toggles = [];
  const button = { textContent: '', title: '', dataset: {}, classList: { toggle: (cls, state) => { toggles.push([cls, state]); } } };
  page.updateTopicReadButton(button, true);
  assert.deepEqual(toggles.find((t) => t[0] === 'snippet-tag-read'), ['snippet-tag-read', true]);
  assert.deepEqual(toggles.find((t) => t[0] === 'snippet-tag-unread'), ['snippet-tag-unread', false]);
});

// ============================================================
// === changeSnippetsStatus ===
// ============================================================

test('changeSnippetsStatus returns resolved Promise when selections is empty', () => {
  const page = new PostGroupedPage();
  return page.changeSnippetsStatus([], true).then((result) => {
    assert.equal(result, null);
  });
});

test('changeSnippetsStatus returns resolved Promise when selections is null', () => {
  const page = new PostGroupedPage();
  return page.changeSnippetsStatus(null, true).then((result) => {
    assert.equal(result, null);
  });
});

test('changeSnippetsStatus calls fetch with /read/snippets endpoint', () => {
  assert.ok(/fetch\s*\(\s*['"]\/read\/snippets['"]/.test(source),
    'should fetch /read/snippets');
});

test('changeSnippetsStatus sends POST request with JSON body', () => {
  assert.ok(/method\s*:\s*['"]POST['"]/.test(source),
    'should use POST method');
  assert.ok(/'Content-Type'\s*:\s*['"]application\/json['"]/.test(source),
    'should set Content-Type header');
  assert.ok(/JSON\.stringify/.test(source),
    'should stringify body');
  assert.ok(/selections/.test(source),
    'should include selections in body');
  assert.ok(/readed/.test(source),
    'should include readed in body');
});

// ============================================================
// === toggleTopicReadStatus ===
// ============================================================

test('toggleTopicReadStatus returns early when no selections', () => {
  const page = new PostGroupedPage();
  page.getSelectionsForTopic = () => [];
  const button = { disabled: false, dataset: { read: '0' } };
  page.toggleTopicReadStatus('Science', button);
  assert.equal(button.disabled, false);
});

test('toggleTopicReadStatus disables button during operation', () => {
  const page = new PostGroupedPage();
  page.getSelectionsForTopic = () => [{ post_id: '1', sentence_indices: [1] }];
  page.changeSnippetsStatus = () => Promise.resolve({ data: 'ok' });
  page.setReadStateForSelections = () => {};
  page.refreshTopicReadButtons = () => {};
  const button = { disabled: false, dataset: { read: '0' } };
  page.toggleTopicReadStatus('Science', button);
  assert.equal(button.disabled, true);
});

test('toggleTopicReadStatus re-enables button after completion', () => {
  const page = new PostGroupedPage();
  page.getSelectionsForTopic = () => [{ post_id: '1', sentence_indices: [1] }];
  page.changeSnippetsStatus = () => Promise.resolve({ data: 'ok' });
  page.setReadStateForSelections = () => {};
  page.refreshTopicReadButtons = () => {};
  const button = { disabled: false, dataset: { read: '0' } };
  page.toggleTopicReadStatus('Science', button);
  return Promise.resolve()
    .then(() => Promise.resolve())
    .then(() => Promise.resolve())
    .then(() => {
      assert.equal(button.disabled, false);
    });
});

// ============================================================
// === Source: bindGlobalEvents ===
// ============================================================

test('bindGlobalEvents checks for window.EVSYS', () => {
  assert.ok(/if\s*\(\s*window\.EVSYS\s*\)/.test(source),
    'should check window.EVSYS');
});

test('bindGlobalEvents binds to POSTS_UPDATED event', () => {
  assert.ok(/window\.EVSYS\.POSTS_UPDATED/.test(source),
    'should bind to POSTS_UPDATED');
});

test('bindGlobalEvents queries .post-read-status by data-post-id', () => {
  assert.ok(/\.post-read-status\[data-post-id/.test(source),
    'should query .post-read-status by data-post-id');
});

test('bindGlobalEvents toggles read/unread classes on status button', () => {
  assert.ok(/classList\.remove\s*\(\s*['"]unread['"]/.test(source),
    'should remove unread class');
  assert.ok(/classList\.add\s*\(\s*['"]read['"]/.test(source),
    'should add read class');
});

test('bindGlobalEvents updates button textContent to read/unread', () => {
  assert.ok(/textContent\s*=\s*['"]read['"]/.test(source),
    'should set textContent to "read"');
  assert.ok(/textContent\s*=\s*['"]unread['"]/.test(source),
    'should set textContent to "unread"');
});

test('bindGlobalEvents updates section opacity based on read state', () => {
  assert.ok(/section\.style\.opacity\s*=\s*isRead\s*\?\s*['"]0\.6['"]/.test(source),
    'should set opacity to 0.6 when read');
  assert.ok(/['"]1\.0['"]/.test(source),
    'should set opacity to 1.0 when unread');
});

// ============================================================
// === Source: setInitialReadStatus ===
// ============================================================

test('setInitialReadStatus queries .post-read-status.read', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.post-read-status\.read['"]/.test(source),
    'should query .post-read-status.read');
});

test('setInitialReadStatus uses closest to find .post-section', () => {
  assert.ok(/btn\.closest\s*\(\s*['"]\.post-section['"]/.test(source),
    'should use closest(".post-section")');
});

test('setInitialReadStatus sets opacity to 0.6 on read sections', () => {
  assert.ok(/section\.style\.opacity\s*=\s*['"]0\.6['"]/.test(source),
    'should set opacity to 0.6');
});

// ============================================================
// === Source: attachReadButtonHandlers ===
// ============================================================

test('attachReadButtonHandlers queries all .post-read-status', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.post-read-status['"]/.test(source),
    'should query .post-read-status');
});

test('attachReadButtonHandlers adds click event listener', () => {
  assert.ok(/btn\.addEventListener\s*\(\s*['"]click['"]/.test(source),
    'should add click listener');
});

test('attachReadButtonHandlers calls event.stopPropagation', () => {
  assert.ok(/ev\.stopPropagation\(\)/.test(source),
    'should call stopPropagation');
});

test('attachReadButtonHandlers reads data-post-id attribute', () => {
  assert.ok(/getAttribute\s*\(\s*['"]data-post-id['"]/.test(source),
    'should read data-post-id');
});

test('attachReadButtonHandlers checks contains("read") class', () => {
  assert.ok(/classList\.contains\s*\(\s*['"]read['"]/.test(source),
    'should check contains("read")');
});

// ============================================================
// === Source: changePostStatus ===
// ============================================================

test('changePostStatus fetches /read/posts endpoint', () => {
  assert.ok(/fetch\s*\(\s*['"]\/read\/posts['"]/.test(source),
    'should fetch /read/posts');
});

test('changePostStatus sends ids array in body', () => {
  assert.ok(/ids\s*:\s*\[\s*postId/.test(source),
    'should send ids array with postId');
});

test('changePostStatus sends readed boolean in body', () => {
  assert.ok(/readed\s*:\s*newStatus/.test(source),
    'should send readed as newStatus');
});

test('changePostStatus checks response.ok', () => {
  assert.ok(/response\.ok/.test(source),
    'should check response.ok');
});

test('changePostStatus logs error on catch', () => {
  assert.ok(/console\.error\s*\(\s*['"]Failed to update post status['"]/.test(source),
    'should log error message');
});

// ============================================================
// === Source: setupPostSections ===
// ============================================================

test('setupPostSections queries #grouped_posts .post-section', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]#grouped_posts\s+\.post-section['"]/.test(source),
    'should query #grouped_posts .post-section');
});

test('setupPostSections reads data-post-id attribute', () => {
  assert.ok(/getAttribute\s*\(\s*['"]data-post-id['"]/.test(source),
    'should read data-post-id');
});

test('setupPostSections sets data-post-index from window.post_to_index_map', () => {
  assert.ok(/window\.post_to_index_map/.test(source),
    'should use window.post_to_index_map');
  assert.ok(/setAttribute\s*\(\s*['"]data-post-index['"]/.test(source),
    'should set data-post-index');
});

// ============================================================
// === Source: addPostHoverEffects ===
// ============================================================

test('addPostHoverEffects adds mouseenter listener', () => {
  assert.ok(/addEventListener\s*\(\s*['"]mouseenter['"]/.test(source),
    'should add mouseenter listener');
});

test('addPostHoverEffects adds mouseleave listener', () => {
  assert.ok(/addEventListener\s*\(\s*['"]mouseleave['"]/.test(source),
    'should add mouseleave listener');
});

test('addPostHoverEffects sets boxShadow on hover', () => {
  assert.ok(/boxShadow\s*=\s*['"]0 2px 8px rgba\(66, 133, 244, 0\.2\)['"]/.test(source),
    'should set blue boxShadow');
});

test('addPostHoverEffects resets boxShadow on mouseleave', () => {
  assert.ok(/boxShadow\s*=\s*['"]none['"]/.test(source),
    'should reset boxShadow to none');
});

// ============================================================
// === Source: indexSentences ===
// ============================================================

test('indexSentences clears sentencesByGlobalNumber', () => {
  assert.ok(/this\.sentencesByGlobalNumber\.clear\(\)/.test(source),
    'should call clear() on sentencesByGlobalNumber');
});

test('indexSentences reads window.sentences', () => {
  assert.ok(/window\.sentences/.test(source),
    'should read window.sentences');
});

test('indexSentences skips non-finite sentence numbers', () => {
  assert.ok(/Number\.isFinite\(globalNumber\)/.test(source),
    'should check Number.isFinite');
});

test('indexSentences stores postId, postSentenceNumber, and read', () => {
  assert.ok(/postId\s*:\s*sentence\.post_id/.test(source),
    'should store postId');
  assert.ok(/postSentenceNumber/.test(source),
    'should store postSentenceNumber');
  assert.ok(/read\s*:\s*Boolean/.test(source),
    'should store read as Boolean');
});

// ============================================================
// === Source: buildTopicsList structure ===
// ============================================================

test('buildTopicsList queries #topics_list element', () => {
  assert.ok(/document\.getElementById\s*\(\s*['"]topics_list['"]/.test(source),
    'should get #topics_list');
});

test('buildTopicsList returns early when topics_list not found', () => {
  assert.ok(/if\s*\(\s*!topicsList\s*\)/.test(source) || /if\s*\(!topicsList\)/.test(source),
    'should return early if topics_list is missing');
});

test('buildTopicsList checks window.groups for empty state', () => {
  assert.ok(/Object\.keys\s*\(\s*window\.groups\s*\|\|\s*\{\}\s*\)/.test(source),
    'should check Object.keys(window.groups || {})');
});

test('buildTopicsList renders "No topics available" message', () => {
  assert.ok(/No topics available/.test(source),
    'should show "No topics available" message');
});

// ============================================================
// === Source: renderTopicNode structure ===
// ============================================================

test('renderTopicNode creates topic-tree-node with depth class', () => {
  assert.ok(/topic-tree-node/.test(source),
    'should use topic-tree-node class');
  assert.ok(/depth-/.test(source),
    'should include depth class');
});

test('renderTopicNode sets --topic-accent CSS custom property', () => {
  assert.ok(/--topic-accent/.test(source),
    'should set --topic-accent CSS property');
  assert.ok(/setProperty/.test(source),
    'should use setProperty');
});

test('renderTopicNode creates topic-line, topic-title-wrap, topic-name, topic-count elements', () => {
  assert.ok(/topic-line/.test(source),
    'should have topic-line class');
  assert.ok(/topic-title-wrap/.test(source),
    'should have topic-title-wrap class');
  assert.ok(/topic-name/.test(source),
    'should have topic-name class');
  assert.ok(/topic-count/.test(source),
    'should have topic-count class');
});

test('renderTopicNode creates topic-links wrapper with topic-link class', () => {
  assert.ok(/topic-links/.test(source),
    'should have topic-links class');
  assert.ok(/topic-link/.test(source),
    'should use topic-link class');
});

test('renderTopicNode creates topic-controls with prev, next, read-toggle buttons', () => {
  assert.ok(/topic-controls/.test(source),
    'should have topic-controls class');
  assert.ok(/topic-btn-prev/.test(source),
    'should have topic-btn-prev class');
  assert.ok(/topic-btn-next/.test(source),
    'should have topic-btn-next class');
  assert.ok(/topic-btn-read-toggle/.test(source),
    'should have topic-btn-read-toggle class');
});

test('renderTopicNode stores element in topicElements Map', () => {
  assert.ok(/this\.topicElements\.set\s*\(\s*topicPath/.test(source),
    'should store element in topicElements');
});

test('renderTopicNode adds click handler on topic-line', () => {
  assert.ok(/line\.addEventListener\s*\(\s*['"]click['"]/.test(source),
    'should add click listener on topic-line');
});

test('renderTopicNode checks isContentReady before handling topic click', () => {
  assert.ok(/!this\.isContentReady/.test(source),
    'should check isContentReady');
});

test('renderTopicNode prevents prev/next button events from propagating', () => {
  assert.ok(/prevBtn\.addEventListener/.test(source),
    'should add prev button listener');
  assert.ok(/ev\.preventDefault\(\)/.test(source),
    'should call preventDefault');
});

test('renderTopicNode renders children with topic-children wrapper', () => {
  assert.ok(/topic-children/.test(source),
    'should have topic-children class');
});

// ============================================================
// === Source: attachSentenceGroupHandlers ===
// ============================================================

test('attachSentenceGroupHandlers queries .sentence-group', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.sentence-group['"]/.test(source),
    'should query .sentence-group');
});

test('attachSentenceGroupHandlers parses data-sentence as integer', () => {
  assert.ok(/parseInt/.test(source),
    'should use parseInt');
  assert.ok(/getAttribute\s*\(\s*['"]data-sentence['"]/.test(source),
    'should read data-sentence attribute');
});

test('attachSentenceGroupHandlers searches window.groups for topic', () => {
  assert.ok(/window\.groups/.test(source),
    'should search window.groups');
  assert.ok(/includes\s*\(\s*sentNum/.test(source) || /\.includes\(/.test(source),
    'should check if group includes sentence');
});

test('attachSentenceGroupHandlers clicks topic-line when found', () => {
  assert.ok(/topicLine\.click\(\)/.test(source),
    'should click topic-line');
});

// ============================================================
// === Source: highlightSentences ===
// ============================================================

test('highlightSentences returns early for empty indices', () => {
  assert.ok(/!sentenceIndices\s*\|\|\s*sentenceIndices\.length\s*===\s*0/.test(source),
    'should return early for empty indices');
});

test('highlightSentences removes highlighted class from previous highlights', () => {
  assert.ok(/\.sentence-group\.highlighted/.test(source),
    'should query .sentence-group.highlighted');
  assert.ok(/classList\.remove\s*\(\s*['"]highlighted['"]/.test(source),
    'should remove highlighted class');
});

test('highlightSentences queries .sentence-group by data-sentence', () => {
  assert.ok(/\.sentence-group\[data-sentence/.test(source),
    'should query by data-sentence');
});

test('highlightSentences adds highlighted class', () => {
  assert.ok(/classList\.add\s*\(\s*['"]highlighted['"]/.test(source),
    'should add highlighted class');
});

test('highlightSentences scrolls focused sentence into view', () => {
  assert.ok(/scrollIntoView/.test(source),
    'should call scrollIntoView');
  assert.ok(/behavior\s*:\s*['"]smooth['"]/.test(source),
    'should use smooth scroll behavior');
  assert.ok(/block\s*:\s*['"]center['"]/.test(source),
    'should scroll to center');
});

test('highlightSentences adds and removes pulse class', () => {
  assert.ok(/classList\.add\s*\(\s*['"]pulse['"]/.test(source),
    'should add pulse class');
  assert.ok(/classList\.remove\s*\(\s*['"]pulse['"]/.test(source),
    'should remove pulse class');
});

test('highlightSentences uses setTimeout with 100ms delay for scroll', () => {
  assert.ok(/setTimeout[\s\S]*100/.test(source),
    'should use 100ms delay');
});

test('highlightSentences uses setTimeout with 1200ms for pulse removal', () => {
  assert.ok(/1200/.test(source),
    'should use 1200ms for pulse removal');
});

// ============================================================
// === Source: highlightPosts ===
// ============================================================

test('highlightPosts returns early for empty postIds', () => {
  assert.ok(/!postIds\s*\|\|\s*postIds\.length\s*===\s*0/.test(source),
    'should return early for empty postIds');
});

test('highlightPosts queries #grouped_posts .post-section', () => {
  assert.ok(/#grouped_posts\s+\.post-section/.test(source),
    'should query #grouped_posts .post-section');
});

test('highlightPosts removes range-highlight and resets styles', () => {
  assert.ok(/classList\.remove\s*\(\s*['"]range-highlight['"]/.test(source),
    'should remove range-highlight');
  assert.ok(/backgroundColor\s*=\s*['"]['"]/.test(source),
    'should reset background color');
});

test('highlightPosts uses color with 40 hex alpha suffix', () => {
  assert.ok(/color\s*\+\s*['"]40['"]/.test(source),
    'should append 40 alpha to color');
});

test('highlightPosts sets 3px solid border-left with color', () => {
  assert.ok(/borderLeft\s*=\s*['"]3px solid ['"]\s*\+\s*color/.test(source),
    'should set border-left with color');
});

// ============================================================
// === Source: handleHighlightSentenceFromUrl ===
// ============================================================

test('handleHighlightSentenceFromUrl reads highlight_sentence from URL search params', () => {
  assert.ok(/URLSearchParams/.test(source),
    'should use URLSearchParams');
  assert.ok(/window\.location\.search/.test(source),
    'should read window.location.search');
  assert.ok(/get\s*\(\s*['"]highlight_sentence['"]/.test(source),
    'should get highlight_sentence param');
});

test('handleHighlightSentenceFromUrl returns early if param is NaN', () => {
  assert.ok(/isNaN\s*\(\s*highlightSentNum\s*\)/.test(source),
    'should check isNaN');
});

test('handleHighlightSentenceFromUrl searches window.groups for topic', () => {
  assert.ok(/Object\.keys\s*\(\s*window\.groups/.test(source),
    'should iterate window.groups keys');
});

test('handleHighlightSentenceFromUrl checks isContentReady before highlighting', () => {
  assert.ok(/this\.isContentReady/.test(source),
    'should check isContentReady');
});

test('handleHighlightSentenceFromUrl uses 500ms delay for highlight', () => {
  assert.ok(/setTimeout[\s\S]*500/.test(source) || /500\s*\)/.test(source),
    'should use 500ms delay');
});

test('handleHighlightSentenceFromUrl scrolls topic into view', () => {
  assert.ok(/scrollIntoView\s*\(\s*\{[^}]*behavior\s*:\s*['"]smooth['"]/.test(source),
    'should scroll topic into view smoothly');
});

// ============================================================
// === Source: initTabs ===
// ============================================================

test('initTabs queries .tab-header > .tab-btn', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.tab-header\s*>\s*\.tab-btn['"]/.test(source),
    'should query .tab-header > .tab-btn');
});

test('initTabs queries .tab-content', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.tab-content['"]/.test(source),
    'should query .tab-content');
});

test('initTabs returns early if tabs or contents are empty', () => {
  assert.ok(/!tabs\.length\s*\|\|\s*!contents\.length/.test(source),
    'should check for empty tabs/contents');
});

test('initTabs reads data-tab attribute', () => {
  assert.ok(/getAttribute\s*\(\s*['"]data-tab['"]/.test(source),
    'should read data-tab attribute');
});

test('initTabs removes active class from all tabs and contents', () => {
  assert.ok(/t\.classList\.remove\s*\(\s*['"]active['"]/.test(source),
    'should remove active from tabs');
  assert.ok(/c\.classList\.remove\s*\(\s*['"]active['"]/.test(source),
    'should remove active from contents');
});

test('initTabs activates tab-posts for "posts" tab', () => {
  assert.ok(/['"]tab-posts['"]/.test(source),
    'should reference tab-posts');
});

test('initTabs activates tab-topic-chart for "topic-chart" tab', () => {
  assert.ok(/['"]tab-topic-chart['"]/.test(source),
    'should reference tab-topic-chart');
});

test('initTabs calls initChart when topic-chart tab is activated first time', () => {
  assert.ok(/!this\.chartInitialized/.test(source),
    'should check chartInitialized flag');
  assert.ok(/this\.topicFlowChart\s*=\s*this\.initChart\(\)/.test(source),
    'should call initChart');
  assert.ok(/this\.chartInitialized\s*=\s*true/.test(source),
    'should set chartInitialized to true');
});

test('initTabs calls initLocalTabs', () => {
  assert.ok(/this\.initLocalTabs\(\)/.test(source),
    'should call initLocalTabs');
});

// ============================================================
// === Source: initLocalTabs ===
// ============================================================

test('initLocalTabs queries .local-tab-btn', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.local-tab-btn['"]/.test(source),
    'should query .local-tab-btn');
});

test('initLocalTabs reads data-post-id and data-local-tab attributes', () => {
  assert.ok(/getAttribute\s*\(\s*['"]data-post-id['"]/.test(source),
    'should read data-post-id');
  assert.ok(/getAttribute\s*\(\s*['"]data-local-tab['"]/.test(source),
    'should read data-local-tab');
});

test('initLocalTabs queries #post_ + postId', () => {
  assert.ok(/getElementById\s*\(\s*['"]post_['"]\s*\+\s*postId/.test(source),
    'should query #post_ + postId');
});

test('initLocalTabs toggles active class on local tab buttons', () => {
  assert.ok(/\.local-tab-btn['"]\)\.forEach.*classList\.remove\s*\(\s*['"]active['"]/.test(source),
    'should remove active from sibling tabs');
  assert.ok(/tab\.classList\.add\s*\(\s*['"]active['"]/.test(source),
    'should add active to clicked tab');
});

test('initLocalTabs toggles active class on local tab content', () => {
  assert.ok(/\.local-tab-content/.test(source),
    'should query .local-tab-content');
  assert.ok(/data-local-content/.test(source),
    'should use data-local-content');
});

test('initLocalTabs initializes river chart when target is "river"', () => {
  assert.ok(/target\s*===\s*['"]river['"]/.test(source),
    'should check for river target');
  assert.ok(/this\.initRiverChart\(postId\)/.test(source),
    'should call initRiverChart');
  assert.ok(/setTimeout[\s\S]*10/.test(source) || /,\s*10\s*\)/.test(source),
    'should use 10ms delay for river chart');
});

// ============================================================
// === Source: initRiverChart ===
// ============================================================

test('initRiverChart caches chart instance in riverCharts', () => {
  assert.ok(/this\.riverCharts\[postId\]/.test(source),
    'should use riverCharts[postId]');
});

test('initRiverChart calls render on cached chart', () => {
  assert.ok(/this\.riverCharts\[postId\]\.render\(\)/.test(source),
    'should call render on cached chart');
});

test('initRiverChart finds post from window.posts', () => {
  assert.ok(/window\.posts\.find/.test(source),
    'should use window.posts.find');
});

test('initRiverChart checks post.river_data', () => {
  assert.ok(/!post\s*\|\|\s*!post\.river_data/.test(source),
    'should check post and river_data');
});

test('initRiverChart creates container ID as river_chart_ + postId', () => {
  assert.ok(/['"]river_chart_['"]\s*\+\s*postId/.test(source),
    'should use river_chart_ + postId');
});

test('initRiverChart instantiates TopicsRiverChart with topics and articleLength', () => {
  assert.ok(/new\s+TopicsRiverChart/.test(source),
    'should instantiate TopicsRiverChart');
  assert.ok(/river_data\.topics/.test(source),
    'should pass river_data.topics');
  assert.ok(/river_data\.articleLength/.test(source),
    'should pass river_data.articleLength');
});

// ============================================================
// === Source: initZoomControls ===
// ============================================================

test('initZoomControls queries zoom-in, zoom-out, reset-zoom by ID', () => {
  assert.ok(/getElementById\s*\(\s*['"]zoom-in['"]/.test(source),
    'should get zoom-in');
  assert.ok(/getElementById\s*\(\s*['"]zoom-out['"]/.test(source),
    'should get zoom-out');
  assert.ok(/getElementById\s*\(\s*['"]reset-zoom['"]/.test(source),
    'should get reset-zoom');
});

test('initZoomControls returns early if any zoom element is missing', () => {
  assert.ok(/!zoomIn\s*\|\|\s*!zoomOut\s*\|\|\s*!resetZoom/.test(source),
    'should check all zoom elements');
});

test('initZoomControls adds click handlers to zoom buttons', () => {
  assert.ok(/zoomIn\.addEventListener\s*\(\s*['"]click['"]/.test(source),
    'should add click to zoomIn');
  assert.ok(/zoomOut\.addEventListener\s*\(\s*['"]click['"]/.test(source),
    'should add click to zoomOut');
  assert.ok(/resetZoom\.addEventListener\s*\(\s*['"]click['"]/.test(source),
    'should add click to resetZoom');
});

test('initZoomControls calls zoomIn, zoomOut, resetZoom on topicFlowChart', () => {
  assert.ok(/this\.topicFlowChart\.zoomIn\(\)/.test(source),
    'should call zoomIn');
  assert.ok(/this\.topicFlowChart\.zoomOut\(\)/.test(source),
    'should call zoomOut');
  assert.ok(/this\.topicFlowChart\.resetZoom\(\)/.test(source),
    'should call resetZoom');
});

test('initZoomControls guards against null topicFlowChart', () => {
  assert.ok(/if\s*\(\s*this\.topicFlowChart\s*\)/.test(source),
    'should check topicFlowChart before calling methods');
});

// ============================================================
// === Source: initChart ===
// ============================================================

test('initChart returns null when window.groups is missing', () => {
  assert.ok(/if\s*\(\s*!window\.groups\s*\)\s*return\s+null/.test(source),
    'should return null if no window.groups');
});

test('initChart maps window.groups to children array with name and value', () => {
  assert.ok(/Object\.keys\s*\(\s*window\.groups\s*\)\.map/.test(source),
    'should map Object.keys(window.groups)');
  assert.ok(/name\s*:\s*key/.test(source),
    'should set name from key');
  assert.ok(/value\s*:\s*window\.groups\[key\]\.length/.test(source),
    'should set value from group length');
});

test('initChart creates data object with name "Topics"', () => {
  assert.ok(/name\s*:\s*['"]Topics['"]/.test(source),
    'should set name to "Topics"');
});

test('initChart instantiates TopicFlow with data and #topic_flow_chart selector', () => {
  assert.ok(/new\s+TopicFlow\s*\(\s*data\s*,\s*['"]#topic_flow_chart['"]/.test(source),
    'should instantiate TopicFlow');
});

// ============================================================
// === Source: setReadStateForSelections ===
// ============================================================

test('setReadStateForSelections iterates window.sentences', () => {
  assert.ok(/window\.sentences/.test(source),
    'should read window.sentences');
});

test('setReadStateForSelections matches postId and post_sentence_number', () => {
  assert.ok(/String\s*\(\s*sentence\.post_id\s*\)\s*!==\s*postId/.test(source),
    'should compare post_id');
  assert.ok(/sentence\.post_sentence_number/.test(source),
    'should check post_sentence_number');
});

test('setReadStateForSelections updates sentence.read flag', () => {
  assert.ok(/sentence\.read\s*=\s*readed/.test(source),
    'should update sentence.read');
});

test('setReadStateForSelections toggles sentence-read class on .sentence-group elements', () => {
  assert.ok(/\.sentence-group\[data-sentence/.test(source),
    'should query .sentence-group by data-sentence');
  assert.ok(/classList\.toggle\s*\(\s*['"]sentence-read['"]/.test(source),
    'should toggle sentence-read class');
});

// ============================================================
// === Source: refreshTopicReadButtons ===
// ============================================================

test('refreshTopicReadButtons queries .topic-btn-read-toggle', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.topic-btn-read-toggle['"]/.test(source),
    'should query .topic-btn-read-toggle');
});

test('refreshTopicReadButtons reads dataset.topicName', () => {
  assert.ok(/button\.dataset\.topicName/.test(source),
    'should read dataset.topicName');
});

test('refreshTopicReadButtons calls updateTopicReadButton with isTopicFullyRead', () => {
  assert.ok(/this\.updateTopicReadButton\s*\(\s*button\s*,\s*this\.isTopicFullyRead/.test(source),
    'should call updateTopicReadButton with isTopicFullyRead');
});

// ============================================================
// === Source: buildPostsList ===
// ============================================================

test('buildPostsList queries #posts_list element', () => {
  assert.ok(/document\.getElementById\s*\(\s*['"]posts_list['"]/.test(source),
    'should get #posts_list');
});

test('buildPostsList returns early if posts_list missing or posts <= 1', () => {
  assert.ok(/!postsList\s*\|\|\s*!window\.posts\s*\|\|\s*window\.posts\.length\s*<=\s*1/.test(source),
    'should check posts_list, window.posts, and length');
});

test('buildPostsList creates topic-item elements with blue styling', () => {
  assert.ok(/el\.className\s*=\s*['"]topic-item['"]/.test(source),
    'should set topic-item class');
  assert.ok(/'#4285f440'/.test(source),
    'should set blue background color');
  assert.ok(/borderLeft\s*=\s*['"]4px solid #4285f4['"]/.test(source),
    'should set blue border-left');
});

test('buildPostsList shows post_id and feed_title', () => {
  assert.ok(/post\.post_id/.test(source),
    'should display post_id');
  assert.ok(/post\.feed_title/.test(source),
    'should display feed_title');
  assert.ok(/['"]Unknown['"]/.test(source),
    'should fallback to "Unknown"');
});

test('buildPostsList scrolls post into view on click', () => {
  assert.ok(/scrollIntoView/.test(source),
    'should call scrollIntoView');
  assert.ok(/behavior\s*:\s*['"]smooth['"]/.test(source),
    'should use smooth scrolling');
  assert.ok(/block\s*:\s*['"]center['"]/.test(source),
    'should scroll to center');
});

test('buildPostsList adds range-highlight and pulse classes on click', () => {
  assert.ok(/classList\.add\s*\(\s*['"]range-highlight['"]\s*,\s*['"]pulse['"]/.test(source),
    'should add range-highlight and pulse');
});

test('buildPostsList removes highlight after 2000ms', () => {
  assert.ok(/2000/.test(source),
    'should use 2000ms timeout');
});

// ============================================================
// === Source: stripGlobalStyles ===
// ============================================================

test('stripGlobalStyles queries .post-text containers', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.post-text['"]/.test(source),
    'should query .post-text');
});

test('stripGlobalStyles removes style elements', () => {
  assert.ok(/container\.querySelectorAll\s*\(\s*['"]style['"]/.test(source),
    'should query style elements');
  assert.ok(/styleNode\.remove\(\)/.test(source),
    'should call remove() on style nodes');
});

test('stripGlobalStyles removes link[rel="stylesheet"] elements', () => {
  assert.ok(/link\[rel="stylesheet"\]/.test(source),
    'should query link[rel="stylesheet"]');
  assert.ok(/linkNode\.remove\(\)/.test(source),
    'should call remove() on link nodes');
});
