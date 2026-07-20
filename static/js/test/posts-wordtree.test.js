import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'posts-wordtree.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class', () => {
  const src = readSource();
  assert.ok(/export default class \w+/.test(src), 'should export a default class');
});

test('class name is PostsWordTree', () => {
  const src = readSource();
  assert.ok(/export default class PostsWordTree/.test(src), 'should define class PostsWordTree');
});

test('constructor accepts container_id and event_system parameters', () => {
  const src = readSource();
  assert.ok(
    /constructor\s*\(\s*container_id\s*,\s*event_system\s*\)/.test(src),
    'should have constructor(container_id, event_system)'
  );
});

test('constructor stores event_system as this.ES', () => {
  const src = readSource();
  assert.ok(/this\.ES\s*=\s*event_system/.test(src), 'should assign event_system to this.ES');
});

test('constructor queries container using document.querySelector', () => {
  const src = readSource();
  assert.ok(
    /this\._container\s*=\s*document\.querySelector\s*\(\s*container_id\s*\)/.test(src),
    'should use document.querySelector(container_id)'
  );
});

test('constructor stores container as this._container', () => {
  const src = readSource();
  assert.ok(/this\._container/.test(src), 'should assign container to this._container');
});

test('constructor initializes _renderred flag to false', () => {
  const src = readSource();
  assert.ok(/this\._renderred\s*=\s*false/.test(src), 'should set this._renderred = false');
});

test('constructor binds updateWordTree method', () => {
  const src = readSource();
  assert.ok(
    /this\.updateWordTree\s*=\s*this\.updateWordTree\.bind\(this\)/.test(src),
    'should bind updateWordTree'
  );
});

// ============================================================
// updateWordTree method tests
// ============================================================

test('source declares updateWordTree method', () => {
  const src = readSource();
  assert.ok(
    /updateWordTree\s*\(\s*data\s*\)/.test(src),
    'should declare updateWordTree(data) method'
  );
});

test('updateWordTree skips category group', () => {
  const src = readSource();
  assert.ok(
    /data\.group\s*===\s*['"]category['"]/.test(src),
    'should check for group === "category"'
  );
  assert.ok(/return/.test(src), 'should return early for category');
});

test('updateWordTree skips feed group', () => {
  const src = readSource();
  assert.ok(/data\.group\s*===\s*['"]feed['"]/.test(src), 'should check for group === "feed"');
});

test('updateWordTree skips if already rendered', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*this\._renderred\s*\)/.test(src), 'should check this._renderred');
  assert.ok(/return/.test(src), 'should return if already rendered');
});

test('updateWordTree skips when no posts', () => {
  const src = readSource();
  assert.ok(/!data\.posts/.test(src), 'should check !data.posts');
});

test('updateWordTree sets _renderred flag after validation', () => {
  const src = readSource();
  assert.ok(/this\._renderred\s*=\s*true/.test(src), 'should set this._renderred = true');
});

// ============================================================
// Google Charts loading tests
// ============================================================

