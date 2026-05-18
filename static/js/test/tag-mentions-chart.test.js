import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'tag-mentions-chart.js');

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

test('class name is TagMentionsChart', () => {
  const src = readSource();
  assert.ok(/export default class TagMentionsChart/.test(src),
    'should define class TagMentionsChart');
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

test('constructor binds updateMentions method', () => {
  const src = readSource();
  assert.ok(/this\.updateMentions\s*=\s*this\.updateMentions\.bind\(this\)/.test(src),
    'should bind updateMentions');
});

// ============================================================
// updateMentions method tests
// ============================================================

test('source declares updateMentions method', () => {
  const src = readSource();
  assert.ok(/updateMentions\s*\(\s*data\s*\)/.test(src),
    'should declare updateMentions(data) method');
});

test('updateMentions checks data.dates.length for empty data', () => {
  const src = readSource();
  assert.ok(/!data\.dates\.length/.test(src),
    'should check !data.dates.length');
});

test('updateMentions calls hideChart when no dates', () => {
  const src = readSource();
  assert.ok(/this\.hideChart\(\)/.test(src),
    'should call hideChart() when no dates');
});

test('updateMentions returns early when no dates', () => {
  const src = readSource();
  assert.ok(/this\.hideChart\(\);\s*return;/.test(src),
    'should return after hideChart');
});

test('updateMentions creates an aggregation map (mp)', () => {
  const src = readSource();
  assert.ok(/let mp\s*=\s*\{\}/.test(src),
    'should create empty mp object');
});

test('updateMentions sorts dates array', () => {
  const src = readSource();
  assert.ok(/dates\.sort\(\)/.test(src),
    'should sort dates array');
});

test('updateMentions creates a slice copy of dates', () => {
  const src = readSource();
  assert.ok(/data\.dates\.slice\(\)/.test(src),
    'should use slice() to copy dates');
});

test('updateMentions uses aggregation window of 86400000ms (24h)', () => {
  const src = readSource();
  assert.ok(/3600\s*\*\s*24\s*\*\s*1000/.test(src),
    'should define 24h aggregation window');
});

test('updateMentions multiplies date timestamps by 1000', () => {
  const src = readSource();
  assert.ok(/u\s*\*=\s*1000/.test(src),
    'should convert seconds to milliseconds');
});

test('updateMentions formats dates as YYYY-MM-DD strings', () => {
  const src = readSource();
  assert.ok(/getFullYear\(\)/.test(src),
    'should use getFullYear');
  assert.ok(/getMonth\(\)/.test(src),
    'should use getMonth');
  assert.ok(/getDate\(\)/.test(src),
    'should use getDate');
});

test('updateMentions uses prettyDate for zero-padded month and day', () => {
  const src = readSource();
  assert.ok(/this\.prettyDate/.test(src),
    'should call this.prettyDate');
});

test('updateMentions increments count per date bucket', () => {
  const src = readSource();
  assert.ok(/mp\[k\]\+\+/.test(src) || /mp\[k\]\s*=\s*mp\[k\]\s*\+\s*1/.test(src),
    'should increment count per bucket');
});

test('updateMentions builds labels and values arrays from mp', () => {
  const src = readSource();
  assert.ok(/let labels\s*=\s*\[\]/.test(src),
    'should create labels array');
  assert.ok(/let values\s*=\s*\[\]/.test(src),
    'should create values array');
  assert.ok(/labels\.push/.test(src),
    'should push to labels');
  assert.ok(/values\.push/.test(src),
    'should push to values');
});

test('updateMentions calls renderChart with tag, labels, values', () => {
  const src = readSource();
  assert.ok(/this\.renderChart\s*\(\s*tag\s*,\s*labels\s*,\s*values\s*\)/.test(src),
    'should call renderChart(tag, labels, values)');
});

// ============================================================
// prettyDate method tests
// ============================================================

test('source declares prettyDate method', () => {
  const src = readSource();
  assert.ok(/prettyDate\s*\(\s*n\s*\)/.test(src),
    'should declare prettyDate(n) method');
});

test('prettyDate treats 0 as 1', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*n\s*===\s*0\s*\)\s*\{?\s*\n?\s*n\s*=\s*1/.test(src),
    'should convert 0 to 1');
});

