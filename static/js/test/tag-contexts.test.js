import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'tag-contexts.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class extending React.Component', () => {
  const src = readSource();
  assert.ok(/export default class \w+ extends React\.Component/.test(src),
    'should export a default class extending React.Component');
});

test('class name is TagContexts', () => {
  const src = readSource();
  assert.ok(/export default class TagContexts/.test(src),
    'should define class TagContexts');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src),
    'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src),
    'should call super(props)');
});

test('constructor initializes state with tag from props', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{\s*tag\s*:\s*props\.tag/.test(src),
    'should set state.tag from props.tag');
});

test('constructor initializes state with empty texts array', () => {
  const src = readSource();
  assert.ok(/texts\s*:\s*\[\s*\]/.test(src),
    'should set state.texts to empty array');
});

test('constructor binds updateState method', () => {
  const src = readSource();
  assert.ok(/this\.updateState\s*=\s*this\.updateState\.bind\(this\)/.test(src),
    'should bind updateState');
});

// ============================================================
// updateState method tests
// ============================================================

test('source declares updateState method', () => {
  const src = readSource();
  assert.ok(/updateState\s*\(\s*state\s*\)/.test(src),
    'should declare updateState(state) method');
});

test('updateState calls setState with state parameter', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src),
    'should call setState(state)');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)/.test(src),
    'should declare componentDidMount() method');
});

test('componentDidMount binds WORDTREE_TEXTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/WORDTREE_TEXTS_UPDATED/.test(src),
    'should reference WORDTREE_TEXTS_UPDATED');
  assert.ok(/this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.WORDTREE_TEXTS_UPDATED/.test(src),
    'should bind WORDTREE_TEXTS_UPDATED event');
});

test('componentDidMount binds updateState as handler', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.bind\s*\([^,]+,\s*this\.updateState\s*\)/.test(src),
    'should bind updateState as the event handler');
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentWillUnmount\s*\(\s*\)/.test(src),
    'should declare componentWillUnmount() method');
});

test('componentWillUnmount unbinds WORDTREE_TEXTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.WORDTREE_TEXTS_UPDATED/.test(src),
    'should unbind WORDTREE_TEXTS_UPDATED event');
});

test('componentWillUnmount unbinds updateState as handler', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.unbind\s*\([^,]+,\s*this\.updateState\s*\)/.test(src),
    'should unbind updateState as the event handler');
});

// ============================================================
// hrefs helper method tests (source inspection)
// ============================================================

test('source declares hrefs method with left, tag, right parameters', () => {
  const src = readSource();
  assert.ok(/hrefs\s*\(\s*left\s*,\s*tag\s*,\s*right\s*\)/.test(src),
    'should declare hrefs(left, tag, right) method');
});

test('hrefs creates an array for results', () => {
  const src = readSource();
  assert.ok(/let hrefs\s*=\s*\[\s*\]/.test(src),
    'should initialize hrefs as empty array');
});

