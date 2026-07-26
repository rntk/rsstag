import test from 'node:test';
import assert from 'node:assert/strict';

// feed-hierarchy.js registers a DOMContentLoaded listener at import time, so a
// minimal document/window pair has to exist before the module is loaded.
globalThis.document = {
  getElementById: () => null,
  addEventListener: () => {},
  createElement: () => ({
    style: { setProperty: () => {} },
    classList: { toggle: () => {}, add: () => {}, remove: () => {} },
    setAttribute: () => {},
    appendChild: () => {},
    addEventListener: () => {},
    replaceChildren: () => {},
  }),
  body: { appendChild: () => {} },
};
globalThis.window = { location: { search: '' }, addEventListener: () => {} };

const { topicWithUnreadOnly, filterUnreadTopics, buildTopicTree, FeedHierarchy } =
  await import('../components/feed-hierarchy.js');

/** @returns {object[]} Fresh topics fixture (tests mutate read flags). */
function buildTopics() {
  return [
    {
      name: 'Business > Advertising',
      posts_count: 1,
      sentences_count: 2,
      sentences: ['Ad one.', 'Ad two.'],
      sources: [
        {
          post_id: 'post-1',
          title: 'First post',
          sentences: [
            { number: 1, text: 'Ad one.', read: true },
            { number: 2, text: 'Ad two.', read: true },
          ],
        },
      ],
    },
    {
      name: 'Business > Finance',
      posts_count: 1,
      sentences_count: 2,
      sentences: ['Money one.', 'Money two.'],
      sources: [
        {
          post_id: 'post-1',
          title: 'First post',
          sentences: [
            { number: 3, text: 'Money one.', read: true },
            { number: 4, text: 'Money two.', read: false },
          ],
        },
      ],
    },
    {
      name: 'Sport',
      posts_count: 1,
      sentences_count: 1,
      sentences: ['Match report.'],
      sources: [
        {
          post_id: 'post-2',
          title: 'Second post',
          sentences: [{ number: 1, text: 'Match report.', read: false }],
        },
      ],
    },
  ];
}

test('topicWithUnreadOnly drops a topic whose sentences are all read', () => {
  assert.equal(topicWithUnreadOnly(buildTopics()[0]), null);
});

test('topicWithUnreadOnly keeps unread sentences and recalculates counts', () => {
  const topic = topicWithUnreadOnly(buildTopics()[1]);
  assert.equal(topic.name, 'Business > Finance');
  assert.equal(topic.sentences_count, 1);
  assert.equal(topic.posts_count, 1);
  assert.deepEqual(
    topic.sources[0].sentences.map((sentence) => sentence.number),
    [4]
  );
  assert.deepEqual(topic.sentences, ['Money two.']);
});

test('topicWithUnreadOnly keeps topics without per-sentence sources untouched', () => {
  const topic = { name: 'Legacy', sentences: ['Only strings.'] };
  assert.equal(topicWithUnreadOnly(topic), topic);
});

test('topicWithUnreadOnly counts only posts that still have unread sentences', () => {
  const topic = {
    name: 'Mixed',
    posts_count: 2,
    sentences_count: 2,
    sources: [
      { post_id: 'a', sentences: [{ number: 1, text: 'Read.', read: true }] },
      { post_id: 'b', sentences: [{ number: 1, text: 'Unread.', read: false }] },
    ],
  };
  const filtered = topicWithUnreadOnly(topic);
  assert.equal(filtered.posts_count, 1);
  assert.equal(filtered.sentences_count, 1);
  assert.equal(filtered.sources[0].post_id, 'b');
});

test('topicWithUnreadOnly does not mutate the original topic', () => {
  const topics = buildTopics();
  topicWithUnreadOnly(topics[1]);
  assert.equal(topics[1].sources[0].sentences.length, 2);
  assert.equal(topics[1].sentences_count, 2);
});

test('filterUnreadTopics removes fully read topics only', () => {
  const filtered = filterUnreadTopics(buildTopics());
  assert.deepEqual(
    filtered.map((topic) => topic.name),
    ['Business > Finance', 'Sport']
  );
});

