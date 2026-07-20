import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'bi-grams-graph-simple.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class', () => {
  const src = readSource();
  assert.ok(
    /export default class BiGramsGraphSimple/.test(src),
    'should export a default class BiGramsGraphSimple'
  );
});

test('class does not extend React.Component (vanilla JS)', () => {
  const src = readSource();
  assert.ok(!/extends React/.test(src), 'should not extend React.Component');
});

test('constructor accepts containerSelector, tag, eventSystem parameters', () => {
  const src = readSource();
  assert.ok(
    /constructor\s*\(\s*containerSelector\s*,\s*tag\s*,\s*eventSystem\s*\)/.test(src),
    'should have constructor(containerSelector, tag, eventSystem)'
  );
});

test('constructor assigns containerSelector', () => {
  const src = readSource();
  assert.ok(
    /this\.containerSelector\s*=\s*containerSelector/.test(src),
    'should assign containerSelector'
  );
});

test('constructor assigns tag', () => {
  const src = readSource();
  assert.ok(/this\.tag\s*=\s*tag/.test(src), 'should assign tag');
});

test('constructor assigns eventSystem as this.ES', () => {
  const src = readSource();
  assert.ok(/this\.ES\s*=\s*eventSystem/.test(src), 'should assign eventSystem to this.ES');
});

test('constructor initializes data to null', () => {
  const src = readSource();
  assert.ok(/this\.data\s*=\s*null/.test(src), 'should initialize data to null');
});

test('constructor initializes loaded to false', () => {
  const src = readSource();
  assert.ok(/this\.loaded\s*=\s*false/.test(src), 'should initialize loaded to false');
});

test('source imports rsstag_utils', () => {
  const src = readSource();
  assert.ok(/import rsstag_utils from/.test(src), 'should import rsstag_utils');
});

// ============================================================
// fetchData method tests
// ============================================================

