import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'posts-wordscloud.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class', () => {
  const src = readSource();
  assert.ok(/export default class \w+/.test(src),
    'should export a default class');
});

test('class name is PostsWordsCloud', () => {
  const src = readSource();
  assert.ok(/export default class PostsWordsCloud/.test(src),
    'should define class PostsWordsCloud');
});

test('constructor accepts container_id and event_system parameters', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*container_id\s*,\s*event_system\s*\)/.test(src),
    'should have constructor(container_id, event_system)');
});

test('constructor stores event_system as this.ES', () => {
  const src = readSource();
  assert.ok(/this\.ES\s*=\s*event_system/.test(src),
    'should assign event_system to this.ES');
});

test('constructor queries container using document.querySelector', () => {
  const src = readSource();
  assert.ok(/this\._container\s*=\s*document\.querySelector\s*\(\s*container_id\s*\)/.test(src),
    'should use document.querySelector(container_id)');
});

test('constructor stores container as this._container', () => {
  const src = readSource();
  assert.ok(/this\._container/.test(src),
    'should assign container to this._container');
});

test('constructor binds updateWordsCloud method', () => {
  const src = readSource();
  assert.ok(/this\.updateWordsCloud\s*=\s*this\.updateWordsCloud\.bind\(this\)/.test(src),
    'should bind updateWordsCloud');
});

// ============================================================
// updateWordsCloud method tests
// ============================================================

test('source declares updateWordsCloud method', () => {
  const src = readSource();
  assert.ok(/updateWordsCloud\s*\(\s*data\s*\)/.test(src),
    'should declare updateWordsCloud(data) method');
});

test('updateWordsCloud checks for data.posts existence', () => {
  const src = readSource();
  assert.ok(/!data\.posts/.test(src),
    'should check !data.posts');
});

test('updateWordsCloud returns early when no posts', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*!data\.posts\s*\)\s*\{?\s*return;?/.test(src),
    'should return early when no posts');
});

test('updateWordsCloud creates all_words accumulator object', () => {
  const src = readSource();
  assert.ok(/let all_words\s*=\s*\{\}/.test(src),
    'should create empty all_words object');
});

test('updateWordsCloud loads stopwords', () => {
  const src = readSource();
  assert.ok(/stopwords\(\)/.test(src),
    'should call stopwords()');
  assert.ok(/let stopw\s*=\s*stopwords\(\)/.test(src),
    'should store stopwords in stopw variable');
});

test('updateWordsCloud iterates over data.posts entries', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let item of data\.posts/.test(src),
    'should iterate over data.posts');
});

test('updateWordsCloud splits post.lemmas by space', () => {
  const src = readSource();
  assert.ok(/post\.lemmas\.split\(\s*['"] ['"]\s*\)/.test(src),
    'should split lemmas by space');
});

test('updateWordsCloud skips stop words', () => {
  const src = readSource();
  assert.ok(/stopw\.has\s*\(\s*word\s*\)/.test(src),
    'should check if word is in stopwords');
  assert.ok(/continue/.test(src),
    'should continue/skip stop words');
});

test('updateWordsCloud increments word frequency counters', () => {
  const src = readSource();
  assert.ok(/all_words\[word\]\+\+/.test(src),
    'should increment word count');
});

test('updateWordsCloud initializes new word count to 0', () => {
  const src = readSource();
  assert.ok(/all_words\[word\]\s*=\s*0/.test(src),
    'should initialize new word to 0');
});

// ============================================================
// Word size normalization tests
// ============================================================

test('updateWordsCloud tracks min frequency', () => {
  const src = readSource();
  assert.ok(/let mn\s*=\s*9999999/.test(src),
    'should initialize mn to 9999999');
});

test('updateWordsCloud tracks max frequency', () => {
  const src = readSource();
  assert.ok(/let mx\s*=\s*0/.test(src),
    'should initialize mx to 0');
});

test('updateWordsCloud updates mx when frequency is higher', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*fr\s*>\s*mx\s*\)/.test(src),
    'should check fr > mx');
  assert.ok(/mx\s*=\s*fr/.test(src),
    'should update mx = fr');
});

