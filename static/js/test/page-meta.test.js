import test from 'node:test';
import assert from 'node:assert/strict';

// The counters are pure, so they import without any DOM stubbing.
const { countPostsMeta, countTopicsMeta, formatMetaTitle } =
  await import('../components/page-meta.js');

test('canvas post counts split read from unread', () => {
  const counts = countPostsMeta([{ read: true }, { read: false }, {}, { read: true }]);

  assert.deepEqual(counts, { total: 4, read: 2, unread: 2 });
});

test('canvas post counts tolerate a missing payload', () => {
  assert.deepEqual(countPostsMeta(undefined), { total: 0, read: 0, unread: 0 });
});

test('a sentence shared by several topics is counted once', () => {
  // The same (post_id, number) pair reaches the payload through two topics,
  // which is exactly why applyReadState updates every match.
  const topics = [
    {
      name: 'Cars > Engines',
      posts_count: 1,
      sentences_count: 2,
      sources: [
        {
          post_id: 'p1',
          sentences: [
            { number: 1, text: 'One', read: false },
            { number: 2, text: 'Two', read: true },
          ],
        },
      ],
    },
    {
      name: 'Cars > Wheels',
      posts_count: 1,
      sentences_count: 1,
      sources: [{ post_id: 'p1', sentences: [{ number: 1, text: 'One', read: false }] }],
    },
  ];

  const counts = countTopicsMeta(topics);

  // Summing sentences_count would say 3, and posts_count would say 2 posts.
  assert.equal(counts.sentences, 2);
  assert.equal(counts.posts, 1);
  assert.equal(counts.read, 1);
  assert.equal(counts.unread, 1);
});

test('topic totals span every level of a path', () => {
  const topics = [
    { name: 'Cars > Engines', sources: [{ post_id: 'p1', sentences: [{ number: 1, text: 'a' }] }] },
    { name: 'Cars > Wheels', sources: [{ post_id: 'p2', sentences: [{ number: 1, text: 'b' }] }] },
  ];

  // "Cars", "Cars > Engines" and "Cars > Wheels" are all drawn.
  assert.equal(countTopicsMeta(topics).topics, 3);
  assert.equal(countTopicsMeta(topics).posts, 2);
});

test('the same sentence number in different posts stays distinct', () => {
  const topics = [
    {
      name: 'Cars',
      sources: [
        { post_id: 'p1', sentences: [{ number: 1, text: 'a', read: true }] },
        { post_id: 'p2', sentences: [{ number: 1, text: 'b', read: false }] },
      ],
    },
  ];

  const counts = countTopicsMeta(topics);

  assert.equal(counts.sentences, 2);
  assert.equal(counts.read, 1);
  assert.equal(counts.unread, 1);
});

test('an all-unread payload reports every sentence as unread', () => {
  // What the server sends once the only-unread setting has pruned read
  // sentences: "0 read" is then the truth about the page, not a bug.
  const topics = [
    {
      name: 'Cars',
      sources: [
        {
          post_id: 'p1',
          sentences: [
            { number: 1, text: 'a', read: false },
            { number: 2, text: 'b', read: false },
          ],
        },
      ],
    },
  ];

  const counts = countTopicsMeta(topics);

  assert.equal(counts.read, 0);
  assert.equal(counts.unread, 2);
});

test('older payloads of plain sentence strings count as unread', () => {
  const topics = [{ name: 'Cars', sentences: ['One', 'Two', ''] }];

  const counts = countTopicsMeta(topics);

  assert.equal(counts.sentences, 2);
  assert.equal(counts.unread, 2);
  assert.equal(counts.read, 0);
});

test('an empty payload counts nothing', () => {
  assert.deepEqual(countTopicsMeta([]), {
    topics: 0,
    posts: 0,
    sentences: 0,
    read: 0,
    unread: 0,
  });
});

test('the tooltip spells the stats out in order', () => {
  assert.equal(
    formatMetaTitle([
      { label: 'topics', value: 3 },
      { label: 'unread sentences', value: 1, accent: true },
    ]),
    '3 topics, 1 unread sentences'
  );
});