test('filterUnreadTopics tolerates non-array input', () => {
  assert.deepEqual(filterUnreadTopics(null), []);
});

test('a branch disappears once all of its leaf topics are read', () => {
  const topics = buildTopics();
  // Mark the one remaining unread sentence of Business > Finance as read.
  topics[1].sources[0].sentences[1].read = true;
  const roots = buildTopicTree(filterUnreadTopics(topics), 0);
  assert.deepEqual(
    roots.map((entry) => entry.node.name),
    ['Sport']
  );
});

test('a branch survives while one of its leaves still has unread sentences', () => {
  const roots = buildTopicTree(filterUnreadTopics(buildTopics()), 0);
  assert.deepEqual(
    roots.map((entry) => entry.node.name),
    ['Business', 'Sport']
  );
  const business = roots[0];
  assert.deepEqual(Array.from(business.children.keys()), ['Finance']);
});

/** @returns {object} FeedHierarchy instance over the fixture topics. */
function buildPage(onlyUnread) {
  globalThis.window.hierarchyTopics = buildTopics();
  globalThis.window.hierarchyOnlyUnread = onlyUnread;
  return new FeedHierarchy();
}

test('constructor hides read topics when only unread is on', () => {
  const page = buildPage(true);
  assert.equal(page.onlyUnread, true);
  assert.deepEqual(
    page.visibleTopics.map((topic) => topic.name),
    ['Business > Finance', 'Sport']
  );
});

test('constructor keeps every topic when only unread is off', () => {
  const page = buildPage(false);
  assert.equal(page.onlyUnread, false);
  assert.equal(page.visibleTopics.length, 3);
  assert.equal(page.roots.length, 2);
});

test('applyReadState hides a topic once its last unread sentence is read', () => {
  const page = buildPage(true);
  page.applyReadState([{ post_id: 'post-1', sentence_indices: [4] }], true);
  assert.deepEqual(
    page.visibleTopics.map((topic) => topic.name),
    ['Sport']
  );
});

test('applyReadState brings a topic back when a sentence is marked unread', () => {
  const page = buildPage(true);
  page.applyReadState([{ post_id: 'post-1', sentence_indices: [1, 2] }], false);
  assert.deepEqual(
    page.visibleTopics.map((topic) => topic.name),
    ['Business > Advertising', 'Business > Finance', 'Sport']
  );
});

test('applyReadState updates every topic sharing the same sentence', () => {
  const page = buildPage(true);
  page.topics.push({
    name: 'Business > Shared',
    posts_count: 1,
    sentences_count: 1,
    sources: [{ post_id: 'post-1', sentences: [{ number: 4, text: 'Money two.', read: false }] }],
  });
  page.refreshVisibleTopics();
  assert.equal(page.visibleTopics.length, 3);

  page.applyReadState([{ post_id: 'post-1', sentence_indices: [4] }], true);
  assert.deepEqual(
    page.visibleTopics.map((topic) => topic.name),
    ['Sport']
  );
});

test('applyReadState leaves other posts alone', () => {
  const page = buildPage(true);
  page.applyReadState([{ post_id: 'post-2', sentence_indices: [4] }], true);
  assert.deepEqual(
    page.visibleTopics.map((topic) => topic.name),
    ['Business > Finance', 'Sport']
  );
});

test('applyReadState does not prune when only unread is off', () => {
  const page = buildPage(false);
  page.applyReadState([{ post_id: 'post-1', sentence_indices: [4] }], true);
  assert.equal(page.visibleTopics.length, 3);
});

test('refreshVisibleTopics clamps the selected level to the pruned tree', () => {
  const page = buildPage(true);
  page.selectedLevel = 1;
  page.topics[1].sources[0].sentences[1].read = true;
  page.refreshVisibleTopics();
  // Only the single-level "Sport" topic is left.
  assert.equal(page.maxLevel, 0);
  assert.equal(page.selectedLevel, 0);
});
