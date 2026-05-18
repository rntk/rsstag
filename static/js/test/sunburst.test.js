import test from 'node:test';
import assert from 'assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'sunburst.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Class structure tests
// ============================================================

test('source declares TagSunburst as a default export class', () => {
  assert.ok(/export\s+default\s+class\s+TagSunburst\b/.test(source), 'should export default class TagSunburst');
});

test('source declares constructor with data param', () => {
  assert.ok(/constructor\s*\(\s*data\s*\)/.test(source), 'constructor should accept data');
});

test('source stores data on this.data', () => {
  assert.ok(/this\.data\s*=\s*data/.test(source), 'should store data as this.data');
});

test('source sets base_color to #d7d7af', () => {
  assert.ok(/this\.base_color\s*=\s*['"]#d7d7af['"]/.test(source), 'base_color should be #d7d7af');
});

test('source sets color_range to 20', () => {
  assert.ok(/this\.color_range\s*=\s*20/.test(source), 'color_range should be 20');
});

test('source sets maxChildrenPerChart to 50', () => {
  assert.ok(/this\.maxChildrenPerChart\s*=\s*50/.test(source), 'maxChildrenPerChart should be 50');
});

test('source initializes currentPage to 0', () => {
  assert.ok(/this\.currentPage\s*=\s*0/.test(source), 'currentPage should start at 0');
});

test('source initializes charts as empty array', () => {
  assert.ok(/this\.charts\s*=\s*\[\]/.test(source), 'charts should be empty array');
});

test('source initializes splitData as null', () => {
  assert.ok(/this\.splitData\s*=\s*null/.test(source), 'splitData should start as null');
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
  assert.ok(/createSplitData\s*\(\s*\)/.test(source), 'should have createSplitData method');
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

// ============================================================
// Hierarchy preparation tests (before/after merging)
// ============================================================

test('initializeCharts merges before and after arrays into children', () => {
  assert.ok(/this\.data\.children\s*=\s*\[\.\.\.\s*\(\s*this\.data\.before\s*\|\|\s*\[\]\s*\)\s*,\s*\.\.\.\s*\(\s*this\.data\.after\s*\|\|\s*\[\]\s*\)\s*\]/.test(source), 'should merge before and after into children');
});

test('merge only happens when children not present but before/after exist', () => {
  assert.ok(/!this\.data\.children\s*&&\s*\(this\.data\.before/.test(source), 'merge condition should check !children && (before || after)');
});

// ============================================================
// Data splitting tests
// ============================================================

test('initializeCharts splits data when children exceed maxChildrenPerChart', () => {
  assert.ok(/this\.data\.children\.length\s*>\s*this\.maxChildrenPerChart/.test(source), 'should check if children exceed maxChildrenPerChart');
});

test('createSplitData uses slice with maxChildrenPerChart chunk size', () => {
  assert.ok(/children\.slice\s*\(\s*i\s*,\s*i\s*\+\s*this\.maxChildrenPerChart\s*\)/.test(source), 'should chunk with slice');
});

test('createSplitData spreads original data properties into each chunk', () => {
  assert.ok(/\.\.\.\s*this\.data/.test(source), 'should spread this.data into chunks');
});

test('createSplitData includes _pageInfo with current, total, startIndex, endIndex', () => {
  assert.ok(/_pageInfo\s*:\s*\{/.test(source), 'should include _pageInfo object');
  assert.ok(/current\s*:\s*Math\.floor/.test(source), '_pageInfo should have current');
  assert.ok(/total\s*:\s*Math\.ceil/.test(source), '_pageInfo should have total');
  assert.ok(/startIndex\s*:\s*i/.test(source), '_pageInfo should have startIndex');
  assert.ok(/endIndex\s*:\s*Math\.min/.test(source), '_pageInfo should have endIndex');
});

// ============================================================
// Render structure tests
// ============================================================

test('render uses document.querySelector to find container', () => {
  assert.ok(/document\.querySelector\s*\(\s*selector\s*\)/.test(source), 'should query selector');
});

test('render returns early when container not found', () => {
  assert.ok(/if\s*\(!container\)\s*return/.test(source), 'should return early if no container');
});

test('render clears container innerHTML', () => {
  assert.ok(/container\.innerHTML\s*=\s*['"]['"]/.test(source), 'should clear container');
});

test('render creates div with id sunburst-chart-container', () => {
  assert.ok(/chartContainer\.id\s*=\s*['"]sunburst-chart-container['"]/.test(source), 'should create chart container div');
});

test('render appends chartContainer to container', () => {
  assert.ok(/container\.appendChild\s*\(\s*chartContainer\s*\)/.test(source), 'should append chart container');
});

test('render creates navigation when splitData has multiple pages', () => {
  assert.ok(/this\.splitData\.length\s*>\s*1/.test(source), 'should check splitData length for nav');
  assert.ok(/this\.createNavigation\s*\(\s*container\s*\)/.test(source), 'should call createNavigation');
});

// ============================================================
// Navigation tests
// ============================================================

test('createNavigation creates div with sunburst-navigation class', () => {
  assert.ok(/nav\.className\s*=\s*['"]sunburst-navigation['"]/.test(source), 'should set nav class name');
});

test('createNavigation creates Previous button', () => {
  assert.ok(/prevBtn\.textContent\s*=\s*['"]\u2190\s*Previous['"]/.test(source), 'should create Previous button');
});

test('createNavigation creates Next button', () => {
  assert.ok(/nextBtn\.textContent\s*=\s*['"]Next\s*\u2192['"]/.test(source), 'should create Next button');
});

test('createNavigation disables Previous button on first page', () => {
  assert.ok(/prevBtn\.disabled\s*=\s*this\.currentPage\s*===\s*0/.test(source), 'should disable prev on page 0');
});

test('createNavigation disables Next button on last page', () => {
  assert.ok(/nextBtn\.disabled\s*=\s*this\.currentPage\s*===\s*this\.splitData\.length\s*-\s*1/.test(source), 'should disable next on last page');
});

test('createNavigation shows page info text', () => {
  assert.ok(/pageInfo\.textContent\s*=/.test(source), 'should set page info text');
  assert.ok(/Page\s*\$\{/.test(source), 'page info should include "Page"');
});

test('createNavigation sets display flex on nav', () => {
  assert.ok(/display\s*:\s*flex/.test(source), 'nav should use display flex');
  assert.ok(/justify-content\s*:\s*space-between/.test(source), 'nav should use justify-content space-between');
});

// ============================================================
// Pagination tests
// ============================================================

test('navigateToPage validates pageIndex bounds', () => {
  assert.ok(/pageIndex\s*<\s*0/.test(source), 'should check negative index');
  assert.ok(/pageIndex\s*>=\s*this\.splitData\.length/.test(source), 'should check out-of-bounds index');
});

test('navigateToPage updates currentPage', () => {
  assert.ok(/this\.currentPage\s*=\s*pageIndex/.test(source), 'should update currentPage');
});

test('navigateToPage re-renders chart', () => {
  assert.ok(/this\.renderCurrentChart\s*\(\s*chartContainer\s*\)/.test(source), 'should re-render chart');
});

test('navigateToPage removes old navigation and creates new one', () => {
  assert.ok(/nav\.remove\(\)/.test(source), 'should remove old nav');
  assert.ok(/this\.createNavigation\s*\(\s*container\s*\)/.test(source), 'should create new nav');
});

// ============================================================
// Click/navigation behavior tests
// ============================================================

test('renderCurrentChart sets data on current chart', () => {
  assert.ok(/currentChart\s*\.\s*data\s*\(\s*currentData\s*\)/.test(source), 'should set chart data');
});

test('renderCurrentChart sets minSliceAngle to 0', () => {
  assert.ok(/\.minSliceAngle\s*\(\s*0\s*\)/.test(source), 'should set minSliceAngle to 0');
});

test('renderCurrentChart sets onClick handler', () => {
  assert.ok(/\.onClick\s*\(/.test(source), 'should set onClick handler');
});

test('onClick navigates to /sunburst/ for normal click', () => {
  assert.ok(/window\.location\.href\s*=\s*['"]\/sunburst\/['"]/.test(source), 'should navigate to /sunburst/');
});

test('onClick uses encodeURIComponent for tag path', () => {
  assert.ok(/encodeURIComponent/.test(source), 'should use encodeURIComponent');
});

test('onClick opens new tab for ctrl/meta key', () => {
  assert.ok(/event\.ctrlKey/.test(source), 'should check ctrlKey');
  assert.ok(/event\.metaKey/.test(source), 'should check metaKey');
  assert.ok(/window\.open\s*\(/.test(source), 'should call window.open');
  assert.ok(/['_"]_blank['_"]/.test(source), 'should open in _blank');
});

test('onClick goes to parent tag when clicking center', () => {
  assert.ok(/tags\.pop\(\)/.test(source), 'should pop last tag for parent');
});

test('onClick goes to root (/) for single-word tag', () => {
  assert.ok(/window\.location\.href\s*=\s*['"]\/['"]/.test(source), 'should go to root /');
});

// ============================================================
// Color helper tests (extracted via regex + new Function)
// ============================================================

test('generateSimilarColor function exists in source', () => {
  assert.ok(/function\s+generateSimilarColor\s*\(\s*baseColor\s*,\s*range\s*\)/.test(source), 'should declare generateSimilarColor');
});

test('generateSimilarColor clamps RGB values between 0-255', () => {
  assert.ok(/Math\.min\s*\(\s*255\s*,\s*Math\.max\s*\(\s*0/.test(source), 'should clamp values');
});

test('generateSimilarColor uses Math.random for color variation', () => {
  assert.ok(/Math\.random\(\)/.test(source), 'should use Math.random');
});

test('hexToRGB function exists', () => {
  assert.ok(/function\s+hexToRGB\s*\(\s*hex\s*\)/.test(source), 'should declare hexToRGB');
});

test('hexToRGB parses hex with parseInt and slice', () => {
  assert.ok(/parseInt\s*\(\s*hex\.slice\s*\(\s*1\s*,\s*3\s*\)\s*,\s*16\s*\)/.test(source), 'should parse R component');
  assert.ok(/parseInt\s*\(\s*hex\.slice\s*\(\s*3\s*,\s*5\s*\)\s*,\s*16\s*\)/.test(source), 'should parse G component');
  assert.ok(/parseInt\s*\(\s*hex\.slice\s*\(\s*5\s*,\s*7\s*\)\s*,\s*16\s*\)/.test(source), 'should parse B component');
});

test('rgbToHex function exists', () => {
  assert.ok(/function\s+rgbToHex\s*\(\s*rgb\s*\)/.test(source), 'should declare rgbToHex');
});

test('rgbToHex pads single hex digits with leading zero', () => {
  assert.ok(/hex\.length\s*===\s*1\s*\?\s*['"]0['"]\s*\+/.test(source), 'should pad single hex digit');
});

test('rgbToHex converts via toString(16)', () => {
  assert.ok(/\.toString\s*\(\s*16\s*\)/.test(source), 'should convert with toString(16)');
});

// ============================================================
// Helper function extraction and testing
// ============================================================

test('hexToRGB correctly parses #ff00aa', () => {
  const match = source.match(/function\s+hexToRGB\s*\([^)]*\)\s*\{[\s\S]*?^\}/m);
  assert.ok(match, 'should be able to extract hexToRGB');
  const fn = new Function('hex', match[0] + '\nreturn hexToRGB(hex);');
  const result = fn('#ff00aa');
  assert.deepEqual(result, [255, 0, 170]);
});

test('rgbToHex correctly converts [255, 0, 170]', () => {
  const match = source.match(/function\s+rgbToHex\s*\([^)]*\)\s*\{[\s\S]*?^\}/m);
  assert.ok(match, 'should be able to extract rgbToHex');
  const fn = new Function('rgb', match[0] + '\nreturn rgbToHex(rgb);');
  const result = fn([255, 0, 170]);
  assert.equal(result, '#ff00aa');
});

test('rgbToHex pads single-digit hex values', () => {
  const match = source.match(/function\s+rgbToHex\s*\([^)]*\)\s*\{[\s\S]*?^\}/m);
  assert.ok(match, 'should be able to extract rgbToHex');
  const fn = new Function('rgb', match[0] + '\nreturn rgbToHex(rgb);');
  const result = fn([0, 15, 5]);
  assert.equal(result, '#000f05');
});

// ============================================================
// Import/dependency tests
// ============================================================

test('source imports Sunburst from sunburst-chart', () => {
  assert.ok(/import\s+Sunburst\s+from\s+['"]sunburst-chart['"]/.test(source), 'should import Sunburst from sunburst-chart');
});

test('source calls Sunburst() to create chart instances', () => {
  assert.ok(/Sunburst\(\)/.test(source), 'should call Sunburst()');
});

// ============================================================
// Color function usage tests
// ============================================================

test('renderCurrentChart sets color function using generateSimilarColor', () => {
  assert.ok(/\.color\s*\(\s*\(\s*d\s*\)\s*=>\s*generateSimilarColor/.test(source), 'should use generateSimilarColor for chart color');
});
