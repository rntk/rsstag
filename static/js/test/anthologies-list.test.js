import test from 'node:test';
import assert from 'node:assert/strict';

import { renderTagSuggestions } from '../anthologies-list.js';

test('renders one row per suggestion with counts', () => {
  const html = renderTagSuggestions([
    { tag: 'playstation 5', unread: 3, all: 10, info_url: '/tag-info/playstation 5' },
    { tag: 'xbox', unread: 0, all: 4, info_url: '/tag-info/xbox' },
  ]);
  assert.match(html, /playstation 5 \(3 \/ 10\)/);
  assert.match(html, /xbox \(0 \/ 4\)/);
  assert.match(html, /anth-suggest__item/);
  assert.match(html, /data-tag="playstation 5"/);
});

test('suggestion carries the tag-info link', () => {
  const html = renderTagSuggestions([
    { tag: 'xbox', unread: 1, all: 2, info_url: '/tag-info/xbox' },
  ]);
  assert.match(html, /href="\/tag-info\/xbox"/);
});

test('omits the info link when info_url is missing', () => {
  const html = renderTagSuggestions([{ tag: 'xbox', unread: 1, all: 2 }]);
  assert.doesNotMatch(html, /<a /);
  assert.match(html, /xbox \(1 \/ 2\)/);
});

test('returns empty string for empty or invalid input', () => {
  assert.equal(renderTagSuggestions([]), '');
  assert.equal(renderTagSuggestions(null), '');
  assert.equal(renderTagSuggestions(undefined), '');
});

test('escapes tag text, attributes and urls', () => {
  const html = renderTagSuggestions([
    { tag: '<script>"x"</script>', unread: 1, all: 2, info_url: '/tag-info/<x>' },
  ]);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /\/tag-info\/&lt;x&gt;/);
});

test('falls back to placeholder counts when missing', () => {
  const html = renderTagSuggestions([{ tag: 'xbox' }]);
  assert.match(html, /xbox \(— \/ —\)/);
});
