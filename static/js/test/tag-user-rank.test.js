import test from 'node:test';
import assert from 'node:assert/strict';
import {
  USER_RANK_HIDDEN,
  USER_RANK_PINNED,
  USER_RANK_URL,
  saveUserRank,
  supportsUserRank,
  toggledUserRank,
  userRankClass,
} from '../libs/tag-user-rank.js';

function fakeFetch(status, body) {
  const calls = [];
  const fn = async (url, opts) => {
    calls.push({ url, opts });
    return { ok: status >= 200 && status < 300, status, json: async () => body };
  };
  fn.calls = calls;
  return fn;
}

test('toggledUserRank sets the override or clears it when already applied', () => {
  assert.equal(toggledUserRank(null, 'hide'), USER_RANK_HIDDEN);
  assert.equal(toggledUserRank(USER_RANK_HIDDEN, 'hide'), null);
  assert.equal(toggledUserRank(undefined, 'pin'), USER_RANK_PINNED);
  assert.equal(toggledUserRank(USER_RANK_PINNED, 'pin'), null);
  assert.equal(toggledUserRank(USER_RANK_PINNED, 'hide'), USER_RANK_HIDDEN);
  assert.equal(toggledUserRank(USER_RANK_HIDDEN, 'pin'), USER_RANK_PINNED);
});

test('userRankClass maps overrides to item modifiers', () => {
  assert.equal(userRankClass(USER_RANK_HIDDEN), ' cloud_item_hidden');
  assert.equal(userRankClass(USER_RANK_PINNED), ' cloud_item_pinned');
  assert.equal(userRankClass(null), '');
  assert.equal(userRankClass(undefined), '');
});

test('supportsUserRank requires the user_rank key', () => {
  assert.equal(supportsUserRank({ tag: 'a', user_rank: null }), true);
  assert.equal(supportsUserRank({ tag: 'a', user_rank: 'hidden' }), true);
  assert.equal(supportsUserRank({ tag: 'a' }), false);
  assert.equal(supportsUserRank(null), false);
});

test('saveUserRank posts tag and value as JSON', async () => {
  const fetchFn = fakeFetch(200, { ok: true });
  await saveUserRank('python', USER_RANK_PINNED, fetchFn);
  const { url, opts } = fetchFn.calls[0];
  assert.equal(url, USER_RANK_URL);
  assert.equal(opts.method, 'POST');
  assert.deepEqual(JSON.parse(opts.body), { tag: 'python', value: 'pinned' });
});

test('saveUserRank sends null to clear the override', async () => {
  const fetchFn = fakeFetch(200, { ok: true });
  await saveUserRank('python', null, fetchFn);
  assert.deepEqual(JSON.parse(fetchFn.calls[0].opts.body), { tag: 'python', value: null });
});

test('saveUserRank rejects with the server error message', async () => {
  await assert.rejects(
    saveUserRank('python', 'bogus', fakeFetch(400, { error: 'bad value' })),
    /bad value/
  );
});

test('saveUserRank rejects when the body is not JSON', async () => {
  const fetchFn = async () => ({
    ok: false,
    status: 500,
    json: async () => {
      throw new Error('not json');
    },
  });
  await assert.rejects(saveUserRank('python', null, fetchFn), /Request failed \(500\)/);
});