test('updateWordsCloud updates mn when frequency is lower', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*fr\s*<\s*mn\s*\)/.test(src),
    'should check fr < mn');
  assert.ok(/mn\s*=\s*fr/.test(src),
    'should update mn = fr');
});

test('updateWordsCloud builds data_words array with text and size', () => {
  const src = readSource();
  assert.ok(/data_words\.push/.test(src),
    'should push to data_words');
  assert.ok(/text\s*:\s*word/.test(src),
    'should include text: word');
  assert.ok(/size\s*:\s*fr/.test(src),
    'should include size: frequency');
});

test('updateWordsCloud uses min_f of 8 for font size', () => {
  const src = readSource();
  assert.ok(/const min_f\s*=\s*8/.test(src),
    'should set min_f = 8');
});

test('updateWordsCloud uses max_f of 130 for font size', () => {
  const src = readSource();
  assert.ok(/const max_f\s*=\s*130/.test(src),
    'should set max_f = 130');
});

test('updateWordsCloud normalizes sizes using linear interpolation', () => {
  const src = readSource();
  assert.ok(/min_f\s*\+\s*\(/.test(src),
    'should use min_f as base');
  assert.ok(/mx\s*-\s*mn/.test(src),
    'should divide by (mx - mn)');
});

test('updateWordsCloud maps data_words to normalized sizes', () => {
  const src = readSource();
  assert.ok(/data_words\s*=\s*data_words\.map/.test(src),
    'should use map to normalize sizes');
});

// ============================================================
// Cloud rendering tests
// ============================================================

test('updateWordsCloud creates cloud instance', () => {
  const src = readSource();
  assert.ok(/let cld\s*=\s*cloud\(\)/.test(src),
    'should create cloud instance');
});

test('updateWordsCloud sets cloud size to 1024x1024', () => {
  const src = readSource();
  assert.ok(/\.size\s*\(\s*\[\s*1024\s*,\s*1024\s*\]\s*\)/.test(src),
    'should set cloud size to [1024, 1024]');
});

test('updateWordsCloud sets cloud fontSize from data size', () => {
  const src = readSource();
  assert.ok(/\.fontSize\s*\(\s*\(d\)\s*=>\s*d\.size\s*\)/.test(src),
    'should set fontSize to d.size');
});

test('updateWordsCloud sets cloud words to data_words', () => {
  const src = readSource();
  assert.ok(/\.words\s*\(\s*data_words\s*\)/.test(src),
    'should set words to data_words');
});

test('updateWordsCloud defines an end callback', () => {
  const src = readSource();
  assert.ok(/\.on\s*\(\s*['"]end['"]/.test(src),
    'should set on("end", ...) callback');
});

test('updateWordsCloud uses d3 to select container by id', () => {
  const src = readSource();
  assert.ok(/d3\.select\s*\(\s*['"]#\s*['"]\s*\+\s*this\._container\.id/.test(src),
    'should use d3.select with container id');
});

test('updateWordsCloud appends svg element', () => {
  const src = readSource();
  assert.ok(/\.append\s*\(\s*['"]svg['"]\s*\)/.test(src),
    'should append svg element');
});

test('updateWordsCloud sets svg width from layout size', () => {
  const src = readSource();
  assert.ok(/\.attr\s*\(\s*['"]width['"]\s*,\s*layout\.size\(\)\[0\]/.test(src),
    'should set width from layout.size()[0]');
});

test('updateWordsCloud sets svg height from layout size', () => {
  const src = readSource();
  assert.ok(/\.attr\s*\(\s*['"]height['"]\s*,\s*layout\.size\(\)\[1\]/.test(src),
    'should set height from layout.size()[1]');
});

test('updateWordsCloud appends g group element', () => {
  const src = readSource();
  assert.ok(/\.append\s*\(\s*['"]g['"]\s*\)/.test(src),
    'should append g element');
});

test('updateWordsCloud translates group to center', () => {
  const src = readSource();
  assert.ok(/translate/.test(src),
    'should use translate transform');
});

test('updateWordsCloud binds data to text elements', () => {
  const src = readSource();
  assert.ok(/\.selectAll\s*\(\s*['"]text['"]\s*\)/.test(src),
    'should selectAll text');
  assert.ok(/\.data\s*\(\s*words\s*\)/.test(src),
    'should bind words data');
  assert.ok(/\.enter\(\s*\)\s*\n?\s*\.append\s*\(\s*['"]text['"]\s*\)/.test(src),
    'should enter and append text');
});

test('updateWordsCloud sets font-size style from data', () => {
  const src = readSource();
  assert.ok(/\.style\s*\(\s*['"]font-size['"]/.test(src),
    'should set font-size style');
});

test('updateWordsCloud sets font-family to Impact', () => {
  const src = readSource();
  assert.ok(/\.style\s*\(\s*['"]font-family['"]\s*,\s*['"]Impact['"]/.test(src),
    'should set font-family to Impact');
});

test('updateWordsCloud sets text-anchor to middle', () => {
  const src = readSource();
  assert.ok(/\.attr\s*\(\s*['"]text-anchor['"]\s*,\s*['"]middle['"]/.test(src),
    'should set text-anchor to middle');
});

test('updateWordsCloud sets transform with translate and rotate', () => {
  const src = readSource();
  assert.ok(/\.attr\s*\(\s*['"]transform['"]/.test(src),
    'should set transform attribute');
  assert.ok(/d\.rotate/.test(src),
    'should use d.rotate for rotation');
  assert.ok(/d\.x/.test(src) && /d\.y/.test(src),
    'should use d.x and d.y for position');
});

test('updateWordsCloud sets text content from data.text', () => {
  const src = readSource();
  assert.ok(/\.text\s*\(/.test(src),
    'should set text content');
  assert.ok(/d\.text/.test(src),
    'should use d.text for text content');
});

test('updateWordsCloud starts cloud layout', () => {
  const src = readSource();
  assert.ok(/\.start\(\)/.test(src),
    'should call start()');
});

// ============================================================
// bindEvents and start method tests
// ============================================================

test('source declares bindEvents method', () => {
  const src = readSource();
  assert.ok(/bindEvents\s*\(\s*\)/.test(src),
    'should declare bindEvents() method');
});

test('bindEvents binds POSTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/POSTS_UPDATED/.test(src),
    'should reference POSTS_UPDATED');
  assert.ok(/this\.ES\.bind\s*\(\s*this\.ES\.POSTS_UPDATED/.test(src),
    'should bind POSTS_UPDATED');
});

test('bindEvents binds updateWordsCloud as handler', () => {
  const src = readSource();
  assert.ok(/this\.ES\.bind\s*\([^,]+,\s*this\.updateWordsCloud\s*\)/.test(src),
    'should bind updateWordsCloud as the handler');
});

test('source declares start method', () => {
  const src = readSource();
  assert.ok(/start\s*\(\s*\)/.test(src),
    'should declare start() method');
});

test('start calls bindEvents', () => {
  const src = readSource();
  assert.ok(/this\.bindEvents\(\)/.test(src),
    'should call this.bindEvents()');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports cloud library', () => {
  const src = readSource();
  assert.ok(/import cloud from/.test(src),
    'should import cloud');
  assert.ok(/['"]\.\.\/libs\/cloud\.min\.js['"]/.test(src),
    'should import from ../libs/cloud.min.js');
});

test('source imports stopwords', () => {
  const src = readSource();
  assert.ok(/import.*stopwords.*from/.test(src),
    'should import stopwords');
  assert.ok(/['"]\.\.\/libs\/stopwords\.js['"]/.test(src),
    'should import from ../libs/stopwords.js');
});

test('source uses strict mode', () => {
  const src = readSource();
  assert.ok(/'use strict'/.test(src),
    'should use strict mode');
});
