import test from 'node:test';
import assert from 'node:assert/strict';

import {
  GROUP_MODES,
  categoryProviders,
  categoryNames,
  flattenFeeds,
  groupModeLabel,
  groupSources,
  groupTreeByProvider,
  providerKey,
  providerLabel,
} from '../libs/source-grouping.js';

function cats() {
  return {
    All: { title: 'All', unread_count: 30, feeds: [] },
    Tech: {
      title: 'Tech',
      category_id: 'Tech',
      unread_count: 12,
      feeds: [
        { feed_id: 'f1', title: 'LWN', unread_count: 5, provider: 'bazqux' },
        { feed_id: 'f2', title: 'apod', unread_count: 7, provider: 'telegram' },
      ],
    },
    Gmail: {
      title: 'Gmail',
      category_id: 'Gmail',
      unread_count: 18,
      feeds: [{ feed_id: 'f3', title: 'billing', unread_count: 18, provider: 'gmail' }],
    },
  };
}

// ============================================================
// Provider identity
// ============================================================

test('providerKey falls back to "other" for feeds stored without a provider', () => {
  assert.equal(providerKey({ provider: 'bazqux' }), 'bazqux');
  assert.equal(providerKey({}), 'other');
  assert.equal(providerKey(null), 'other');
});

test('providerLabel capitalizes names and keeps X uppercase', () => {
  assert.equal(providerLabel('bazqux'), 'Bazqux');
  assert.equal(providerLabel('telegram'), 'Telegram');
  assert.equal(providerLabel('x'), 'X');
});

test('groupModeLabel names every switcher mode', () => {
  assert.deepEqual(GROUP_MODES.map(groupModeLabel), ['Provider', 'Category', 'No grouping']);
});

// ============================================================
// Category helpers
// ============================================================

test('categoryNames drops the All pseudo category', () => {
  assert.deepEqual(categoryNames(cats()), ['Tech', 'Gmail']);
  assert.deepEqual(categoryNames({}), []);
});

test('categoryProviders lists the distinct providers of a category', () => {
  assert.deepEqual(categoryProviders(cats().Tech), ['bazqux', 'telegram']);
  assert.deepEqual(categoryProviders(cats().Gmail), ['gmail']);
  assert.deepEqual(categoryProviders({}), []);
});

// ============================================================
// Tree grouped by provider
// ============================================================

test('groupTreeByProvider builds one group per provider', () => {
  const groups = groupTreeByProvider(cats());

  assert.deepEqual(
    groups.map((group) => group.key),
    ['bazqux', 'gmail', 'telegram']
  );
  assert.deepEqual(
    groups.map((group) => group.label),
    ['Bazqux', 'Gmail', 'Telegram']
  );
});

test('groupTreeByProvider sums unread counts of the provider feeds only', () => {
  const groups = groupTreeByProvider(cats());
  const byKey = {};
  groups.forEach((group) => {
    byKey[group.key] = group;
  });

  assert.equal(byKey.bazqux.unread_count, 5);
  assert.equal(byKey.telegram.unread_count, 7);
  assert.equal(byKey.gmail.unread_count, 18);
  assert.equal(byKey.bazqux.categories[0].unread_count, 5);
});

test('groupTreeByProvider splits a shared category between its providers', () => {
  const groups = groupTreeByProvider(cats());
  const bazqux = groups.filter((group) => group.key === 'bazqux')[0];
  const telegram = groups.filter((group) => group.key === 'telegram')[0];

  assert.deepEqual(
    bazqux.categories.map((entry) => entry.name),
    ['Tech']
  );
  assert.deepEqual(
    bazqux.categories[0].feeds.map((feed) => feed.feed_id),
    ['f1']
  );
  assert.deepEqual(
    telegram.categories[0].feeds.map((feed) => feed.feed_id),
    ['f2']
  );
});

test('a category split across providers offers no delete checkbox', () => {
  const groups = groupTreeByProvider(cats());
  const bazqux = groups.filter((group) => group.key === 'bazqux')[0];
  const gmail = groups.filter((group) => group.key === 'gmail')[0];

  // Deleting by category id would also remove the telegram feed hidden in
  // another group, so the split category must not be selectable there.
  assert.equal(bazqux.categories[0].deletable, false);
  assert.equal(gmail.categories[0].deletable, true);
});

test('groupTreeByProvider keeps the server category order inside a group', () => {
  const data = cats();
  data.Tech.feeds.push({ feed_id: 'f4', title: 'lobsters', unread_count: 1, provider: 'bazqux' });
  data.Gmail.feeds.push({ feed_id: 'f5', title: 'invoices', unread_count: 2, provider: 'bazqux' });
  const bazqux = groupTreeByProvider(data).filter((group) => group.key === 'bazqux')[0];

  assert.deepEqual(
    bazqux.categories.map((entry) => entry.name),
    ['Tech', 'Gmail']
  );
});

test('groupTreeByProvider groups feeds without a provider as other, listed last', () => {
  const data = cats();
  data.Tech.feeds.push({ feed_id: 'f6', title: 'legacy', unread_count: 3 });
  const groups = groupTreeByProvider(data);

  assert.equal(groups[groups.length - 1].key, 'other');
  assert.equal(groups[groups.length - 1].label, 'Other');
});

test('groupTreeByProvider returns no groups for an empty tree', () => {
  assert.deepEqual(groupTreeByProvider({}), []);
  assert.deepEqual(groupTreeByProvider({ All: { title: 'All', feeds: [] } }), []);
});

// ============================================================
// Flat feeds
// ============================================================

test('flattenFeeds returns every feed sorted by title', () => {
  assert.deepEqual(
    flattenFeeds(cats()).map((feed) => feed.title),
    ['apod', 'billing', 'LWN']
  );
});

test('flattenFeeds ignores the All row and survives categories without feeds', () => {
  assert.deepEqual(flattenFeeds({ All: { feeds: [{ feed_id: 'x' }] }, Empty: {} }), []);
});

// ============================================================
// Available sources
// ============================================================

function sources() {
  return [
    { feed_id: 's1', title: 'LWN', provider: 'bazqux', category_title: 'Tech' },
    { feed_id: 's2', title: 'apod', provider: 'telegram', category_title: 'Telegram' },
    { feed_id: 's3', title: 'lobsters', provider: 'bazqux', category_title: 'Tech' },
    { feed_id: 's4', title: 'legacy', category_title: 'Tech' },
  ];
}

test('groupSources by provider keeps items together and puts other last', () => {
  const groups = groupSources(sources(), 'provider');

  assert.deepEqual(
    groups.map((group) => group.label),
    ['Bazqux', 'Telegram', 'Other']
  );
  assert.deepEqual(
    groups[0].items.map((source) => source.feed_id),
    ['s1', 's3']
  );
});

test('groupSources by category groups on the category title', () => {
  const groups = groupSources(sources(), 'category');

  assert.deepEqual(
    groups.map((group) => group.label),
    ['Tech', 'Telegram']
  );
  assert.equal(groups[0].items.length, 3);
});

test('groupSources flat returns one unlabelled group', () => {
  const groups = groupSources(sources(), 'flat');

  assert.equal(groups.length, 1);
  assert.equal(groups[0].label, '');
  assert.equal(groups[0].items.length, 4);
});

test('groupSources returns nothing when there are no sources', () => {
  assert.deepEqual(groupSources([], 'provider'), []);
  assert.deepEqual(groupSources([], 'flat'), []);
  assert.deepEqual(groupSources(undefined, 'category'), []);
});
