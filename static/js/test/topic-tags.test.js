import test from 'node:test';
import assert from 'node:assert/strict';

// The helpers below are pure, so they import without any DOM stubbing. The
// dialog itself is covered by test/topic-tags-dialog.test.js.
const { normalizeTopicPath, filterTagsByTerm, formatTagMeta } =
  await import('../components/topic-tags.js');
const { collectTopicPostIds, buildTopicTree } = await import('../components/feed-hierarchy.js');

const TAGS = [
  { tag: 'bank', url: '/tag-info/bank', count: 3, posts_count: 2 },
  { tag: 'rate', url: '/tag-info/rate', count: 1, posts_count: 1 },
];

test('a topic path is joined with one separator whichever form it arrives in', () => {
  // The canvas builds "A > B", the hierarchy "A>B"; the endpoint sees one form.
  assert.equal(normalizeTopicPath('A>B>C'), 'A > B > C');
  assert.equal(normalizeTopicPath('A > B > C'), 'A > B > C');
  assert.equal(normalizeTopicPath('  A  >  B  '), 'A > B');
});

test('empty topic path parts are dropped', () => {
  assert.equal(normalizeTopicPath('>A>>B>'), 'A > B');
  assert.equal(normalizeTopicPath(''), '');
  assert.equal(normalizeTopicPath(null), '');
});

test('an empty search term keeps every tag', () => {
  assert.equal(filterTagsByTerm(TAGS, '  ').length, 2);
  assert.equal(filterTagsByTerm(TAGS, '').length, 2);
});

test('the search term matches tag names case-insensitively', () => {
  assert.deepEqual(
    filterTagsByTerm(TAGS, 'BAN').map((tag) => tag.tag),
    ['bank']
  );
  assert.deepEqual(filterTagsByTerm(TAGS, 'zzz'), []);
});

test('a missing tag list filters to nothing instead of throwing', () => {
  assert.deepEqual(filterTagsByTerm(null, 'a'), []);
  assert.deepEqual(filterTagsByTerm(undefined, ''), []);
});

test('tag meta pluralizes sentences and posts', () => {
  assert.equal(formatTagMeta({ count: 3, posts_count: 2 }), '3 sentences · 2 posts');
  assert.equal(formatTagMeta({ count: 1, posts_count: 1 }), '1 sentence · 1 post');
});

test('tag meta omits an unknown post count', () => {
  assert.equal(formatTagMeta({ count: 2 }), '2 sentences');
  assert.equal(formatTagMeta({}), '0 sentences');
});

const TOPICS = [
  {
    name: 'Tech > AI',
    sources: [
      { post_id: 'p1', sentences: [{ number: 1, text: 'Model news.', read: false }] },
      { post_id: 'p2', sentences: [{ number: 2, text: 'More model news.', read: false }] },
    ],
  },
  {
    name: 'Tech > Hardware',
    sources: [{ post_id: 'p3', sentences: [{ number: 1, text: 'Chip news.', read: false }] }],
  },
];

test('a topic contributes the post ids of everything below it', () => {
  const roots = buildTopicTree(TOPICS);

  assert.deepEqual(collectTopicPostIds(roots[0]), ['p1', 'p2', 'p3']);
  assert.deepEqual(collectTopicPostIds(roots[0].children.get('AI')), ['p1', 'p2']);
  assert.deepEqual(collectTopicPostIds(roots[0].children.get('Hardware')), ['p3']);
});

test('a post shared by sibling topics is sent once', () => {
  const roots = buildTopicTree([
    { name: 'A > One', sources: [{ post_id: 'p1', sentences: ['x'] }] },
    { name: 'A > Two', sources: [{ post_id: 'p1', sentences: ['y'] }] },
  ]);

  assert.deepEqual(collectTopicPostIds(roots[0]), ['p1']);
});

test('a topic without per-post sources yields no post ids', () => {
  // Older payloads carried plain sentences and no post_id to scope by.
  const roots = buildTopicTree([{ name: 'Solo', sentences: ['no sources here'] }]);

  assert.deepEqual(collectTopicPostIds(roots[0]), []);
});
