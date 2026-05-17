import test from 'node:test';
import assert from 'node:assert/strict';

import { stopwords } from '../libs/stopwords.js';

test('stopwords returns a Set', () => {
  const s = stopwords();
  assert.ok(s instanceof Set);
});

test('stopwords contains English stopwords', () => {
  const s = stopwords();
  assert.ok(s.has('the'));
  assert.ok(s.has('and'));
  assert.ok(s.has('you'));
  assert.ok(s.has('with'));
  assert.ok(s.has('not'));
  assert.ok(s.has('for'));
});

test('stopwords contains Russian stopwords', () => {
  const s = stopwords();
  assert.ok(s.has('и'));
  assert.ok(s.has('в'));
  assert.ok(s.has('не'));
  assert.ok(s.has('на'));
  assert.ok(s.has('что'));
  assert.ok(s.has('с'));
});

test('stopwords does not contain common words that should not be filtered', () => {
  const s = stopwords();
  assert.ok(!s.has('opencode'));
  assert.ok(!s.has('javascript'));
  assert.ok(!s.has('node'));
});

test('stopwords returns a new Set on each call', () => {
  const s1 = stopwords();
  const s2 = stopwords();
  assert.notEqual(s1, s2);
  assert.deepEqual([...s1], [...s2]);
});

test('stopwords Set has reasonable size', () => {
  const s = stopwords();
  assert.ok(s.size > 100);
  assert.ok(s.size < 500);
});

test('stopwords handles special characters correctly', () => {
  const s = stopwords();
  assert.ok(s.has("don't"));
  assert.ok(s.has("it's"));
  assert.ok(s.has("you'll"));
  assert.ok(s.has("shouldn't"));
});
