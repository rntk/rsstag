import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'topic-flow.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Class structure tests
// ============================================================

test('source declares TopicFlow as a default export class', () => {
  assert.ok(
    /export\s+default\s+class\s+TopicFlow\b/.test(source),
    'should export default class TopicFlow'
  );
});

test('source declares constructor with data and containerSelector params', () => {
  assert.ok(
    /constructor\s*\(\s*data\s*,\s*containerSelector\s*\)/.test(source),
    'constructor should accept data and containerSelector'
  );
});

test('source stores data and containerSelector on this', () => {
  assert.ok(/this\.data\s*=\s*data/.test(source), 'should store data');
  assert.ok(
    /this\.containerSelector\s*=\s*containerSelector/.test(source),
    'should store containerSelector'
  );
});

// ============================================================
// Config tests
// ============================================================

test('source initializes config object with width 1200', () => {
  assert.ok(/width\s*:\s*1200/.test(source), 'config.width should be 1200');
});

test('source initializes config with height 1000', () => {
  assert.ok(/height\s*:\s*1000/.test(source), 'config.height should be 1000');
});

test('source initializes config margin with top, right, bottom, left', () => {
  assert.ok(/margin\s*:\s*\{[^}]*top\s*:\s*60/.test(source), 'margin.top should be 60');
  assert.ok(/right\s*:\s*300/.test(source), 'margin.right should be 300');
  assert.ok(/bottom\s*:\s*60/.test(source), 'margin.bottom should be 60');
  assert.ok(/left\s*:\s*300/.test(source), 'margin.left should be 300');
});

test('source sets stepHeight to 80', () => {
  assert.ok(/stepHeight\s*:\s*80/.test(source), 'stepHeight should be 80');
});