test('prettyDate adds leading zero for single-digit numbers', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*n\s*<\s*10\s*\)/.test(src),
    'should check n < 10');
  assert.ok(/zero\s*=\s*['"]0['"]/.test(src),
    'should set zero to "0"');
});

test('prettyDate returns zero-padded string', () => {
  const src = readSource();
  assert.ok(/return zero\s*\+\s*n/.test(src),
    'should return zero + n');
});

// ============================================================
// renderChart method tests
// ============================================================

test('source declares renderChart method', () => {
  const src = readSource();
  assert.ok(/renderChart\s*\(\s*tag\s*,\s*labels\s*,\s*values\s*\)/.test(src),
    'should declare renderChart(tag, labels, values) method');
});

test('renderChart creates a dataset object', () => {
  const src = readSource();
  assert.ok(/label\s*:\s*tag/.test(src),
    'should set dataset label to tag');
  assert.ok(/data\s*:\s*values/.test(src),
    'should set dataset data to values');
});

test('renderChart creates dataset with labels array', () => {
  const src = readSource();
  assert.ok(/labels\s*:\s*labels/.test(src),
    'should use labels in dataset');
});

test('renderChart clears container innerHTML', () => {
  const src = readSource();
  assert.ok(/this\._container\.innerHTML\s*=\s*['"]['"]/.test(src),
    'should clear container innerHTML');
});

test('renderChart creates a canvas element', () => {
  const src = readSource();
  assert.ok(/document\.createElement\s*\(\s*['"]canvas['"]\s*\)/.test(src),
    'should create canvas element');
});

test('renderChart appends canvas to container', () => {
  const src = readSource();
  assert.ok(/this\._container\.appendChild/.test(src),
    'should append canvas to container');
});

test('renderChart creates Chart with bar type', () => {
  const src = readSource();
  assert.ok(/new Chart/.test(src),
    'should create new Chart instance');
  assert.ok(/type\s*:\s*['"]bar['"]/.test(src),
    'should set chart type to bar');
});

test('renderChart uses canvas 2d context', () => {
  const src = readSource();
  assert.ok(/getContext\s*\(\s*['"]2d['"]\s*\)/.test(src),
    'should get 2d context');
});

// ============================================================
// hideChart method tests
// ============================================================

test('source declares hideChart method', () => {
  const src = readSource();
  assert.ok(/hideChart\s*\(\s*\)/.test(src),
    'should declare hideChart() method');
});

test('hideChart sets innerHTML to "No mentions" paragraph', () => {
  const src = readSource();
  assert.ok(/this\._container\.innerHTML\s*=\s*['"]<p>No mentions<\/p>['"]/.test(src),
    'should set innerHTML to <p>No mentions</p>');
});

// ============================================================
// bindEvents and start method tests
// ============================================================

test('source declares bindEvents method', () => {
  const src = readSource();
  assert.ok(/bindEvents\s*\(\s*\)/.test(src),
    'should declare bindEvents() method');
});

test('bindEvents binds TAG_MENTIONS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/TAG_MENTIONS_UPDATED/.test(src),
    'should reference TAG_MENTIONS_UPDATED');
  assert.ok(/this\.ES\.bind\s*\(\s*this\.ES\.TAG_MENTIONS_UPDATED/.test(src),
    'should bind TAG_MENTIONS_UPDATED');
});

test('bindEvents binds updateMentions as handler', () => {
  const src = readSource();
  assert.ok(/this\.ES\.bind\s*\([^,]+,\s*this\.updateMentions\s*\)/.test(src),
    'should bind updateMentions as the handler');
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

test('source uses strict mode', () => {
  const src = readSource();
  assert.ok(/'use strict'/.test(src),
    'should use strict mode');
});

test('source uses Date constructor', () => {
  const src = readSource();
  assert.ok(/new Date\(\)/.test(src),
    'should use new Date()');
});
