import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'wordtree.js');

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

test('class name is WordTree', () => {
  const src = readSource();
  assert.ok(/export default class WordTree/.test(src), 'should define class WordTree');
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

test('updateWordTree checks data.texts.length for empty data', () => {
  const src = readSource();
  assert.ok(/!data\.texts\.length/.test(src), 'should check !data.texts.length');
});

test('updateWordTree shows "No texts" when texts array is empty', () => {
  const src = readSource();
  assert.ok(
    /<p class="tag-info-empty-state">No texts<\/p>/.test(src),
    'should display <p class="tag-info-empty-state">No texts</p>'
  );
});

test('updateWordTree sets container innerHTML when no texts', () => {
  const src = readSource();
  assert.ok(
    /this\._container\.innerHTML\s*=\s*['"]<p class="tag-info-empty-state">No texts<\/p>['"]/.test(
      src
    ),
    'should set innerHTML to "No texts" message'
  );
});

test('updateWordTree returns early when no texts', () => {
  const src = readSource();
  assert.ok(/return;?/.test(src), 'should return early for empty texts');
});

test('updateWordTree clears container innerHTML before rendering', () => {
  const src = readSource();
  assert.ok(
    /this\._container\.innerHTML\s*=\s*['"]['"]/.test(src),
    'should clear container innerHTML'
  );
});

// ============================================================
// Text data preparation tests
// ============================================================

test('updateWordTree creates texts array', () => {
  const src = readSource();
  assert.ok(/let texts\s*=\s*\[\]/.test(src), 'should create empty texts array');
});

test('updateWordTree iterates over data.texts', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let txt of data\.texts/.test(src), 'should iterate over data.texts');
});

test('updateWordTree wraps each text in an array', () => {
  const src = readSource();
  assert.ok(/texts\.push\s*\(\s*\[\s*txt\s*\]\s*\)/.test(src), 'should push [txt] to texts');
});

// ============================================================
// Tag splitting and rendering tests
// ============================================================

test('updateWordTree splits data.tag by space', () => {
  const src = readSource();
  assert.ok(/data\.tag\.split\(\s*['"] ['"]\s*\)/.test(src), 'should split tag by space');
});

test('updateWordTree iterates over tags', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*const tag of tags/.test(src), 'should iterate over tags');
});

test('updateWordTree creates a div container per tag', () => {
  const src = readSource();
  assert.ok(
    /document\.createElement\s*\(\s*['"]div['"]\s*\)/.test(src),
    'should create div element'
  );
});

test('updateWordTree appends container div to this._container', () => {
  const src = readSource();
  assert.ok(
    /this\._container\.appendChild\s*\(\s*container\s*\)/.test(src),
    'should append container'
  );
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

test('bindEvents binds WORDTREE_TEXTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/WORDTREE_TEXTS_UPDATED/.test(src), 'should reference WORDTREE_TEXTS_UPDATED');
  assert.ok(
    /this\.ES\.bind\s*\(\s*this\.ES\.WORDTREE_TEXTS_UPDATED/.test(src),
    'should bind WORDTREE_TEXTS_UPDATED'
  );
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

test('start loads Google Charts wordtree package', () => {
  const src = readSource();
  assert.ok(/google\.charts\.load/.test(src), 'should call google.charts.load');
  assert.ok(/packages\s*:\s*\[\s*['"]wordtree['"]\s*\]/.test(src), 'should load wordtree package');
});

test('start calls bindEvents after loading charts', () => {
  const src = readSource();
  assert.ok(/this\.bindEvents\(\)/.test(src), 'should call this.bindEvents()');
});

test('start uses google.charts.load with current version', () => {
  const src = readSource();
  assert.ok(
    /google\.charts\.load\s*\(\s*['"]current['"]/.test(src),
    'should load "current" version'
  );
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
