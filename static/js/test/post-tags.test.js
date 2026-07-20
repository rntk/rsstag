import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'post-tags.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Function export and signature tests
// ============================================================

test('source exports PostsTags as a named function', () => {
  const src = readSource();
  assert.ok(
    /export function PostsTags\s*\(\s*state\s*\)/.test(src),
    'should export function PostsTags(state)'
  );
});

test('PostsTags accepts a single state parameter', () => {
  const src = readSource();
  assert.ok(/PostsTags\s*\(\s*state\s*\)/.test(src), 'should accept state parameter');
});

// ============================================================
// Empty/missing state handling tests
// ============================================================

test('PostsTags checks for falsy state', () => {
  const src = readSource();
  assert.ok(/!state/.test(src), 'should check !state');
});

test('PostsTags checks for state.posts existence', () => {
  const src = readSource();
  assert.ok(/!state\.posts/.test(src), 'should check !state.posts');
});

test('PostsTags returns "No posts" paragraph when no state or posts', () => {
  const src = readSource();
  assert.ok(/<p>No posts<\/p>/.test(src), 'should return <p>No posts</p>');
});

// ============================================================
// Tag frequency computation tests
// ============================================================

test('PostsTags creates freq accumulator object', () => {
  const src = readSource();
  assert.ok(/let freq\s*=\s*\{\}/.test(src), 'should create empty freq object');
});

test('PostsTags creates tags_l array', () => {
  const src = readSource();
  assert.ok(/let tags_l\s*=\s*\[\]/.test(src), 'should create tags_l array');
});

test('PostsTags iterates over state.posts entries', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let item of state\.posts/.test(src), 'should iterate over state.posts');
});

test('PostsTags iterates over post.post.tags', () => {
  const src = readSource();
  assert.ok(
    /for\s*\(\s*let tag of post\.post\.tags/.test(src),
    'should iterate over post.post.tags'
  );
});

test('PostsTags initializes new tag frequency to 0', () => {
  const src = readSource();
  assert.ok(/freq\[tag\]\s*=\s*0/.test(src), 'should initialize freq[tag] = 0');
});

test('PostsTags pushes new tag to tags_l array', () => {
  const src = readSource();
  assert.ok(/tags_l\.push\s*\(\s*tag\s*\)/.test(src), 'should push tag to tags_l');
});

test('PostsTags increments tag frequency counter', () => {
  const src = readSource();
  assert.ok(/freq\[tag\]\+\+/.test(src), 'should increment freq[tag]');
});

// ============================================================
// Tag sorting tests
// ============================================================

test('PostsTags sorts tags_l array', () => {
  const src = readSource();
  assert.ok(/tags_l\.sort\s*\(/.test(src), 'should call sort on tags_l');
});

test('PostsTags sorts by frequency descending (highest first)', () => {
  const src = readSource();
  assert.ok(/freq\[a\]\s*<\s*freq\[b\]/.test(src), 'should compare freq[a] < freq[b]');
  assert.ok(/return 1/.test(src), 'should return 1 when a < b');
  assert.ok(/return -1/.test(src), 'should return -1 otherwise');
});

// ============================================================
// Tag rendering tests
// ============================================================

test('PostsTags creates tag object with tag property', () => {
  const src = readSource();
  assert.ok(/tag\s*:\s*tg/.test(src), 'should set tag: tg');
});

test('PostsTags creates tag object with count from freq', () => {
  const src = readSource();
  assert.ok(/count\s*:\s*freq\[tg\]/.test(src), 'should set count: freq[tg]');
});

test('PostsTags creates tag object with words array', () => {
  const src = readSource();
  assert.ok(/words\s*:\s*\[\s*tg\s*\]/.test(src), 'should set words: [tg]');
});

test('PostsTags creates tag URL with /tag/ path', () => {
  const src = readSource();
  assert.ok(/['"]\/tag\/['"]/.test(src), 'should use /tag/ path');
});

test('PostsTags uses encodeURIComponent for tag URL', () => {
  const src = readSource();
  assert.ok(/encodeURIComponent\s*\(\s*tg\s*\)/.test(src), 'should use encodeURIComponent(tg)');
});

test('PostsTags renders TagItem components', () => {
  const src = readSource();
  assert.ok(/<TagItem/.test(src), 'should render TagItem');
  assert.ok(/import TagItem from/.test(src), 'should import TagItem');
});

test('PostsTags passes key prop to TagItem', () => {
  const src = readSource();
  assert.ok(/key\s*=\s*\{?\s*tg/.test(src), 'should pass key=tg');
});

test('PostsTags passes tag prop to TagItem', () => {
  const src = readSource();
  assert.ok(/tag\s*=\s*\{?\s*tag\s*\}/.test(src), 'should pass tag object');
});

test('PostsTags passes empty tags array to TagItem', () => {
  const src = readSource();
  assert.ok(/tags\s*=\s*\{?\s*\[\s*\]/.test(src), 'should pass tags=[]');
});

test('PostsTags passes tag_hash prop to TagItem', () => {
  const src = readSource();
  assert.ok(/tag_hash\s*=\s*\{?\s*tg/.test(src), 'should pass tag_hash=tg');
});

test('PostsTags passes uniq_id prop to TagItem', () => {
  const src = readSource();
  assert.ok(/uniq_id\s*=\s*\{?\s*tg/.test(src), 'should pass uniq_id=tg');
});

test('PostsTags passes is_bigram prop as false', () => {
  const src = readSource();
  assert.ok(/is_bigram\s*=\s*\{?\s*false/.test(src), 'should pass is_bigram=false');
});

// ============================================================
// Container and layout tests
// ============================================================

test('PostsTags wraps tags in ol with cloud class', () => {
  const src = readSource();
  assert.ok(/<ol className\s*=\s*['"]cloud['"]/.test(src), 'should use ol with cloud class');
});

test('PostsTags wraps content in div with posts_list class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]posts_list['"]/.test(src), 'should use posts_list class');
});

test('PostsTags uses inner div with posts class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]posts['"]/.test(src), 'should use posts class');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src), 'should import React');
});

test('source imports stopwords', () => {
  const src = readSource();
  assert.ok(/import.*stopwords.*from/.test(src), 'should import stopwords');
  assert.ok(
    /['"]\.\.\/libs\/stopwords\.js['"]/.test(src),
    'should import from ../libs/stopwords.js'
  );
});

test('source uses strict mode', () => {
  const src = readSource();
  assert.ok(/'use strict'/.test(src), 'should use strict mode');
});