test('source sets trunkColor to #800040', () => {
  assert.ok(/trunkColor\s*:\s*['"]#800040['"]/.test(source), 'trunkColor should be #800040');
});

test('source sets fontFamily to sans-serif', () => {
  assert.ok(/fontFamily\s*:\s*['"]sans-serif['"]/.test(source), 'fontFamily should be sans-serif');
});

test('source sets curveRadius to 400', () => {
  assert.ok(/curveRadius\s*:\s*400/.test(source), 'curveRadius should be 400');
});

test('source sets minCurveRadius to 50', () => {
  assert.ok(/minCurveRadius\s*:\s*50/.test(source), 'minCurveRadius should be 50');
});

// ============================================================
// Method declarations tests
// ============================================================

test('source declares calculateValue method', () => {
  assert.ok(/\bcalculateValue\s*\(\s*node\s*\)/.test(source), 'should have calculateValue method');
});

test('source declares init method', () => {
  assert.ok(/\binit\s*\(\s*\)/.test(source), 'should have init method');
});

test('source declares render method', () => {
  assert.ok(/\brender\s*\(\s*\)/.test(source), 'should have render method');
});

// ============================================================
// calculateValue logic tests
// ============================================================

test('calculateValue returns node.value for leaf nodes without children', () => {
  const match = source.match(
    /calculateValue\s*\(node\)\s*\{[\s\S]*?if\s*\(!node\.children[^}]*return\s+node\.value\s*\|\|\s*0/
  );
  assert.ok(match, 'should return node.value || 0 for leaf nodes');
});

test('calculateValue recurses and sums children values', () => {
  assert.ok(
    /inputSum\s*\+=\s*child\.value/.test(source),
    'should accumulate inputSum from children'
  );
  assert.ok(/return\s+inputSum/.test(source), 'should return inputSum (sum of children)');
});

test('calculateValue assigns child.value recursively if undefined', () => {
  assert.ok(
    /child\.value\s*=\s*this\.calculateValue\(child\)/.test(source),
    'should recursively calculate child.value'
  );
});

// ============================================================
// init logic tests
// ============================================================

test('init calls render', () => {
  assert.ok(/this\.render\(\)/.test(source), 'init should call render');
});

test('init registers window resize listener that calls render', () => {
  assert.ok(
    /window\.addEventListener\s*\(\s*['"]resize['"]/.test(source),
    'should add resize listener'
  );
  assert.ok(
    /addEventListener.*resize.*=>.*this\.render\(\)/s.test(source),
    'resize handler should call render'
  );
});

// ============================================================
// render structure tests
// ============================================================

test('render uses document.querySelector with containerSelector', () => {
  assert.ok(
    /document\.querySelector\s*\(\s*this\.containerSelector\s*\)/.test(source),
    'should use querySelector with containerSelector'
  );
});

test('render clears container innerHTML', () => {
  assert.ok(/container\.innerHTML\s*=\s*['"]['"]/.test(source), 'should clear container innerHTML');
});

test('render returns early when container is not found', () => {
  assert.ok(/if\s*\(!container\)\s*return/.test(source), 'should return early if no container');
});

test('render calculates required height from child count and stepHeight', () => {
  assert.ok(
    /childCount\s*\*\s*stepHeight/.test(source),
    'should multiply childCount by stepHeight'
  );
});

test('render uses Math.max with config.height for final height', () => {
  assert.ok(
    /Math\.max\s*\(\s*this\.config\.height/.test(source),
    'should use Math.max with config.height'
  );
});

// ============================================================
// SVG and D3 structure tests
// ============================================================

test('render creates SVG with d3.select and append', () => {
  assert.ok(
    /d3\s*\.\s*select\s*\(\s*container\s*\)/.test(source),
    'should use d3.select(container)'
  );
  assert.ok(/\.append\s*\(\s*['"]svg['"]\s*\)/.test(source), 'should append svg element');
});

test('render sets SVG viewBox attribute', () => {
  assert.ok(/\.attr\s*\(\s*['"]viewBox['"]/.test(source), 'should set viewBox attribute');
});

test('render sets preserveAspectRatio to xMidYMid meet', () => {
  assert.ok(
    /preserveAspectRatio['"]\s*,\s*['"]xMidYMid\s+meet['"]/.test(source),
    'should set preserveAspectRatio'
  );
});

test('render sets SVG background to white', () => {
  assert.ok(
    /\.style\s*\(\s*['"]background['"]\s*,\s*['"]#fff['"]\s*\)/.test(source),
    'should set background to #fff'
  );
});

// ============================================================
// Zoom behavior tests
// ============================================================

test('render creates d3 zoom with scaleExtent [0.1, 5]', () => {
  assert.ok(/d3\s*\.\s*zoom\(\)/.test(source), 'should create d3 zoom');
  assert.ok(
    /\.scaleExtent\s*\(\s*\[\s*0\.1\s*,\s*5\s*\]\s*\)/.test(source),
    'scaleExtent should be [0.1, 5]'
  );
});

test('render stores zoom reference as this.zoom', () => {
  assert.ok(/this\.zoom\s*=\s*zoom/.test(source), 'should store zoom as this.zoom');
});

// ============================================================
// Side assignment and sorting tests
// ============================================================

test('render filters children by side === left', () => {
  assert.ok(
    /\.filter\s*\(\s*\(\s*c\s*\)\s*=>\s*c\.side\s*===\s*['"]left['"]\s*\)/.test(source),
    'should filter left children'
  );
});

test('render reverses rights for stacking order', () => {
  assert.ok(
    /\[\s*\.\.\.\s*rights\s*\]\s*\.reverse\(\)/.test(source),
    'should reverse rights array'
  );
});

test('render sorts children by value descending', () => {
  assert.ok(
    /\.sort\s*\(\s*\(\s*a\s*,\s*b\s*\)\s*=>\s*b\.value\s*-\s*a\.value\s*\)/.test(source),
    'should sort children by value desc'
  );
});

// ============================================================
// Layout geometry tests
// ============================================================

test('render calculates maxTrunkWidth with Math.min(300, ...)', () => {
  assert.ok(/Math\.min\s*\(\s*300/.test(source), 'maxTrunkWidth should cap at 300');
  assert.ok(/drawW\s*\*\s*0\.6/.test(source), 'should use 60% of drawW');
});

test('render assigns _width and _x to children', () => {
  assert.ok(
    /child\._width\s*=\s*child\.value\s*\*\s*scale/.test(source),
    'should assign _width proportional to value'
  );
  assert.ok(/child\._x\s*=\s*currentStackX/.test(source), 'should assign _x from currentStackX');
});

test('render calculates scale from maxTrunkWidth / this.data.value', () => {
  assert.ok(
    /maxTrunkWidth\s*\/\s*this\.data\.value/.test(source),
    'scale should be maxTrunkWidth / data.value'
  );
});

// ============================================================
// Header text tests
// ============================================================

test('render creates header text with data name and value', () => {
  assert.ok(/\$\{this\.data\.name\}\s*\(/.test(source), 'header should include data.name');
  assert.ok(/\$\{this\.data\.value\}/.test(source), 'header should include data.value');
});

test('render sets header font-family to config.fontFamily', () => {
  assert.ok(
    /\.style\s*\(\s*['"]font-family['"]\s*,\s*this\.config\.fontFamily/.test(source),
    'header should use config.fontFamily'
  );
});

// ============================================================
// Branch geometry tests
// ============================================================

test('render creates d3.path for each branch', () => {
  assert.ok(/d3\.path\(\)/.test(source), 'should create d3.path for branch geometry');
});

test('left branch logic includes arc from angle 0 to Math.PI/2', () => {
  const leftBranch = source.match(
    /if\s*\(isLeft\)\s*\{[\s\S]*?path\.arc\s*\([^)]*0\s*,\s*Math\.PI\s*\/\s*2\s*\)/
  );
  assert.ok(leftBranch, 'left branch should have arc from 0 to PI/2');
});

test('right branch logic includes arc from Math.PI to Math.PI/2', () => {
  const rightBranch = source.match(
    /path\.arc\s*\([^)]*Math\.PI\s*,\s*Math\.PI\s*\/\s*2\s*,\s*true\s*\)/
  );
  assert.ok(rightBranch, 'right branch should have arc from PI to PI/2');
});

test('render uses path.toString() for SVG path d attribute', () => {
  assert.ok(
    /\.attr\s*\(\s*['"]d['"]\s*,\s*path\.toString\(\)\s*\)/.test(source),
    'should use path.toString() for d attribute'
  );
});

// ============================================================
// Hover/opacity tests
// ============================================================

test('render sets initial path opacity to 0.85', () => {
  assert.ok(
    /\.attr\s*\(\s*['"]opacity['"]\s*,\s*0\.85\s*\)/.test(source),
    'should set opacity to 0.85'
  );
});

test('render adds mouseenter handler that sets opacity to 1', () => {
  assert.ok(/['"]mouseenter['"]/.test(source), 'should have mouseenter event');
  assert.ok(
    /\.attr\s*\(\s*['"]opacity['"]\s*,\s*1\s*\)/.test(source),
    'mouseenter should set opacity to 1'
  );
});

test('render adds mouseleave handler that resets opacity to 0.85', () => {
  assert.ok(/['"]mouseleave['"]/.test(source), 'should have mouseleave event');
});

// ============================================================
// Label positioning tests
// ============================================================

test('render positions left labels at x=50', () => {
  assert.ok(/isLeft\s*\?\s*50/.test(source), 'left labelX should be 50');
});

test('render positions right labels at width-50', () => {
  assert.ok(/width\s*-\s*50/.test(source), 'right labelX should be width - 50');
});

test('render sets label text-anchor to end for left, start for right', () => {
  assert.ok(/['"]text-anchor['"]\s*,\s*['"]end['"]/.test(source), 'should have text-anchor end');
  assert.ok(
    /['"]text-anchor['"]\s*,\s*['"]start['"]/.test(source),
    'should have text-anchor start'
  );
});

test('render uses dominant-baseline middle for labels', () => {
  assert.ok(
    /['"]dominant-baseline['"]\s*,\s*['"]middle['"]/.test(source),
    'should set dominant-baseline to middle'
  );
});

// ============================================================
// Alternating side assignment tests
// ============================================================

test('source assigns alternating sides when child.side is not present', () => {
  assert.ok(
    /i\s*%\s*2\s*===\s*0\s*\?\s*['"]left['"]\s*:\s*['"]right['"]/.test(source),
    'should alternate left/right by index'
  );
});

// ============================================================
// Stack order tests
// ============================================================

test('source builds stackOrder as [...lefts, ...rightsStackOrder]', () => {
  assert.ok(
    /\[\s*\.\.\.\s*lefts\s*,\s*\.\.\.\s*rightsStackOrder\s*\]/.test(source),
    'stackOrder should be lefts followed by reversed rights'
  );
});

test('source assigns centerX from margin.left + drawW / 2', () => {
  assert.ok(
    /centerX\s*=\s*margin\.left\s*\+\s*drawW\s*\/\s*2/.test(source),
    'centerX should be left margin + half draw width'
  );
});
