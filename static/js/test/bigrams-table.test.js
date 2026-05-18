import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'bigrams-table.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Class structure tests
// ============================================================

test('source imports React', () => {
  assert.ok(/import\s+React\s+from\s+['"]react['"]/.test(source), 'should import React');
});

test('source declares BigramsTable as default export class extending React.Component', () => {
  assert.ok(/export\s+default\s+class\s+BigramsTable\s+extends\s+React\.Component/.test(source), 'should export default class BigramsTable extends React.Component');
});

test('source declares constructor with props param calling super', () => {
  assert.ok(/constructor\s*\(\s*props\s*\)\s*\{[\s\S]*super\s*\(\s*props\s*\)/.test(source), 'constructor should call super(props)');
});

// ============================================================
// Constructor state tests
// ============================================================

test('source initializes state.tags as new Map()', () => {
  assert.ok(/this\.state\s*=\s*\{[^}]*tags\s*:\s*new\s+Map\(\)/s.test(source), 'should initialize tags as new Map()');
});

test('source initializes state.tag_hash as empty string', () => {
  assert.ok(/tag_hash\s*:\s*[''][''"]/.test(source), 'should initialize tag_hash as empty string');
});

test('source initializes state.hoveredRow and hoveredCol as null', () => {
  assert.ok(/hoveredRow\s*:\s*null/.test(source), 'should initialize hoveredRow as null');
  assert.ok(/hoveredCol\s*:\s*null/.test(source), 'should initialize hoveredCol as null');
});

test('source binds updateTags in constructor', () => {
  assert.ok(/this\.updateTags\s*=\s*this\.updateTags\.bind\(this\)/.test(source), 'should bind updateTags');
});

test('source binds handleCellMouseEnter in constructor', () => {
  assert.ok(/this\.handleCellMouseEnter\s*=\s*this\.handleCellMouseEnter\.bind\(this\)/.test(source), 'should bind handleCellMouseEnter');
});

test('source binds handleCellMouseLeave in constructor', () => {
  assert.ok(/this\.handleCellMouseLeave\s*=\s*this\.handleCellMouseLeave\.bind\(this\)/.test(source), 'should bind handleCellMouseLeave');
});

// ============================================================
// Method declarations tests
// ============================================================

test('source declares updateTags method', () => {
  assert.ok(/updateTags\s*\(\s*state\s*\)/.test(source), 'should have updateTags method');
});

test('source declares handleCellMouseEnter method', () => {
  assert.ok(/handleCellMouseEnter\s*\(\s*row\s*,\s*col\s*\)/.test(source), 'should have handleCellMouseEnter method');
});

test('source declares handleCellMouseLeave method', () => {
  assert.ok(/handleCellMouseLeave\s*\(\s*\)/.test(source), 'should have handleCellMouseLeave method');
});

test('source declares componentDidMount method', () => {
  assert.ok(/componentDidMount\s*\(\s*\)/.test(source), 'should have componentDidMount method');
});

test('source declares componentWillUnmount method', () => {
  assert.ok(/componentWillUnmount\s*\(\s*\)/.test(source), 'should have componentWillUnmount method');
});

test('source declares processBigrams method', () => {
  assert.ok(/processBigrams\s*\(\s*\)/.test(source), 'should have processBigrams method');
});

test('source declares getCircleSize method', () => {
  assert.ok(/getCircleSize\s*\(\s*count\s*,\s*maxCount\s*\)/.test(source), 'should have getCircleSize method');
});

test('source declares getCircleColor method', () => {
  assert.ok(/getCircleColor\s*\(\s*count\s*,\s*maxCount\s*\)/.test(source), 'should have getCircleColor method');
});

test('source declares renderCircle method', () => {
  assert.ok(/renderCircle\s*\(\s*cellData\s*,\s*maxCount\s*\)/.test(source), 'should have renderCircle method');
});

test('source declares render method', () => {
  assert.ok(/\brender\s*\(\s*\)/.test(source), 'should have render method');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('componentDidMount binds TAGS_UPDATED event', () => {
  assert.ok(/this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.TAGS_UPDATED/.test(source), 'should bind TAGS_UPDATED');
  assert.ok(/this\.updateTags/.test(source), 'should bind updateTags handler');
});

test('componentWillUnmount unbinds TAGS_UPDATED event', () => {
  assert.ok(/this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.TAGS_UPDATED/.test(source), 'should unbind TAGS_UPDATED');
});

// ============================================================
// updateTags method tests
// ============================================================

test('updateTags calls this.setState with state argument', () => {
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(source), 'should call setState with state');
});

// ============================================================
// handleCellMouseEnter/Leave tests
// ============================================================

test('handleCellMouseEnter sets hoveredRow and hoveredCol via setState', () => {
  assert.ok(/this\.setState\s*\(\s*\{[\s\S]*hoveredRow\s*:\s*row/.test(source), 'should set hoveredRow');
  assert.ok(/hoveredCol\s*:\s*col/.test(source), 'should set hoveredCol');
});

test('handleCellMouseLeave clears hover state via setState', () => {
  assert.ok(/this\.setState\s*\(\s*\{[\s\S]*hoveredRow\s*:\s*null/.test(source), 'should clear hoveredRow');
  assert.ok(/hoveredCol\s*:\s*null/.test(source), 'should clear hoveredCol');
});

// ============================================================
// processBigrams structure tests
// ============================================================

test('processBigrams extracts tags from this.state', () => {
  assert.ok(/const\s*\{\s*tags\s*\}\s*=\s*this\.state/.test(source), 'should destructure tags from state');
});

test('processBigrams returns empty result when no tags', () => {
  assert.ok(/if\s*\(!tags\s*\|\|\s*!tags\.size\)/.test(source), 'should check for empty tags');
  assert.ok(/return\s*\{\s*firstWords\s*:\s*\[\]\s*,\s*secondWords\s*:\s*\[\]\s*,\s*matrix\s*:\s*\{\}\s*,\s*maxCount\s*:\s*0\s*\}/.test(source), 'should return empty result');
});

test('processBigrams initializes firstWordCounts, secondWordCounts, matrix, maxCount', () => {
  assert.ok(/const\s+firstWordCounts\s*=\s*\{/.test(source), 'should initialize firstWordCounts');
  assert.ok(/const\s+secondWordCounts\s*=\s*\{/.test(source), 'should initialize secondWordCounts');
  assert.ok(/const\s+matrix\s*=\s*\{/.test(source), 'should initialize matrix');
  assert.ok(/let\s+maxCount\s*=\s*0/.test(source), 'should initialize maxCount');
});

test('processBigrams tracks connections with Sets', () => {
  assert.ok(/firstWordConnections\[firstWord\]\s*=\s*new\s+Set\(\)/.test(source), 'should create Set for firstWord connections');
  assert.ok(/secondWordConnections\[secondWord\]\s*=\s*new\s+Set\(\)/.test(source), 'should create Set for secondWord connections');
});

test('processBigrams splits tag by space to get bigram parts', () => {
  assert.ok(/tagData\.tag\.split\s*\(\s*['"']\s+['"]\s*\)/.test(source), 'should split tag by space');
});

test('processBigrams checks bigramParts length >= 2', () => {
  assert.ok(/bigramParts\.length\s*>=\s*2/.test(source), 'should check at least 2 parts');
});

test('processBigrams accumulates first and second word counts', () => {
  assert.ok(/firstWordCounts\[firstWord\]\s*=\s*\(firstWordCounts\[firstWord\]\s*\|\|\s*0\)\s*\+\s*count/.test(source), 'should accumulate first word count');
  assert.ok(/secondWordCounts\[secondWord\]\s*=\s*\(secondWordCounts\[secondWord\]\s*\|\|\s*0\)\s*\+\s*count/.test(source), 'should accumulate second word count');
});

test('processBigrams stores cell data with count, tag, url', () => {
  assert.ok(/count\s*:\s*count/.test(source), 'should store count in matrix');
  assert.ok(/tag\s*:\s*tagData\.tag/.test(source), 'should store tag in matrix');
  assert.ok(/url\s*:\s*tagData\.url/.test(source), 'should store url in matrix');
});

test('processBigrams tracks maxCount', () => {
  assert.ok(/if\s*\(\s*count\s*>\s*maxCount\s*\)\s*\{[\s\S]*maxCount\s*=\s*count/.test(source), 'should update maxCount');
});

test('processBigrams sorts words by frequency descending', () => {
  assert.ok(/firstWordCounts\[b\]\s*-\s*firstWordCounts\[a\]/.test(source), 'should sort first words desc');
  assert.ok(/secondWordCounts\[b\]\s*-\s*secondWordCounts\[a\]/.test(source), 'should sort second words desc');
});

test('processBigrams uses iterative refinement with 3 iterations', () => {
  assert.ok(/const\s+iterations\s*=\s*3/.test(source), 'should use 3 iterations');
});

test('processBigrams refinement scores words by top connections', () => {
  assert.ok(/topSecondWords\s*=\s*new\s+Set\s*\([^)]*secondWords\.slice/.test(source), 'should create Set of top second words');
  assert.ok(/bTopConnections\s*-\s*aTopConnections/.test(source), 'should score by top connections');
});

// ============================================================
// getCircleSize tests
// ============================================================

test('getCircleSize defines minSize as 6', () => {
  assert.ok(/const\s+minSize\s*=\s*6/.test(source), 'minSize should be 6');
});

test('getCircleSize defines maxSize as 28', () => {
  assert.ok(/const\s+maxSize\s*=\s*28/.test(source), 'maxSize should be 28');
});

test('getCircleSize returns minSize when maxCount is 0', () => {
  assert.ok(/if\s*\(\s*maxCount\s*===\s*0\s*\)\s*return\s*minSize/.test(source), 'should return minSize for maxCount=0');
});

test('getCircleSize uses Math.sqrt for scaling', () => {
  assert.ok(/Math\.sqrt\s*\(\s*count\s*\/\s*maxCount\s*\)/.test(source), 'should use square root scaling');
});

test('getCircleSize formula: minSize + (maxSize - minSize) * normalized', () => {
  assert.ok(/minSize\s*\+\s*\(maxSize\s*-\s*minSize\)\s*\*\s*normalized/.test(source), 'should use linear interpolation with normalized sqrt value');
});

// ============================================================
// getCircleColor tests
// ============================================================

test('getCircleColor calculates ratio as count/maxCount', () => {
  assert.ok(/const\s+ratio\s*=\s*count\s*\/\s*maxCount/.test(source), 'should calculate ratio');
});

test('getCircleColor returns #3498db (blue) for ratio > 0.7', () => {
  assert.ok(/ratio\s*>\s*0\.7/.test(source), 'should check > 0.7');
  assert.ok(/return\s*['"]#3498db['"]/.test(source), 'should return blue for high frequency');
});

test('getCircleColor returns #e67e22 (orange) for ratio > 0.4', () => {
  assert.ok(/ratio\s*>\s*0\.4/.test(source), 'should check > 0.4');
  assert.ok(/return\s*['"]#e67e22['"]/.test(source), 'should return orange for medium frequency');
});

test('getCircleColor returns #f1c40f (yellow) for ratio > 0.2', () => {
  assert.ok(/ratio\s*>\s*0\.2/.test(source), 'should check > 0.2');
  assert.ok(/return\s*['"]#f1c40f['"]/.test(source), 'should return yellow for low-medium frequency');
});

test('getCircleColor returns #e74c3c (red) for low ratio', () => {
  assert.ok(/return\s*['"]#e74c3c['"]/.test(source), 'should return red for low frequency');
});

// ============================================================
// renderCircle tests
// ============================================================

test('renderCircle returns null when cellData is falsy', () => {
  assert.ok(/if\s*\(\s*!cellData\s*\)\s*return\s*null/.test(source), 'should return null for empty cell');
});

test('renderCircle calls getCircleSize and getCircleColor', () => {
  assert.ok(/this\.getCircleSize\s*\(\s*cellData\.count\s*,\s*maxCount\s*\)/.test(source), 'should call getCircleSize');
  assert.ok(/this\.getCircleColor\s*\(\s*cellData\.count\s*,\s*maxCount\s*\)/.test(source), 'should call getCircleColor');
});

test('renderCircle conditionally shows inner circle when count > 30% of max', () => {
  assert.ok(/cellData\.count\s*>\s*maxCount\s*\*\s*0\.3/.test(source), 'should check 30% threshold for inner circle');
});

test('renderCircle conditionally shows center circle when count > 60% of max', () => {
  assert.ok(/cellData\.count\s*>\s*maxCount\s*\*\s*0\.6/.test(source), 'should check 60% threshold for center circle');
});

test('renderCircle creates anchor with bigram-cell-link class', () => {
  assert.ok(/className\s*=\s*['"]bigram-cell-link['"]/.test(source), 'should set bigram-cell-link class');
});

test('renderCircle sets href from cellData.url', () => {
  assert.ok(/href\s*=\s*\{cellData\.url\}/.test(source), 'should use cellData.url for href');
});

test('renderCircle sets title with tag and count', () => {
  assert.ok(/title\s*=/.test(source), 'should set title');
  assert.ok(/\$\{cellData\.tag\}/.test(source), 'title should include tag');
  assert.ok(/\$\{cellData\.count\}/.test(source), 'title should include count');
});

test('renderCircle creates SVG with bigram-circle-svg class', () => {
  assert.ok(/className\s*=\s*['"]bigram-circle-svg['"]/.test(source), 'should set SVG class');
});

test('renderCircle creates circles with bigram-circle, bigram-circle-inner, bigram-circle-center classes', () => {
  assert.ok(/className\s*=\s*['"]bigram-circle['"]/.test(source), 'should set bigram-circle class');
  assert.ok(/className\s*=\s*['"]bigram-circle-inner['"]/.test(source), 'should set inner class');
  assert.ok(/className\s*=\s*['"]bigram-circle-center['"]/.test(source), 'should set center class');
});

// ============================================================
// render method tests
// ============================================================

test('render destructures processBigrams result', () => {
  assert.ok(/const\s*\{\s*firstWords\s*,\s*secondWords\s*,\s*matrix\s*,\s*maxCount\s*\}\s*=\s*this\.processBigrams\(\)/.test(source), 'should destructure from processBigrams');
});

test('render destructures hoveredRow and hoveredCol from state', () => {
  assert.ok(/const\s*\{\s*hoveredRow\s*,\s*hoveredCol\s*\}\s*=\s*this\.state/.test(source), 'should destructure hover state');
});

test('render returns <p>No bigrams data available</p> when no data', () => {
  assert.ok(/<p>No bigrams data available<\/p>/.test(source), 'should show no data message');
});

test('render creates bigrams-table-container div', () => {
  assert.ok(/className\s*=\s*['"]bigrams-table-container['"]/.test(source), 'should set container class');
});

test('render creates legend with bigrams-table-legend class', () => {
  assert.ok(/className\s*=\s*['"]bigrams-table-legend['"]/.test(source), 'should set legend class');
});

test('render legend shows Frequency Legend title', () => {
  assert.ok(/<h4>Frequency Legend<\/h4>/.test(source), 'should show Frequency Legend title');
});

test('render legend shows High, Medium, Low-Medium, Low items with color circles', () => {
  assert.ok(/High/.test(source), 'should show High legend');
  assert.ok(/Medium/.test(source), 'should show Medium legend');
  assert.ok(/Low-Medium/.test(source), 'should show Low-Medium legend');
  assert.ok(/Low/.test(source), 'should show Low legend');
});

test('render creates bigrams-table-scroll wrapper', () => {
  assert.ok(/className\s*=\s*['"]bigrams-table-scroll['"]/.test(source), 'should set scroll wrapper class');
});

test('render creates table with bigrams-table class', () => {
  assert.ok(/className\s*=\s*['"]bigrams-table['"]/.test(source), 'should set table class');
});

test('render creates corner cell with bigrams-corner-cell class', () => {
  assert.ok(/className\s*=\s*['"]bigrams-corner-cell['"]/.test(source), 'should set corner cell class');
});

test('render creates column headers with bigrams-col-header class', () => {
  assert.ok(/className\s*=.*bigrams-col-header/.test(source), 'should set col header class');
});

test('render creates row headers with bigrams-row-header class', () => {
  assert.ok(/className\s*=.*bigrams-row-header/.test(source), 'should set row header class');
});

test('render creates cells with bigrams-cell class', () => {
  assert.ok(/className\s*=.*bigrams-cell/.test(source), 'should set cell class');
});

test('render adds highlighted class based on hover state', () => {
  assert.ok(/isHighlighted/.test(source), 'should compute isHighlighted');
  assert.ok(/highlighted/.test(source), 'should use highlighted class');
  assert.ok(/hoveredRow\s*===\s*firstWord/.test(source), 'should check hoveredRow');
  assert.ok(/hoveredCol\s*===\s*secondWord/.test(source), 'should check hoveredCol');
});

test('render links headers to /tag-info/ endpoint', () => {
  assert.ok(/\/tag-info\/\$\{/.test(source), 'should link to /tag-info/');
  assert.ok(/encodeURIComponent/.test(source), 'should encode the word');
});

// ============================================================
// Extract and test pure functions
// ============================================================

/**
 * Extract a class method body from source.
 */
function extractMethodBody(src, name) {
  const idx = src.indexOf(`${name}(`);
  if (idx === -1) throw new Error(`Method ${name} not found`);

  const parenOpen = src.indexOf('(', idx + name.length);
  let depth = 0;
  let parenClose = -1;
  for (let i = parenOpen; i < src.length; i += 1) {
    if (src[i] === '(') depth += 1;
    else if (src[i] === ')') {
      depth -= 1;
      if (depth === 0) { parenClose = i; break; }
    }
  }

  const bodyStart = src.indexOf('{', parenClose);
  let braceDepth = 0;
  let end = bodyStart;
  for (; end < src.length; end += 1) {
    if (src[end] === '{') braceDepth += 1;
    else if (src[end] === '}') {
      braceDepth -= 1;
      if (braceDepth === 0) break;
    }
  }

  return src.slice(bodyStart + 1, end);
}

test('getCircleSize correctly computes size for max count', () => {
  const body = extractMethodBody(source, 'getCircleSize');
  const fn = new Function('count', 'maxCount', `
    function getCircleSize(count, maxCount) { ${body} }
    return getCircleSize(count, maxCount);
  `);
  assert.equal(fn(100, 100), 28);
  assert.equal(fn(0, 100), 6);
  assert.equal(fn(5, 0), 6);
});

test('getCircleSize uses square root scaling (non-linear)', () => {
  const body = extractMethodBody(source, 'getCircleSize');
  const fn = new Function('count', 'maxCount', `
    function getCircleSize(count, maxCount) { ${body} }
    return getCircleSize(count, maxCount);
  `);
  // Sqrt scaling: quarter count should give more than quarter size
  const quarter = fn(25, 100);
  const half = fn(50, 100);
  const full = fn(100, 100);
  assert.ok(half - quarter < full - half, 'sqrt scaling means differences decrease as count increases');
});

test('getCircleColor returns correct colors for ratio tiers', () => {
  const body = extractMethodBody(source, 'getCircleColor');
  const fn = new Function('count', 'maxCount', `
    function getCircleColor(count, maxCount) { ${body} }
    return getCircleColor(count, maxCount);
  `);
  assert.equal(fn(8, 10), '#3498db');
  assert.equal(fn(10, 10), '#3498db');
  assert.equal(fn(5, 10), '#e67e22');
  assert.equal(fn(3, 10), '#f1c40f');
  assert.equal(fn(1, 10), '#e74c3c');
});