test('source declares fetchData method', () => {
  const src = readSource();
  assert.ok(/fetchData\s*\(\s*\)\s*\{/.test(src), 'should declare fetchData() method');
});

test('fetchData uses rsstag_utils.fetchJSON', () => {
  const src = readSource();
  assert.ok(/rsstag_utils[\s\S]*?\.fetchJSON/.test(src), 'should call rsstag_utils.fetchJSON');
});

test('fetchData uses correct API endpoint with encoded tag', () => {
  const src = readSource();
  assert.ok(
    /\/api\/tag-bi-grams-graph\/\$\{encodeURIComponent\(this\.tag\)\}/.test(src),
    'should use /api/tag-bi-grams-graph/{tag} endpoint'
  );
});

test('fetchData sets GET method', () => {
  const src = readSource();
  assert.ok(/method\s*:\s*['"]GET['"]/.test(src), 'should use GET method');
});

test('fetchData includes credentials: include', () => {
  const src = readSource();
  assert.ok(/credentials\s*:\s*['"]include['"]/.test(src), 'should include credentials');
});

test('fetchData sets Content-Type header', () => {
  const src = readSource();
  assert.ok(
    /['"]Content-Type['"]\s*:\s*['"]application\/json['"]/.test(src),
    'should set Content-Type header'
  );
});

test('fetchData checks response.data', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*response\.data\s*\)/.test(src), 'should check if response.data exists');
});

test('fetchData assigns data and calls renderSimpleVisualization on success', () => {
  const src = readSource();
  assert.ok(
    /this\.data\s*=\s*response\.data/.test(src),
    'should assign response.data to this.data'
  );
  assert.ok(
    /this\.renderSimpleVisualization\s*\(\s*\)/.test(src),
    'should call renderSimpleVisualization'
  );
});

test('fetchData logs error for missing data', () => {
  const src = readSource();
  assert.ok(
    /console\.error\s*\(\s*['"]No graph data received['"]/.test(src),
    'should log "No graph data received"'
  );
});

test('fetchData calls renderError for missing data', () => {
  const src = readSource();
  assert.ok(
    /this\.renderError\s*\(\s*['"]No graph data available['"]\s*\)/.test(src),
    'should call renderError with "No graph data available"'
  );
});

test('fetchData handles fetch error in catch block', () => {
  const src = readSource();
  assert.ok(/\.catch/.test(src), 'should have .catch handler');
  assert.ok(
    /this\.renderError\s*\(\s*['"]Failed to load graph data['"]\s*\)/.test(src),
    'should call renderError for fetch failures'
  );
});

// ============================================================
// renderSimpleVisualization method tests
// ============================================================

test('source declares renderSimpleVisualization method', () => {
  const src = readSource();
  assert.ok(
    /renderSimpleVisualization\s*\(\s*\)\s*\{/.test(src),
    'should declare renderSimpleVisualization() method'
  );
});

test('renderSimpleVisualization validates data.nodes exists', () => {
  const src = readSource();
  assert.ok(/!this\.data\s*\|\|\s*!this\.data\.nodes/.test(src), 'should check for data.nodes');
});

test('renderSimpleVisualization validates data.links exists', () => {
  const src = readSource();
  assert.ok(/!this\.data\.links/.test(src), 'should check for data.links');
});

test('renderSimpleVisualization queries container', () => {
  const src = readSource();
  assert.ok(
    /document\.querySelector\s*\(\s*this\.containerSelector\s*\)/.test(src),
    'should query container by selector'
  );
});

test('renderSimpleVisualization clears container innerHTML', () => {
  const src = readSource();
  assert.ok(/container\.innerHTML\s*=\s*['']/.test(src), 'should clear container innerHTML');
});

test('renderSimpleVisualization creates table element', () => {
  const src = readSource();
  assert.ok(
    /document\.createElement\s*\(\s*['"]table['"]\s*\)/.test(src),
    'should create table element'
  );
});

test('renderSimpleVisualization sets table styles', () => {
  const src = readSource();
  assert.ok(/table\.style\.width\s*=\s*['"]100%['"]/.test(src), 'should set table width to 100%');
  assert.ok(
    /table\.style\.borderCollapse\s*=\s*['"]collapse['"]/.test(src),
    'should set borderCollapse'
  );
  assert.ok(/table\.style\.marginTop\s*=\s*['"]10px['"]/.test(src), 'should set marginTop');
});

test('renderSimpleVisualization creates thead and header row', () => {
  const src = readSource();
  assert.ok(/document\.createElement\s*\(\s*['"]thead['"]\s*\)/.test(src), 'should create thead');
  assert.ok(/document\.createElement\s*\(\s*['"]tr['"]\s*\)/.test(src), 'should create header row');
});

test('renderSimpleVisualization has "Main Tag" column header', () => {
  const src = readSource();
  assert.ok(/['"]Main Tag['"]/.test(src), 'should have "Main Tag" header');
});

test('renderSimpleVisualization has "Related Tag" column header', () => {
  const src = readSource();
  assert.ok(/['"]Related Tag['"]/.test(src), 'should have "Related Tag" header');
});

test('renderSimpleVisualization has "Frequency" column header', () => {
  const src = readSource();
  assert.ok(/['"]Frequency['"]/.test(src), 'should have "Frequency" header');
});

test('renderSimpleVisualization creates tbody', () => {
  const src = readSource();
  assert.ok(/document\.createElement\s*\(\s*['"]tbody['"]\s*\)/.test(src), 'should create tbody');
});

test('renderSimpleVisualization iterates over data.links', () => {
  const src = readSource();
  assert.ok(/this\.data\.links\.forEach/.test(src), 'should iterate over data.links');
});

test('renderSimpleVisualization uses link.source, link.target, link.weight', () => {
  const src = readSource();
  assert.ok(/link\.source/.test(src), 'should use link.source');
  assert.ok(/link\.target/.test(src), 'should use link.target');
  assert.ok(/link\.weight/.test(src), 'should use link.weight');
});

test('renderSimpleVisualization highlights cells matching this.tag', () => {
  const src = readSource();
  assert.ok(/link\.source\s*===\s*this\.tag/.test(src), 'should check if link.source matches tag');
  assert.ok(/link\.target\s*===\s*this\.tag/.test(src), 'should check if link.target matches tag');
  assert.ok(/['"]#ff4500['"]/.test(src), 'should use #ff4500 highlight color');
  assert.ok(/fontWeight\s*=\s*['"]bold['"]/.test(src), 'should set fontWeight to bold');
});

test('renderSimpleVisualization finds mainTagNode', () => {
  const src = readSource();
  assert.ok(/this\.data\.nodes\.find/.test(src), 'should use Array.find on nodes');
  assert.ok(/node\.id\s*===\s*this\.tag/.test(src), 'should find node with matching tag id');
});

test('renderSimpleVisualization adds note paragraph', () => {
  const src = readSource();
  assert.ok(
    /document\.createElement\s*\(\s*['"]p['"]\s*\)/.test(src),
    'should create note paragraph'
  );
  assert.ok(/This is a simple tabular representation/.test(src), 'should include explanatory note');
});

// ============================================================
// renderError method tests
// ============================================================

test('source declares renderError method', () => {
  const src = readSource();
  assert.ok(
    /renderError\s*\(\s*message\s*\)\s*\{/.test(src),
    'should declare renderError(message) method'
  );
});

test('renderError queries container', () => {
  const src = readSource();
  assert.ok(
    /document\.querySelector\s*\(\s*this\.containerSelector\s*\)/.test(src),
    'should query container'
  );
});

test('renderError clears container innerHTML', () => {
  const src = readSource();
  assert.ok(/container\.innerHTML\s*=\s*['']/.test(src), 'should clear container innerHTML');
});

test('renderError creates error div', () => {
  const src = readSource();
  assert.ok(/document\.createElement\s*\(\s*['"]div['"]\s*\)/.test(src), 'should create error div');
});

test('renderError sets message as textContent', () => {
  const src = readSource();
  assert.ok(/errorDiv\.textContent\s*=\s*message/.test(src), 'should set textContent to message');
});

test('renderError sets red styling', () => {
  const src = readSource();
  assert.ok(/errorDiv\.style\.color\s*=\s*['"]#d32f2f['"]/.test(src), 'should set red text color');
  assert.ok(
    /errorDiv\.style\.backgroundColor\s*=\s*['"]#ffebee['"]/.test(src),
    'should set light red background'
  );
  assert.ok(
    /errorDiv\.style\.border\s*=\s*['"]1px solid #ef9a9a['"]/.test(src),
    'should set red border'
  );
  assert.ok(/errorDiv\.style\.borderRadius\s*=\s*['"]4px['"]/.test(src), 'should set borderRadius');
});

// ============================================================
// start method tests
// ============================================================

test('source declares start method', () => {
  const src = readSource();
  assert.ok(/start\s*\(\s*\)\s*\{/.test(src), 'should declare start() method');
});

test('start returns early if already loaded', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*this\.loaded\s*\)\s*\{\s*return/.test(src), 'should return early if loaded');
});

test('start sets loaded to true before fetching', () => {
  const src = readSource();
  assert.ok(/this\.loaded\s*=\s*true/.test(src), 'should set loaded = true');
});

test('start calls fetchData', () => {
  const src = readSource();
  assert.ok(/this\.fetchData\s*\(\s*\)/.test(src), 'should call fetchData()');
});
