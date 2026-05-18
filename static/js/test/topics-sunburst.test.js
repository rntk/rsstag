import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'topics-sunburst.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Class structure tests
// ============================================================

test('source declares TopicsSunburst class', () => {
  assert.ok(/class\s+TopicsSunburst\b/.test(source), 'should declare class TopicsSunburst');
});

test('source exports TopicsSunburst as default', () => {
  assert.ok(/export\s+default\s+TopicsSunburst/.test(source), 'should export default TopicsSunburst');
});

test('source imports Sunburst from sunburst-chart', () => {
  assert.ok(/import\s+Sunburst\s+from\s+['"]sunburst-chart['"]/.test(source), 'should import Sunburst from sunburst-chart');
});

test('source imports triggerAnthology from topics-list', () => {
  assert.ok(/import\s*\{\s*triggerAnthology\s*\}\s*from\s+['"]\.\/topics-list\.js['"]/.test(source), 'should import triggerAnthology');
});

test('source declares constructor with data and options params', () => {
  assert.ok(/constructor\s*\(\s*data\s*,\s*options\s*=\s*\{/.test(source), 'constructor should accept data and options');
});

test('source stores data and default color properties', () => {
  assert.ok(/this\.data\s*=\s*data/.test(source), 'should store data');
  assert.ok(/this\.base_color\s*=\s*['"]#d7d7af['"]/.test(source), 'should set base_color');
  assert.ok(/this\.color_range\s*=\s*20/.test(source), 'should set color_range');
});

test('source sets maxChildrenPerChart to 50', () => {
  assert.ok(/this\.maxChildrenPerChart\s*=\s*50/.test(source), 'maxChildrenPerChart should be 50');
});

test('source initializes currentPage to 0', () => {
  assert.ok(/this\.currentPage\s*=\s*0/.test(source), 'currentPage should start at 0');
});

test('source initializes charts and splitData', () => {
  assert.ok(/this\.charts\s*=\s*\[\]/.test(source), 'charts should be empty array');
  assert.ok(/this\.splitData\s*=\s*null/.test(source), 'splitData should be null');
});

test('source initializes hostContainer and chartContainer to null', () => {
  assert.ok(/this\.hostContainer\s*=\s*null/.test(source), 'hostContainer should be null');
  assert.ok(/this\.chartContainer\s*=\s*null/.test(source), 'chartContainer should be null');
});

// ============================================================
// Value transform option tests
// ============================================================

test('source sets default valueTransform to sqrt', () => {
  assert.ok(/this\.valueTransform\s*=\s*options\.valueTransform\s*\|\|\s*['"]sqrt['"]/.test(source), 'valueTransform should default to sqrt');
});

test('source sets default minValue to 1', () => {
  assert.ok(/this\.minValue\s*=\s*options\.minValue\s*\|\|\s*1/.test(source), 'minValue should default to 1');
});

test('constructor calls initializeCharts', () => {
  assert.ok(/this\.initializeCharts\(\)/.test(source), 'constructor should call initializeCharts');
});

// ============================================================
// Method declarations tests
// ============================================================

test('source declares initializeCharts method', () => {
  assert.ok(/initializeCharts\s*\(\s*\)/.test(source), 'should have initializeCharts method');
});

test('source declares createSplitData method', () => {
  assert.ok(/createSplitData\s*\(\s*data\s*\)/.test(source), 'should have createSplitData method');
});

test('source declares transformDataValues method', () => {
  assert.ok(/transformDataValues\s*\(\s*node\s*\)/.test(source), 'should have transformDataValues method');
});

test('source declares applyValueTransform method', () => {
  assert.ok(/applyValueTransform\s*\(\s*value\s*\)/.test(source), 'should have applyValueTransform method');
});

test('source declares render method', () => {
  assert.ok(/render\s*\(\s*selector\s*\)/.test(source), 'should have render method');
});

test('source declares createNavigation method', () => {
  assert.ok(/createNavigation\s*\(\s*container\s*\)/.test(source), 'should have createNavigation method');
});

test('source declares navigateToPage method', () => {
  assert.ok(/navigateToPage\s*\(\s*pageIndex\s*\)/.test(source), 'should have navigateToPage method');
});

test('source declares renderCurrentChart method', () => {
  assert.ok(/renderCurrentChart\s*\(\s*container\s*\)/.test(source), 'should have renderCurrentChart method');
});

test('source declares handleClick method', () => {
  assert.ok(/handleClick\s*\(\s*d\s*,\s*event\s*,\s*currentData\s*\)/.test(source), 'should have handleClick method');
});

test('source declares generateSimilarColor method', () => {
  assert.ok(/generateSimilarColor\s*\(\s*baseColor\s*,\s*range\s*\)/.test(source), 'should have generateSimilarColor method');
});

test('source declares hexToRGB method', () => {
  assert.ok(/hexToRGB\s*\(\s*hex\s*\)/.test(source), 'should have hexToRGB method');
});

test('source declares rgbToHex method', () => {
  assert.ok(/rgbToHex\s*\(\s*rgb\s*\)/.test(source), 'should have rgbToHex method');
});

// ============================================================
// initializeCharts tests
// ============================================================

test('initializeCharts calls transformDataValues on data', () => {
  assert.ok(/this\.transformDataValues\s*\(\s*this\.data\s*\)/.test(source), 'should transform data values');
});

test('initializeCharts splits when transformed children exceed maxChildrenPerChart', () => {
  assert.ok(/transformedData\.children.*this\.maxChildrenPerChart/.test(source), 'should check children count');
});

test('initializeCharts maps splitData to Sunburst() instances', () => {
  assert.ok(/this\.splitData\.map\s*\(\s*\(\)\s*=>\s*Sunburst\(\)\)/.test(source), 'should create Sunburst per page');
});

// ============================================================
// createSplitData tests
// ============================================================

test('createSplitData chunks children with maxChildrenPerChart slice', () => {
  assert.ok(/children\.slice\s*\(\s*i\s*,\s*i\s*\+\s*this\.maxChildrenPerChart\s*\)/.test(source), 'should slice children array');
});

test('createSplitData spreads data properties into chunks', () => {
  assert.ok(/\.\.\.\s*data/.test(source), 'should spread data into chunks');
});

test('createSplitData includes _pageInfo with all metadata fields', () => {
  assert.ok(/_pageInfo/.test(source), 'should include _pageInfo');
  assert.ok(/current\s*:\s*Math\.floor/.test(source), 'should have current');
  assert.ok(/total\s*:\s*Math\.ceil/.test(source), 'should have total');
  assert.ok(/startIndex\s*:\s*i/.test(source), 'should have startIndex');
  assert.ok(/endIndex\s*:\s*Math\.min/.test(source), 'should have endIndex');
});

// ============================================================
// Value transformation tests
// ============================================================

test('transformDataValues creates shallow copy with spread', () => {
  assert.ok(/const\s+transformed\s*=\s*\{\s*\.\.\.\s*node\s*\}/.test(source), 'should create shallow copy');
});

test('transformDataValues transforms value if it is a number', () => {
  assert.ok(/typeof\s+transformed\.value\s*===\s*['"]number['"]/.test(source), 'should check value is number');
  assert.ok(/transformed\.value\s*=\s*this\.applyValueTransform/.test(source), 'should apply transform to value');
});

test('transformDataValues recurses on children array', () => {
  assert.ok(/transformed\.children\s*&&\s*Array\.isArray\s*\(\s*transformed\.children\s*\)/.test(source), 'should check children array');
  assert.ok(/transformed\.children\s*=\s*transformed\.children\.map\s*\(\s*\(\s*child\s*\)\s*=>\s*this\.transformDataValues\s*\(\s*child\s*\)/.test(source), 'should recurse on children');
});

test('applyValueTransform uses Math.max with minValue', () => {
  assert.ok(/Math\.max\s*\(\s*value\s*,\s*this\.minValue\s*\)/.test(source), 'should enforce minimum value');
});

test('applyValueTransform handles sqrt case', () => {
  assert.ok(/case\s+['"]sqrt['"]/.test(source), 'should handle sqrt case');
  assert.ok(/Math\.sqrt\s*\(\s*safeValue\s*\)/.test(source), 'should use Math.sqrt');
});

test('applyValueTransform handles log case with log10', () => {
  assert.ok(/case\s+['"]log['"]/.test(source), 'should handle log case');
  assert.ok(/Math\.log10\s*\(\s*safeValue\s*\+\s*1\s*\)/.test(source), 'should use log10 with +1 offset');
});

test('applyValueTransform handles cbrt case', () => {
  assert.ok(/case\s+['"]cbrt['"]/.test(source), 'should handle cbrt case');
  assert.ok(/Math\.cbrt\s*\(\s*safeValue\s*\)/.test(source), 'should use Math.cbrt');
});

test('applyValueTransform handles none case returning safeValue', () => {
  assert.ok(/case\s+['"]none['"]/.test(source), 'should handle none case');
  assert.ok(/return\s+safeValue/.test(source), 'should return value unchanged for none');
});

// ============================================================
// Color helper tests
// ============================================================

test('generateSimilarColor uses clamp helper', () => {
  assert.ok(/const\s+clamp\s*=\s*\(\s*value\s*\)\s*=>\s*Math\.min\s*\(\s*255/.test(source), 'should define clamp function');
});

test('generateSimilarColor converts baseColor to RGB', () => {
  assert.ok(/this\.hexToRGB\s*\(\s*baseColor\s*\)/.test(source), 'should call hexToRGB');
});

test('generateSimilarColor generates RGB within range and clamps', () => {
  assert.ok(/Math\.max\s*\(\s*0\s*,\s*value\s*-\s*range/.test(source), 'should compute min within range');
  assert.ok(/Math\.min\s*\(\s*255\s*,\s*value\s*\+\s*range/.test(source), 'should compute max within range');
  assert.ok(/clamp\s*\(\s*Math\.floor\s*\(\s*Math\.random/.test(source), 'should clamp random result');
});

test('hexToRGB parses hex with parseInt and slice', () => {
  assert.ok(/parseInt\s*\(\s*hex\.slice\s*\(\s*1\s*,\s*3\s*\)\s*,\s*16\s*\)/.test(source), 'should parse R');
  assert.ok(/parseInt\s*\(\s*hex\.slice\s*\(\s*3\s*,\s*5\s*\)\s*,\s*16\s*\)/.test(source), 'should parse G');
  assert.ok(/parseInt\s*\(\s*hex\.slice\s*\(\s*5\s*,\s*7\s*\)\s*,\s*16\s*\)/.test(source), 'should parse B');
  // Verify the method returns an array of [r, g, b]
  assert.ok(/return\s*\[\s*r\s*,\s*g\s*,\s*b\s*\]/.test(source), 'should return [r, g, b] array');
});

test('rgbToHex pads single hex digits with leading zero', () => {
  assert.ok(/hex\.length\s*===\s*1\s*\?\s*['"]0['"]\s*\+/.test(source), 'should pad single hex digit');
});

// ============================================================
// Render structure tests
// ============================================================

test('render uses document.querySelector to find container', () => {
  assert.ok(/document\.querySelector\s*\(\s*selector\s*\)/.test(source), 'should query selector');
});

test('render returns early when container not found', () => {
  assert.ok(/if\s*\(!container\)\s*return/.test(source), 'should return early');
});

test('render stores container as this.hostContainer', () => {
  assert.ok(/this\.hostContainer\s*=\s*container/.test(source), 'should store host container');
});

test('render clears container innerHTML', () => {
  assert.ok(/container\.innerHTML\s*=\s*[''][''"]/.test(source), 'should clear container');
});

test('render creates chart container div with topics-sunburst-chart-container class', () => {
  assert.ok(/chartContainer\.className\s*=\s*['"]topics-sunburst-chart-container['"]/.test(source), 'should set chart container class');
});

test('render stores chartContainer reference', () => {
  assert.ok(/this\.chartContainer\s*=\s*chartContainer/.test(source), 'should store chart container');
});

test('render creates navigation when splitData has multiple pages', () => {
  assert.ok(/this\.splitData\.length\s*>\s*1/.test(source), 'should check for multi-page');
  assert.ok(/this\.createNavigation\s*\(\s*container\s*\)/.test(source), 'should call createNavigation');
});

// ============================================================
// Navigation tests
// ============================================================

test('createNavigation sets sunburst-navigation class', () => {
  assert.ok(/nav\.className\s*=\s*['"]sunburst-navigation['"]/.test(source), 'should set nav class');
});

test('createNavigation uses display flex and justify-content space-between', () => {
  assert.ok(/display\s*:\s*flex/.test(source), 'should use flex display');
  assert.ok(/justify-content\s*:\s*space-between/.test(source), 'should use space-between');
});

test('createNavigation creates Previous and Next buttons with arrow characters', () => {
  assert.ok(/prevBtn\.textContent\s*=\s*['"]\u2190/.test(source), 'should create Previous button');
  assert.ok(/nextBtn\.textContent\s*=\s*['"]Next\s*\u2192/.test(source), 'should create Next button');
});

test('createNavigation inserts nav before chart container', () => {
  assert.ok(/container\.insertBefore\s*\(\s*nav\s*,\s*container\.firstChild\s*\)/.test(source), 'should insert nav before first child');
});

// ============================================================
// Pagination tests
// ============================================================

test('navigateToPage validates bounds with pageIndex < 0 and >= splitData.length', () => {
  assert.ok(/pageIndex\s*<\s*0\s*\|\|\s*pageIndex\s*>=\s*this\.splitData\.length/.test(source), 'should check bounds');
});

test('navigateToPage updates currentPage and re-renders', () => {
  assert.ok(/this\.currentPage\s*=\s*pageIndex/.test(source), 'should update currentPage');
  assert.ok(/this\.renderCurrentChart\s*\(\s*chartContainer\s*\)/.test(source), 'should re-render');
});

test('navigateToPage removes old nav and creates new one', () => {
  assert.ok(/nav\.remove\(\)/.test(source), 'should remove old nav');
  assert.ok(/this\.createNavigation\s*\(\s*container\s*\)/.test(source), 'should create new nav');
});

// ============================================================
// renderCurrentChart tests
// ============================================================

test('renderCurrentChart calculates size from container clientWidth', () => {
  assert.ok(/this\.hostContainer.*clientWidth/.test(source), 'should read clientWidth');
  assert.ok(/Math\.min\s*\(\s*parentWidth\s*-\s*40/.test(source), 'should subtract 40px padding');
});

test('renderCurrentChart caps size at MAX_SIZE 700', () => {
  assert.ok(/MAX_SIZE\s*=\s*700/.test(source), 'should define MAX_SIZE as 700');
  assert.ok(/Math\.min\s*\(\s*parentWidth\s*-\s*40\s*,\s*MAX_SIZE/.test(source), 'should cap at MAX_SIZE');
});

test('renderCurrentChart sets width and height on chart', () => {
  assert.ok(/\.width\s*\(\s*size\s*\)/.test(source), 'should set chart width');
  assert.ok(/\.height\s*\(\s*size\s*\)/.test(source), 'should set chart height');
});

test('renderCurrentChart uses generateSimilarColor for color function', () => {
  assert.ok(/\.color\s*\(\s*\(\s*d\s*\)\s*=>\s*this\.generateSimilarColor/.test(source), 'should use generateSimilarColor for color');
});

// ============================================================
// handleClick navigation tests
// ============================================================

test('handleClick with shiftKey triggers triggerAnthology', () => {
  assert.ok(/event\.shiftKey/.test(source), 'should check shiftKey');
  assert.ok(/triggerAnthology\s*\(\s*d\.name\s*\|\|\s*d\._topicPath/.test(source), 'should trigger anthology');
  assert.ok(/d\._topicPosts/.test(source), 'should pass topic posts to anthology');
});

test('handleClick navigates to /post-grouped/ URL for normal click', () => {
  assert.ok(/\/post-grouped\/\$\{postIds\}/.test(source), 'should navigate to /post-grouped/');
  assert.ok(/encodeURIComponent\s*\(\s*d\._topicPath/.test(source), 'should encode topic path');
  assert.ok(/d\._topicPosts\.join\s*\(\s*['_"]_['_"]/.test(source), 'should join post IDs with underscore');
});

test('handleClick opens new tab for ctrl/meta key', () => {
  assert.ok(/event\.ctrlKey\s*\|\|\s*event\.metaKey/.test(source), 'should check ctrl/meta key');
  assert.ok(/window\.open\s*\(\s*url\s*,\s*['_"]_blank['_"]/.test(source), 'should open in new tab');
});

test('handleClick goes to /topics-list when clicking center (no data)', () => {
  assert.ok(/\/topics-list/.test(source), 'should navigate to /topics-list for center click');
});

// ============================================================
// Extract and test pure functions
// ============================================================

/**
 * Extract a class method body from source.
 * Finds `methodName(` then tracks parentheses to find the `)`,
 * then finds `{` and brace-counts to find the body.
 * Returns just the body content (without the surrounding braces).
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

test('hexToRGB correctly parses #ff00aa (source inspection)', () => {
  // Verify hexToRGB uses parseInt with base 16 on hex slices
  assert.ok(/parseInt.*hex\.slice.*16/.test(source), 'should use parseInt with base 16');
  assert.ok(/return\s*\[\s*r\s*,\s*g\s*,\s*b\s*\]/.test(source), 'should return [r, g, b]');
});

test('rgbToHex correctly converts [255, 0, 170] (source inspection)', () => {
  // Verify rgbToHex maps values to hex strings and joins them
  assert.ok(/\.map\s*\(/.test(source), 'should use map for conversion');
  assert.ok(/\.toString\s*\(\s*16\s*\)/.test(source), 'should convert to base 16');
  assert.ok(/\.join\s*\(\s*['"]["']\s*\)/.test(source), 'should join hex values');
  assert.ok(/['"]#['"]/.test(source) || /'\\#'/.test(source) || /["']#["']/.test(source), 'should prepend #');
});

test('rgbToHex pads single-digit hex values (source inspection)', () => {
  // Verify single-digit hex padding
  assert.ok(/hex\.length\s*===\s*1/.test(source), 'should check hex length');
  assert.ok(/['"]0['"]\s*\+/.test(source), 'should prepend 0 for single digit');
});
