import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'topics-texts.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class', () => {
  const src = readSource();
  assert.ok(
    /export default class TopicsTexts/.test(src),
    'should export a default class TopicsTexts'
  );
});

test('constructor accepts container_id and event_system parameters', () => {
  const src = readSource();
  assert.ok(
    /constructor\s*\(\s*container_id\s*,\s*event_system\s*\)/.test(src),
    'should have constructor(container_id, event_system)'
  );
});

test('constructor assigns event_system to this.ES', () => {
  const src = readSource();
  assert.ok(/this\.ES\s*=\s*event_system/.test(src), 'should assign event_system to this.ES');
});

test('constructor queries container using document.querySelector', () => {
  const src = readSource();
  assert.ok(
    /this\._container\s*=\s*document\.querySelector\s*\(\s*container_id\s*\)/.test(src),
    'should query container using document.querySelector(container_id)'
  );
});

test('constructor binds updateData method', () => {
  const src = readSource();
  assert.ok(
    /this\.updateData\s*=\s*this\.updateData\.bind\s*\(\s*this\s*\)/.test(src),
    'should bind updateData to this'
  );
});

// ============================================================
// updateData method tests
// ============================================================

test('source declares updateData method', () => {
  const src = readSource();
  assert.ok(/updateData\s*\(\s*data\s*\)\s*\{/.test(src), 'should declare updateData(data) method');
});

test('updateData uses a window of 5 for context', () => {
  const src = readSource();
  assert.ok(/const window\s*=\s*5/.test(src), 'should define window = 5 for context');
});

test('updateData iterates over data.topics', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let topic of data\.topics/.test(src), 'should iterate over data.topics');
});

test('updateData iterates over data.texts', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let txt of data\.texts/.test(src), 'should iterate over data.texts');
});

test('updateData splits text by spaces', () => {
  const src = readSource();
  assert.ok(/txt\.split\s*\(\s*['"]\s+['"]\s*\)/.test(src), 'should split text by spaces');
});

test('updateData calculates st_pos with Math.max', () => {
  const src = readSource();
  assert.ok(
    /Math\.max\s*\(\s*i\s*-\s*window\s*,\s*0\s*\)/.test(src),
    'should use Math.max for start position'
  );
});

test('updateData handles end_pos boundary check', () => {
  const src = readSource();
  assert.ok(/end_pos\s*>\s*words\.length/.test(src), 'should check end_pos against words.length');
});

test('updateData calls renderWordtree for each topic', () => {
  const src = readSource();
  assert.ok(
    /this\.renderWordtree\s*\(\s*topic\s*,\s*texts\s*\)/.test(src),
    'should call renderWordtree(topic, texts)'
  );
});

// ============================================================
// renderWordtree method tests
// ============================================================

test('source declares renderWordtree method', () => {
  const src = readSource();
  assert.ok(
    /renderWordtree\s*\(\s*topic\s*,\s*topic_texts\s*\)\s*\{/.test(src),
    'should declare renderWordtree(topic, topic_texts) method'
  );
});

test('renderWordtree creates a div element', () => {
  const src = readSource();
  assert.ok(
    /document\.createElement\s*\(\s*['"]div['"]\s*\)/.test(src),
    'should create a div element'
  );
});

test('renderWordtree appends div to container', () => {
  const src = readSource();
  assert.ok(
    /this\._container\.appendChild\s*\(\s*div\s*\)/.test(src),
    'should append div to _container'
  );
});

test('renderWordtree loads google.charts wordtree package', () => {
  const src = readSource();
  assert.ok(/google\.charts\.load/.test(src), 'should call google.charts.load');
  assert.ok(/packages\s*:\s*\[\s*['"]wordtree['"]\s*\]/.test(src), 'should load wordtree package');
});

test('renderWordtree uses setOnLoadCallback', () => {
  const src = readSource();
  assert.ok(
    /google\.charts\.setOnLoadCallback/.test(src),
    'should use google.charts.setOnLoadCallback'
  );
});

test('renderWordtree creates WordTree chart', () => {
  const src = readSource();
  assert.ok(
    /new google\.visualization\.WordTree/.test(src),
    'should create google.visualization.WordTree'
  );
});

test('renderWordtree sets format to implicit', () => {
  const src = readSource();
  assert.ok(/format\s*:\s*['"]implicit['"]/.test(src), 'should set wordtree format to implicit');
});

test('renderWordtree sets word option to topic', () => {
  const src = readSource();
  assert.ok(/word\s*:\s*topic/.test(src), 'should set word option to topic');
});

test('renderWordtree sets type to double', () => {
  const src = readSource();
  assert.ok(/type\s*:\s*['"]double['"]/.test(src), 'should set wordtree type to double');
});

test('renderWordtree sets backgroundColor', () => {
  const src = readSource();
  assert.ok(
    /backgroundColor\s*:\s*['"]#d7d7af['"]/.test(src),
    'should set background color to #d7d7af'
  );
});

// ============================================================
// bindEvents and start method tests
// ============================================================

test('source declares bindEvents method', () => {
  const src = readSource();
  assert.ok(/bindEvents\s*\(\s*\)\s*\{/.test(src), 'should declare bindEvents() method');
});

test('bindEvents binds TOPICS_TEXTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(
    /this\.ES\.bind\s*\(\s*this\.ES\.TOPICS_TEXTS_UPDATED\s*,\s*this\.updateData/.test(src),
    'should bind TOPICS_TEXTS_UPDATED to updateData'
  );
});

test('source declares start method', () => {
  const src = readSource();
  assert.ok(/start\s*\(\s*\)\s*\{/.test(src), 'should declare start() method');
});

test('start calls bindEvents', () => {
  const src = readSource();
  assert.ok(/this\.bindEvents\s*\(\s*\)/.test(src), 'should call bindEvents()');
});

// ============================================================
// Import and structure tests
// ============================================================

test('source has no React import', () => {
  const src = readSource();
  assert.ok(!/import.*React/.test(src), 'should not import React (vanilla JS)');
});

test('source declares google.charts.load call', () => {
  const src = readSource();
  assert.ok(
    /google\.charts\.load\s*\(\s*['"]current['"]/.test(src),
    'should load current version of google charts'
  );
});

test('renderWordtree uses arrayToDataTable', () => {
  const src = readSource();
  assert.ok(
    /google\.visualization\.arrayToDataTable/.test(src),
    'should use google.visualization.arrayToDataTable'
  );
});

test('renderWordtree builds texts array from topic_texts', () => {
  const src = readSource();
  assert.ok(
    /texts\.push\s*\(\s*\[\s*txt\s*\]\s*\)/.test(src),
    'should push [txt] into texts array'
  );
});