test('updateWordTree loads Google Charts wordtree package', () => {
  const src = readSource();
  assert.ok(/google\.charts\.load/.test(src), 'should call google.charts.load');
  assert.ok(/packages\s*:\s*\[\s*['"]wordtree['"]\s*\]/.test(src), 'should load wordtree package');
});

test('updateWordTree uses setOnLoadCallback', () => {
  const src = readSource();
  assert.ok(/google\.charts\.setOnLoadCallback/.test(src), 'should use setOnLoadCallback');
});

// ============================================================
// Word tree rendering tests
// ============================================================

test('updateWordTree splits group_title by space to get tags', () => {
  const src = readSource();
  assert.ok(
    /data\.group_title\.split\(\s*['"] ['"]\s*\)/.test(src),
    'should split group_title by space'
  );
  assert.ok(/let tags\s*=/.test(src), 'should store tags in tags variable');
});

test('updateWordTree uses window size of 10', () => {
  const src = readSource();
  assert.ok(/let window\s*=\s*10/.test(src), 'should set window = 10');
});

test('updateWordTree iterates over tags', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let i\s*=\s*0/.test(src), 'should iterate over tags');
  assert.ok(/i\s*<\s*tags\.length/.test(src), 'should iterate by tag index');
});

test('updateWordTree creates a div container per tag', () => {
  const src = readSource();
  assert.ok(
    /document\.createElement\s*\(\s*['"]div['"]\s*\)/.test(src),
    'should create div element'
  );
  assert.ok(
    /container\.id\s*=\s*['"]wordtree['"]/.test(src),
    'should set container id to wordtree'
  );
});

test('updateWordTree appends container to this._container', () => {
  const src = readSource();
  assert.ok(
    /this\._container\.appendChild\s*\(\s*container\s*\)/.test(src),
    'should append container'
  );
});

test('updateWordTree iterates over data.posts entries', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let item of data\.posts/.test(src), 'should iterate over data.posts');
});

test('updateWordTree splits post.lemmas by space', () => {
  const src = readSource();
  assert.ok(
    /post\.post\.lemmas\.split\(\s*['"] ['"]\s*\)/.test(src),
    'should split lemmas by space'
  );
});

test('updateWordTree searches for tag match in words', () => {
  const src = readSource();
  assert.ok(/tag\s*!==\s*words\[j\]/.test(src), 'should compare tag with words[j]');
  assert.ok(/continue/.test(src), 'should continue if no match');
});

test('updateWordTree extracts context window around matched word', () => {
  const src = readSource();
  assert.ok(/start\s*=\s*j\s*-\s*window/.test(src), 'should calculate start index');
  assert.ok(/end\s*=\s*j\s*\+\s*window/.test(src), 'should calculate end index');
});

test('updateWordTree clamps start to 0', () => {
  const src = readSource();
  assert.ok(
    /if\s*\(\s*start\s*<\s*0\s*\)\s*\{\s*\n?\s*start\s*=\s*0/.test(src),
    'should clamp start to 0'
  );
});

test('updateWordTree clamps end to words.length', () => {
  const src = readSource();
  assert.ok(
    /if\s*\(\s*end\s*>\s*words\.length\s*\)\s*\{\s*\n?\s*end\s*=\s*words\.length/.test(src),
    'should clamp end to words.length'
  );
});

test('updateWordTree joins context words with space', () => {
  const src = readSource();
  assert.ok(/words\.slice\s*\(/.test(src), 'should slice words array');
  assert.ok(/\.join\s*\(\s*['"] ['"]\s*\)/.test(src), 'should join with space');
});

test('updateWordTree pushes text context as array row', () => {
  const src = readSource();
  assert.ok(/texts\.push\s*\(\s*\[\s*text\s*\]\s*\)/.test(src), 'should push [text] to texts');
});

// ============================================================
// Google Visualization chart creation tests
// ============================================================

test('updateWordTree creates DataTable from texts array', () => {
  const src = readSource();
  assert.ok(
    /google\.visualization\.arrayToDataTable\s*\(\s*texts\s*\)/.test(src),
    'should create DataTable from texts'
  );
});

test('updateWordTree creates WordTree visualization', () => {
  const src = readSource();
  assert.ok(
    /new google\.visualization\.WordTree\s*\(\s*container\s*\)/.test(src),
    'should create WordTree with container'
  );
});

test('updateWordTree sets wordtree format to implicit', () => {
  const src = readSource();
  assert.ok(/format\s*:\s*['"]implicit['"]/.test(src), 'should set format to implicit');
});

test('updateWordTree sets wordtree word to current tag', () => {
  const src = readSource();
  assert.ok(/word\s*:\s*tag/.test(src), 'should set word to tag');
});

test('updateWordTree sets wordtree type to double', () => {
  const src = readSource();
  assert.ok(/type\s*:\s*['"]double['"]/.test(src), 'should set type to double');
});

test('updateWordTree sets backgroundColor to #d7d7af', () => {
  const src = readSource();
  assert.ok(
    /backgroundColor\s*:\s*['"]#d7d7af['"]/.test(src),
    'should set backgroundColor to #d7d7af'
  );
});

test('updateWordTree draws chart with options', () => {
  const src = readSource();
  assert.ok(
    /chart\.draw\s*\(\s*dt\s*,\s*options\s*\)/.test(src),
    'should call chart.draw(dt, options)'
  );
});

// ============================================================
// bindEvents and start method tests
// ============================================================

test('source declares bindEvents method', () => {
  const src = readSource();
  assert.ok(/bindEvents\s*\(\s*\)/.test(src), 'should declare bindEvents() method');
});

test('bindEvents binds POSTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/POSTS_UPDATED/.test(src), 'should reference POSTS_UPDATED');
  assert.ok(/this\.ES\.bind\s*\(\s*this\.ES\.POSTS_UPDATED/.test(src), 'should bind POSTS_UPDATED');
});

test('bindEvents binds updateWordTree as handler', () => {
  const src = readSource();
  assert.ok(
    /this\.ES\.bind\s*\([^,]+,\s*this\.updateWordTree\s*\)/.test(src),
    'should bind updateWordTree as the handler'
  );
});

test('source declares start method', () => {
  const src = readSource();
  assert.ok(/start\s*\(\s*\)/.test(src), 'should declare start() method');
});

test('start calls bindEvents', () => {
  const src = readSource();
  assert.ok(/this\.bindEvents\(\)/.test(src), 'should call this.bindEvents()');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source uses strict mode', () => {
  const src = readSource();
  assert.ok(/'use strict'/.test(src), 'should use strict mode');
});

test('source uses google.charts API', () => {
  const src = readSource();
  assert.ok(/google\.charts/.test(src), 'should reference google.charts');
  assert.ok(/google\.visualization/.test(src), 'should reference google.visualization');
});