test('hrefs trims and splits left text by space', () => {
  const src = readSource();
  assert.ok(/left\.trim\(\)\.split\(\s*['"] ['"]\s*\)/.test(src),
    'should trim and split left by space');
});

test('hrefs trims and splits right text by space', () => {
  const src = readSource();
  assert.ok(/right\.trim\(\)\.split\(\s*['"] ['"]\s*\)/.test(src),
    'should trim and split right by space');
});

test('hrefs uses encodeURIComponent for entity URLs', () => {
  const src = readSource();
  const matches = src.match(/encodeURIComponent/g);
  assert.ok(matches && matches.length >= 3,
    'should use encodeURIComponent at least 3 times');
});

test('hrefs builds /entity/ URLs', () => {
  const src = readSource();
  assert.ok(/['"]\/entity\/['"]/.test(src),
    'should use /entity/ path');
});

test('hrefs pushes "#" fallback for empty left', () => {
  const src = readSource();
  assert.ok(/hrefs\.push\s*\(\s*['"]#['"]\s*\)/.test(src),
    'should push # as fallback');
});

test('hrefs returns an array of 3 hrefs', () => {
  const src = readSource();
  assert.ok(/hrefs\.push/.test(src),
    'should push multiple hrefs');
  const pushes = src.match(/hrefs\.push/g);
  assert.ok(pushes && pushes.length >= 3,
    'should push at least 3 hrefs');
});

test('hrefs uses last word from left for left URL', () => {
  const src = readSource();
  assert.ok(/ls\[ls\.length\s*-\s*1\]/.test(src),
    'should get last word from left split');
});

test('hrefs uses first word from right for right URL', () => {
  const src = readSource();
  assert.ok(/rs\[0\]/.test(src),
    'should get first word from right split');
});

test('hrefs combines l + tag + r for third URL', () => {
  const src = readSource();
  assert.ok(/\(\s*l\s*\+\s*['"] ['"]\s*\+\s*tag\s*\+\s*['"] ['"]\s*\+\s*r\s*\)\.trim\(\)/.test(src),
    'should combine l, tag, r for combined URL');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render checks this.state.texts for empty data', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*!this\.state\.texts\s*\)/.test(src),
    'should check !this.state.texts');
});

test('render returns "No data yet" when no texts', () => {
  const src = readSource();
  assert.ok(/<p>No data yet<\/p>/.test(src),
    'should return <p>No data yet</p> when no texts');
});

test('render uses Set to deduplicate texts', () => {
  const src = readSource();
  assert.ok(/new Set\s*\(\s*this\.state\.texts\s*\)/.test(src),
    'should create Set from state.texts');
});

test('render sorts deduplicated texts', () => {
  const src = readSource();
  assert.ok(/texts_s\.sort\(\)/.test(src),
    'should call sort() on texts_s');
});

test('render uses indexOf to find tag position in text', () => {
  const src = readSource();
  assert.ok(/\.indexOf\s*\(\s*tag\s*\)/.test(src),
    'should use indexOf to find tag');
});

test('render uses substr to extract left text', () => {
  const src = readSource();
  assert.ok(/\.substr\s*\(\s*0\s*,\s*pos\s*\)/.test(src),
    'should use substr(0, pos) for left text');
});

test('render uses substr to extract right text', () => {
  const src = readSource();
  assert.ok(/\.substr\s*\(\s*pos\s*\+\s*tag\.length/.test(src),
    'should use substr for right text');
});

// ============================================================
// Table rendering tests
// ============================================================

test('render creates left_style with textAlign center', () => {
  const src = readSource();
  assert.ok(/left_style/.test(src),
    'should define left_style');
  assert.ok(/textAlign\s*:\s*['"]center['"]/.test(src),
    'should set textAlign to center');
});

test('render creates middle_style with fontWeight bold', () => {
  const src = readSource();
  assert.ok(/middle_style/.test(src),
    'should define middle_style');
  assert.ok(/fontWeight\s*:\s*['"]bold['"]/.test(src),
    'should set fontWeight to bold');
});

test('render creates right_style with textAlign center', () => {
  const src = readSource();
  assert.ok(/right_style/.test(src),
    'should define right_style');
});

test('render pushes to lefts, middles, rights arrays', () => {
  const src = readSource();
  assert.ok(/lefts\.push/.test(src),
    'should push to lefts array');
  assert.ok(/middles\.push/.test(src),
    'should push to middles array');
  assert.ok(/rights\.push/.test(src),
    'should push to rights array');
});

test('render returns table with tbody', () => {
  const src = readSource();
  assert.ok(/<table>/.test(src),
    'should render table element');
  assert.ok(/<tbody>/.test(src),
    'should render tbody');
});

test('render creates three rows in tbody', () => {
  const src = readSource();
  const rows = src.match(/<tr>/g);
  assert.ok(rows && rows.length >= 3,
    'should have at least 3 <tr> elements');
});

test('render uses key patterns for td elements', () => {
  const src = readSource();
  assert.ok(/txt_left/.test(src),
    'should use txt_left key pattern');
  assert.ok(/txt_middle/.test(src),
    'should use txt_middle key pattern');
  assert.ok(/txt_right/.test(src),
    'should use txt_right key pattern');
});

// ============================================================
// Anchor/link rendering tests
// ============================================================

test('render wraps cells in anchor tags with hrefs', () => {
  const src = readSource();
  assert.ok(/<a href=\{hrefs\[0\]\}>/.test(src),
    'should use hrefs[0] for left link');
  assert.ok(/<a href=\{hrefs\[1\]\}>/.test(src) || /<a href=\{hrefs\[2\]\}>/.test(src),
    'should use hrefs array for links');
});

// ============================================================
// Word-level rendering tests
// ============================================================

test('render splits text into individual words', () => {
  const src = readSource();
  assert.ok(/text\.split\(\s*['"] ['"]\s*\)/.test(src),
    'should split text by space');
});

test('render wraps each word in a paragraph element', () => {
  const src = readSource();
  assert.ok(/<p key=/.test(src),
    'should wrap words in <p> with key');
});

// ============================================================
// Container and style tests
// ============================================================

test('render wraps table in div with overflow scroll', () => {
  const src = readSource();
  assert.ok(/overflow\s*:\s*['"]scroll['"]/.test(src),
    'should set overflow to scroll');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});
