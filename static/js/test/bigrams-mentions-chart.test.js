import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'bigrams-mentions-chart.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class BiGramsMentionsChart', () => {
  const src = readSource();
  assert.ok(
    /export default class BiGramsMentionsChart/.test(src),
    'should export default class BiGramsMentionsChart'
  );
});

test('constructor accepts container_id and event_system parameters', () => {
  const src = readSource();
  assert.ok(
    /constructor\s*\(\s*container_id\s*,\s*event_system/.test(src),
    'should accept container_id and event_system params'
  );
});

test('constructor stores event system as this.ES', () => {
  const src = readSource();
  assert.ok(/this\.ES\s*=\s*event_system/.test(src), 'should store this.ES = event_system');
});

test('constructor queries container element', () => {
  const src = readSource();
  assert.ok(
    /this\._container\s*=\s*document\.querySelector/.test(src),
    'should set this._container via document.querySelector'
  );
});

test('constructor accepts container_id parameter with hash prefix', () => {
  const src = readSource();
  assert.ok(/container_id/.test(src), 'should use container_id parameter');
});

test('constructor binds updateMentions method', () => {
  const src = readSource();
  assert.ok(
    /this\.updateMentions\s*=\s*this\.updateMentions\.bind\(this\)/.test(src),
    'should bind updateMentions'
  );
});

// ============================================================
// getDates method tests
// ============================================================

test('source declares getDates method', () => {
  const src = readSource();
  assert.ok(
    /getDates\s*\(\s*data\s*,\s*skip/.test(src),
    'should declare getDates(data, skip) method'
  );
});

test('getDates iterates over data.bigrams', () => {
  const src = readSource();
  assert.ok(/data\.bigrams/.test(src), 'should access data.bigrams');
  assert.ok(
    /for\s*\(\s*let\s+bi\s+in\s+data\.bigrams/.test(src),
    'should iterate over bigrams object'
  );
});

test('getDates calculates sums for each bigram', () => {
  const src = readSource();
  assert.ok(/sum\s*\+?=/.test(src), 'should accumulate sum');
  assert.ok(/Number\.parseInt/.test(src), 'should use Number.parseInt');
});

test('getDates uses Set for sums tracking', () => {
  const src = readSource();
  assert.ok(/sums\s*=\s*new Set/.test(src), 'should create sums as Set');
});

test('getDates sorts sums array', () => {
  const src = readSource();
  assert.ok(/sums\.sort/.test(src), 'should sort sums');
});

test('getDates uses stopwords for filtering', () => {
  const src = readSource();
  assert.ok(/stopwords\s*\(\s*\)/.test(src), 'should call stopwords()');
  assert.ok(/stopw\.has/.test(src), 'should check words against stopwords');
});

test('getDates splits bigram words for stopword check', () => {
  const src = readSource();
  assert.ok(/bi\.split\s*\(\s*['"] ['"]/.test(src), 'should split bigram by space');
  assert.ok(/bis\[0\]/.test(src) && /bis\[1\]/.test(src), 'should check both words');
});

test('getDates uses skip_bi Set', () => {
  const src = readSource();
  assert.ok(/skip_bi\s*=\s*new Set/.test(src), 'should create skip_bi Set');
  assert.ok(/skip_bi\.add/.test(src), 'should add to skip_bi');
  assert.ok(/skip_bi\.has/.test(src), 'should check skip_bi');
});

test('getDates applies minimum count threshold', () => {
  const src = readSource();
  assert.ok(/min_n/.test(src), 'should define min_n threshold');
  assert.ok(/sum\s*<\s*min_n/.test(src), 'should compare sum against min_n');
});

test('getDates increments min_n when it equals 1', () => {
  const src = readSource();
  assert.ok(
    /min_n\s*===\s*1/.test(src) && /min_n\+\+/.test(src),
    'should increment min_n from 1 to 2'
  );
});

test('getDates collects dates from non-skipped bigrams', () => {
  const src = readSource();
  assert.ok(/dates\s*=\s*new Set/.test(src), 'should create dates Set');
  assert.ok(/dates\.add/.test(src), 'should add dates');
});

test('getDates returns array of dates and skip_bi', () => {
  const src = readSource();
  assert.ok(/return\s*\[\s*dates\s*,\s*skip_bi\s*\]/.test(src), 'should return [dates, skip_bi]');
});

test('getDates skip parameter controls threshold position', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*!\s*skip\s*\)/.test(src) || /!skip/.test(src), 'should check !skip');
  assert.ok(/sum_pos\s*=\s*0/.test(src), 'should reset sum_pos when skip=false');
});

// ============================================================
// updateMentions method tests
// ============================================================

test('source declares updateMentions method', () => {
  const src = readSource();
  assert.ok(/updateMentions\s*\(\s*data/.test(src), 'should declare updateMentions(data) method');
});

test('updateMentions checks for data.bigrams existence', () => {
  const src = readSource();
  assert.ok(/!\s*data\.bigrams/.test(src), 'should check for falsy data.bigrams');
});

test('updateMentions shows "No mentions" when no bigrams', () => {
  const src = readSource();
  assert.ok(
    /['"]<p>No mentions<\/p>['"]/.test(src) || /innerHTML\s*=.*No mentions/.test(src),
    'should set innerHTML to "<p>No mentions</p>"'
  );
});

test('updateMentions clears container before rendering', () => {
  const src = readSource();
  assert.ok(/this\._container\.innerHTML\s*=\s*['']/.test(src), 'should clear innerHTML');
});

test('updateMentions calls getDates with skip=true first', () => {
  const src = readSource();
  assert.ok(/getDates\s*\(\s*data\s*,\s*true/.test(src), 'should call getDates(data, true) first');
});

test('updateMentions retries getDates with skip=false if no dates', () => {
  const src = readSource();
  assert.ok(
    /dates\.size\s*===\s*0/.test(src) || /!dates\.size/.test(src),
    'should check dates size'
  );
  assert.ok(
    /getDates\s*\(\s*data\s*,\s*false/.test(src),
    'should retry with getDates(data, false)'
  );
});

test('updateMentions converts dates Set to sorted array', () => {
  const src = readSource();
  assert.ok(/Array\.from\s*\(\s*dates/.test(src), 'should convert dates Set to array');
  assert.ok(/dates\.sort/.test(src), 'should sort dates array');
});

test('updateMentions aggregates dates within time windows', () => {
  const src = readSource();
  assert.ok(/dates_aggr/.test(src), 'should define dates_aggr');
  assert.ok(
    /aggr\s*=\s*3600\s*\*\s*24\s*\*\s*1000/.test(src) || /aggr/.test(src),
    'should define aggregation interval'
  );
});

test('updateMentions creates Date objects', () => {
  const src = readSource();
  assert.ok(/new Date/.test(src), 'should create Date objects');
  assert.ok(/\.setTime/.test(src), 'should call setTime');
  assert.ok(/\.setMinutes/.test(src), 'should call setMinutes');
  assert.ok(/\.setSeconds/.test(src), 'should call setSeconds');
  assert.ok(/\.setMilliseconds/.test(src), 'should call setMilliseconds');
});

test('updateMentions builds series data array', () => {
  const src = readSource();
  assert.ok(/series\s*=\s*\[\s*\]/.test(src), 'should create series array');
  assert.ok(/series\.push/.test(src), 'should push to series');
});

test('updateMentions adds rsstag_date to series items', () => {
  const src = readSource();
  assert.ok(/rsstag_date/.test(src), 'should include rsstag_date property');
});

test('updateMentions calls renderChart with series', () => {
  const src = readSource();
  assert.ok(/this\.renderChart\s*\(\s*series/.test(src), 'should call renderChart(series)');
});

// ============================================================
// renderChart method tests
// ============================================================

test('source declares renderChart method', () => {
  const src = readSource();
  assert.ok(
    /renderChart\s*\(\s*series_data/.test(src),
    'should declare renderChart(series_data) method'
  );
});

test('renderChart creates labels array', () => {
  const src = readSource();
  assert.ok(/labels\s*=\s*\[\s*\]/.test(src), 'should create labels array');
  assert.ok(/labels\.push/.test(src), 'should push to labels');
});

test('renderChart creates bi_points object', () => {
  const src = readSource();
  assert.ok(/bi_points\s*=\s*\{\s*\}/.test(src), 'should create bi_points object');
  assert.ok(/bi_points\s*\[\s*bi\s*\]/.test(src), 'should access bi_points by bigram');
});

test('renderChart formats date labels with YYYY-MM-DD format', () => {
  const src = readSource();
  assert.ok(/getFullYear/.test(src), 'should use getFullYear');
  assert.ok(/getMonth/.test(src), 'should use getMonth');
  assert.ok(/getDate/.test(src), 'should use getDate');
  assert.ok(/prettyDate/.test(src), 'should call prettyDate helper');
});

test('renderChart builds datasets from bi_points', () => {
  const src = readSource();
  assert.ok(/datasets\s*=\s*\[\s*\]/.test(src), 'should create datasets array');
  assert.ok(/datasets\.push/.test(src), 'should push to datasets');
});

test('renderChart dataset includes label with bigram name', () => {
  const src = readSource();
  assert.ok(/label\s*:/.test(src), 'should set label');
  assert.ok(/label.*bi/.test(src), 'should include bigram in label');
});

test('renderChart dataset includes sum in label', () => {
  const src = readSource();
  assert.ok(/\.reduce/.test(src), 'should use reduce for sum');
  assert.ok(
    /acc\s*\+\s*v/.test(src) || /accumulator.*value/.test(src),
    'should sum values in reduce'
  );
});

test('renderChart uses d3.interpolateCubehelixDefault for colors', () => {
  const src = readSource();
  assert.ok(
    /d3\.interpolateCubehelixDefault/.test(src),
    'should use d3.interpolateCubehelixDefault'
  );
  assert.ok(/Math\.random/.test(src), 'should use Math.random for color seed');
});

test('renderChart creates canvas element', () => {
  const src = readSource();
  assert.ok(
    /document\.createElement\s*\(\s*['"]canvas['"]/.test(src),
    'should create canvas element'
  );
  assert.ok(/this\._container\.appendChild/.test(src), 'should append canvas to container');
});

test('renderChart creates Chart instance', () => {
  const src = readSource();
  assert.ok(/new Chart/.test(src), 'should create new Chart');
  assert.ok(/getContext\s*\(\s*['"]2d['"]/.test(src), 'should get 2d context');
});

test('renderChart sets chart type to bar', () => {
  const src = readSource();
  assert.ok(/type\s*:\s*['"]bar['"]/.test(src), 'should set type to "bar"');
});

test('renderChart sets responsive to true', () => {
  const src = readSource();
  assert.ok(/responsive\s*:\s*true/.test(src), 'should set responsive: true');
});

test('renderChart sets stacked: true on both axes', () => {
  const src = readSource();
  assert.ok(/stacked\s*:\s*true/.test(src), 'should set stacked: true');
  assert.ok(/xAxes/.test(src), 'should configure xAxes');
  assert.ok(/yAxes/.test(src), 'should configure yAxes');
});

test('renderChart sets tooltip mode to index', () => {
  const src = readSource();
  assert.ok(/tooltips/.test(src), 'should configure tooltips');
  assert.ok(/mode\s*:\s*['"]index['"]/.test(src), 'should set mode to "index"');
  assert.ok(/intersect\s*:\s*false/.test(src), 'should set intersect to false');
});

// ============================================================
// prettyDate helper tests
// ============================================================

test('source declares prettyDate method', () => {
  const src = readSource();
  assert.ok(/prettyDate\s*\(\s*n/.test(src), 'should declare prettyDate(n) method');
});

test('prettyDate treats 0 as 1', () => {
  const src = readSource();
  assert.ok(
    /if\s*\(\s*n\s*===\s*0\s*\)/.test(src) && /[\{;]\s*\n?\s*n\s*=\s*1/.test(src),
    'should convert 0 to 1'
  );
});

test('prettyDate adds leading zero for single digits', () => {
  const src = readSource();
  assert.ok(/n\s*<\s*10/.test(src), 'should check if n < 10');
  assert.ok(/zero\s*=\s*['"]0['"]/.test(src), 'should set zero prefix');
});

test('prettyDate returns zero-padded string', () => {
  const src = readSource();
  assert.ok(/return\s*zero\s*\+\s*n/.test(src), 'should return zero + n');
});

// ============================================================
// renderLegend method tests
// ============================================================

test('source declares renderLegend method', () => {
  const src = readSource();
  assert.ok(/renderLegend\s*\(\s*color/.test(src), 'should declare renderLegend(color) method');
});

test('renderLegend iterates over color.domain()', () => {
  const src = readSource();
  assert.ok(/color\.domain/.test(src), 'should call color.domain()');
});

test('renderLegend builds HTML string with inline styles', () => {
  const src = readSource();
  assert.ok(/html\s*\+=/.test(src), 'should append to html string');
  assert.ok(/style/.test(src), 'should include style attributes');
  assert.ok(/background-color/.test(src), 'should set background-color');
  assert.ok(/color\s*\(\s*bi/.test(src), 'should call color(bi) for background');
});

// ============================================================
// Event binding tests
// ============================================================

test('source declares bindEvents method', () => {
  const src = readSource();
  assert.ok(/bindEvents\s*\(\s*\)/.test(src), 'should declare bindEvents() method');
});

test('source declares start method', () => {
  const src = readSource();
  assert.ok(/start\s*\(\s*\)/.test(src), 'should declare start() method');
});

test('start method calls bindEvents', () => {
  const src = readSource();
  assert.ok(
    /start\s*\(\s*\)\s*\{[\s\S]*?this\.bindEvents/.test(src),
    'should call bindEvents in start'
  );
});

test('bindEvents binds to BIGRAMS_MENTIONS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/BIGRAMS_MENTIONS_UPDATED/.test(src), 'should reference BIGRAMS_MENTIONS_UPDATED');
  assert.ok(
    /this\.ES\.bind\s*\(\s*this\.ES\.BIGRAMS_MENTIONS_UPDATED/.test(src),
    'should bind BIGRAMS_MENTIONS_UPDATED event'
  );
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports stopwords', () => {
  const src = readSource();
  assert.ok(/import.*stopwords.*from/.test(src), 'should import stopwords');
});

test('source uses Chart.js library', () => {
  const src = readSource();
  assert.ok(/new Chart/.test(src), 'should use Chart constructor');
});

test('source uses d3 library', () => {
  const src = readSource();
  assert.ok(/d3\./.test(src), 'should use d3 library');
});
