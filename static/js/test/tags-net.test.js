import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'tags-net.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Class structure tests
// ============================================================

test('source declares TagsNet as a default export class', () => {
  assert.ok(/export\s+default\s+class\s+TagsNet\b/.test(source), 'should export default class TagsNet');
});

test('source declares constructor with container_id and event_system params', () => {
  assert.ok(/constructor\s*\(\s*container_id\s*,\s*event_system\s*\)/.test(source), 'constructor should accept container_id and event_system');
});

test('source assigns this.ES from event_system', () => {
  assert.ok(/this\.ES\s*=\s*event_system/.test(source), 'should store event_system as this.ES');
});

test('source initializes _state with tags Map', () => {
  assert.ok(/this\._state\s*=\s*\{[^}]*tags\s*:\s*new\s+Map\(\)/s.test(source), '_state should initialize tags as new Map()');
});

test('source initializes _state with main_tag and selected_tag as empty strings', () => {
  assert.ok(/main_tag\s*:\s*['"]{2}/.test(source), 'main_tag should be empty string');
  assert.ok(/selected_tag\s*:\s*['"]{2}/.test(source), 'selected_tag should be empty string');
});

test('source gets container via document.getElementById', () => {
  assert.ok(/this\._container\s*=\s*document\.getElementById\(container_id\)/.test(source), 'should get container by ID');
});

test('source initializes _network as null', () => {
  assert.ok(/this\._network\s*=\s*null/.test(source), '_network should start as null');
});

test('source initializes _colors as a Map', () => {
  assert.ok(/this\._colors\s*=\s*new\s+Map\(\)/.test(source), '_colors should be new Map()');
});

test('source initializes _positions as a Map', () => {
  assert.ok(/this\._positions\s*=\s*new\s+Map\(\)/.test(source), '_positions should be new Map()');
});

// ============================================================
// Sentiment colors tests
// ============================================================

test('source defines sentiment colors for negative, positive, positive/negative, neutral', () => {
  assert.ok(/'negative'/.test(source), 'should have negative sentiment');
  assert.ok(/'positive'/.test(source), 'should have positive sentiment');
  assert.ok(/'positive\/negative'/.test(source), 'should have positive/negative sentiment');
  assert.ok(/'neutral'/.test(source), 'should have neutral sentiment');
});

test('source sets negative sentiment color to red (#ff0000)', () => {
  assert.ok(/'negative'\s*,\s*\{[^}]*color\s*:\s*['"]#ff0000/.test(source), 'negative color should be #ff0000');
});

test('source sets positive sentiment color to green (#00ff00)', () => {
  assert.ok(/'positive'\s*,\s*\{[^}]*color\s*:\s*['"]#00ff00/.test(source), 'positive color should be #00ff00');
});

test('source sets neutral sentiment color to gray (#aaaaaa)', () => {
  assert.ok(/'neutral'\s*,\s*\{[^}]*color\s*:\s*['"]#aaaaaa/.test(source), 'neutral color should be #aaaaaa');
});

// ============================================================
// Method declarations tests
// ============================================================

test('source declares getRandomColorHEX method', () => {
  assert.ok(/\bgetRandomColorHEX\s*\(\s*\)/.test(source), 'should have getRandomColorHEX method');
});

test('source declares getRandomCoords method', () => {
  assert.ok(/\bgetRandomCoords\s*\(\s*(?:point)?\s*\)/.test(source), 'should have getRandomCoords method');
});

test('source declares initCoords method', () => {
  assert.ok(/\binitCoords\s*\(\s*state\s*\)/.test(source), 'should have initCoords method');
});

test('source declares loadTagNet method', () => {
  assert.ok(/\bloadTagNet\s*\(\s*event\s*\)/.test(source), 'should have loadTagNet method');
});

test('source declares selectTag method', () => {
  assert.ok(/\bselectTag\s*\(\s*event\s*\)/.test(source), 'should have selectTag method');
});

test('source declares moveDependedNodes method', () => {
  assert.ok(/\bmoveDependedNodes\s*\(\s*delta\s*,\s*tag_id\s*\)/.test(source), 'should have moveDependedNodes method');
});

test('source declares moveTag method', () => {
  assert.ok(/\bmoveTag\s*\(\s*event\s*\)/.test(source), 'should have moveTag method');
});

test('source declares getNetData method', () => {
  assert.ok(/\bgetNetData\s*\(\s*state\s*\)/.test(source), 'should have getNetData method');
});

test('source declares updateNet method', () => {
  assert.ok(/\bupdateNet\s*\(\s*state\s*\)/.test(source), 'should have updateNet method');
});

test('source declares renderNet method', () => {
  assert.ok(/\brenderNet\s*\(\s*nodes\s*,\s*edges\s*\)/.test(source), 'should have renderNet method');
});

test('source declares bindEvents method', () => {
  assert.ok(/\bbindEvents\s*\(\s*\)/.test(source), 'should have bindEvents method');
});

test('source declares start method', () => {
  assert.ok(/\bstart\s*\(\s*\)/.test(source), 'should have start method');
});

// ============================================================
// Method binding tests
// ============================================================

test('source binds updateNet in constructor', () => {
  assert.ok(/this\.updateNet\s*=\s*this\.updateNet\.bind\(this\)/.test(source), 'should bind updateNet');
});

test('source binds loadTagNet in constructor', () => {
  assert.ok(/this\.loadTagNet\s*=\s*this\.loadTagNet\.bind\(this\)/.test(source), 'should bind loadTagNet');
});

test('source binds selectTag in constructor', () => {
  assert.ok(/this\.selectTag\s*=\s*this\.selectTag\.bind\(this\)/.test(source), 'should bind selectTag');
});

test('source binds moveTag in constructor', () => {
  assert.ok(/this\.moveTag\s*=\s*this\.moveTag\.bind\(this\)/.test(source), 'should bind moveTag');
});

// ============================================================
// getRandomColorHEX logic tests
// ============================================================

test('getRandomColorHEX returns object with color and inverted_color', () => {
  const match = source.match(/return\s*\{\s*color\s*:\s*['"]([^'"]+)['"]\s*,\s*inverted_color\s*:\s*['"]([^'"]+)['"]\s*\}/);
  assert.ok(match, 'should return object with color and inverted_color');
  assert.equal(match[1], '#0000ff');
  assert.equal(match[2], '#ffffff');
});

// ============================================================
// getRandomCoords logic tests
// ============================================================

test('getRandomCoords uses x_delta and y_delta of 200', () => {
  assert.ok(/x_delta\s*=\s*200/.test(source), 'x_delta should be 200');
  assert.ok(/y_delta\s*=\s*200/.test(source), 'y_delta should be 200');
});

test('getRandomCoords generates coords within 5000 when no point', () => {
  assert.ok(/Math\.random\(\)\s*\*\s*5000/.test(source), 'should use Math.random() * 5000 for default range');
});

// ============================================================
// Event system interaction tests
// ============================================================

test('loadTagNet triggers LOAD_TAG_NET event', () => {
  assert.ok(/this\.ES\.trigger\s*\(\s*this\.ES\.LOAD_TAG_NET/.test(source), 'loadTagNet should trigger LOAD_TAG_NET');
});

test('selectTag triggers NET_TAG_SELECTED event', () => {
  assert.ok(/this\.ES\.trigger\s*\(\s*this\.ES\.NET_TAG_SELECTED/.test(source), 'selectTag should trigger NET_TAG_SELECTED');
});

test('bindEvents binds TAGS_NET_UPDATED to updateNet', () => {
  assert.ok(/this\.ES\.bind\s*\(\s*this\.ES\.TAGS_NET_UPDATED\s*,\s*this\.updateNet\s*\)/.test(source), 'bindEvents should bind TAGS_NET_UPDATED');
});

test('start calls bindEvents', () => {
  assert.ok(/start\s*\(\s*\)\s*\{[\s\S]*this\.bindEvents\(\)/.test(source), 'start should call bindEvents');
});

// ============================================================
// getNetData node structure tests
// ============================================================

test('getNetData creates nodes with id, label, title from tag.tag', () => {
  assert.ok(/id\s*:\s*tag\.tag/.test(source), 'node id should come from tag.tag');
  assert.ok(/label\s*:\s*tag\.tag/.test(source), 'node label should come from tag.tag');
  assert.ok(/title\s*:\s*tag\.tag/.test(source), 'node title should come from tag.tag');
});

test('getNetData sets node physics to true', () => {
  assert.ok(/physics\s*:\s*true/.test(source), 'node physics should be true');
});

test('getNetData sets node shape to dot', () => {
  assert.ok(/shape\s*:\s*['"]dot['"]/.test(source), 'node shape should be dot');
});

test('getNetData creates edges with from and to properties', () => {
  assert.ok(/from\s*:\s*tag\.tag/.test(source), 'edge from should be tag.tag');
  assert.ok(/to\s*:\s*edge/.test(source), 'edge to should be edge');
});

test('getNetData filters hidden tags', () => {
  assert.ok(/!tag\.hidden/.test(source), 'should check tag.hidden');
});

// ============================================================
// renderNet vis.Network creation tests
// ============================================================

test('renderNet creates new vis.Network', () => {
  assert.ok(/new\s+vis\.Network\s*\(\s*this\._container/.test(source), 'should create vis.Network with container');
});

test('renderNet registers doubleClick event handler', () => {
  assert.ok(/this\._network\.on\s*\(\s*['"]doubleClick['"]/.test(source), 'should register doubleClick handler');
});

test('renderNet registers selectNode event handler', () => {
  assert.ok(/this\._network\.on\s*\(\s*['"]selectNode['"]/.test(source), 'should register selectNode handler');
});

test('renderNet registers dragEnd event handler', () => {
  assert.ok(/this\._network\.on\s*\(\s*['"]dragEnd['"]/.test(source), 'should register dragEnd handler');
});

test('renderNet sets physics to false in options', () => {
  assert.ok(/physics\s*:\s*\{[^}]*enabled\s*:\s*false/s.test(source), 'physics should be disabled in options');
});

test('renderNet sets hideEdgesOnDrag to true', () => {
  assert.ok(/hideEdgesOnDrag\s*:\s*true/.test(source), 'hideEdgesOnDrag should be true');
});

test('renderNet calls setData on existing network', () => {
  assert.ok(/this\._network\.setData\s*\(\s*data\s*\)/.test(source), 'should call setData on existing network');
});

test('renderNet calls redraw on existing network', () => {
  assert.ok(/this\._network\.redraw\(\)/.test(source), 'should call redraw on existing network');
});

// ============================================================
// No-data alert test
// ============================================================

test('renderNet alerts "Not data" when nodes are empty', () => {
  assert.ok(/alert\s*\(\s*['"]Not\s+data['"]\s*\)/.test(source), 'should alert "Not data"');
});

// ============================================================
// initCoords logic tests
// ============================================================

test('initCoords uses getRandomCoords for new positions', () => {
  assert.ok(/this\.getRandomCoords\(\)/.test(source), 'initCoords should call getRandomCoords');
});

test('initCoords uses getRandomCoords(pos) for edge nodes', () => {
  assert.ok(/this\.getRandomCoords\(pos\)/.test(source), 'should pass pos to getRandomCoords for edges');
});

// ============================================================
// moveDependedNodes logic tests
// ============================================================

test('moveDependedNodes uses distance of 100', () => {
  assert.ok(/const\s+distance\s*=\s*100/.test(source), 'moveDependedNodes should use distance=100');
});

test('moveDependedNodes calls _network.moveNode', () => {
  assert.ok(/this\._network\.moveNode\s*\(\s*edge/.test(source), 'should call moveNode on network');
});
