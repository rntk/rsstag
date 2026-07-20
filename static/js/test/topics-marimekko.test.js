import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'topics-marimekko.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Class structure tests
// ============================================================

test('source declares TopicsMarimekko class', () => {
  assert.ok(/class\s+TopicsMarimekko\b/.test(source), 'should declare class TopicsMarimekko');
});

test('source exports TopicsMarimekko as default', () => {
  assert.ok(
    /export\s+default\s+TopicsMarimekko/.test(source),
    'should export default TopicsMarimekko'
  );
});

test('source imports triggerAnthology from topics-list', () => {
  assert.ok(
    /import\s*\{\s*triggerAnthology\s*\}\s*from\s+['"]\.\/topics-list\.js['"]/.test(source),
    'should import triggerAnthology'
  );
});

test('source declares constructor with no parameters', () => {
  assert.ok(/constructor\s*\(\s*\)/.test(source), 'constructor should take no parameters');
});

test('source initializes constructor state', () => {
  assert.ok(/this\.currentPage\s*=\s*0/.test(source), 'currentPage should start at 0');
  assert.ok(/this\.allColumns\s*=\s*\[\]/.test(source), 'allColumns should be empty array');
  assert.ok(/this\.totalPages\s*=\s*0/.test(source), 'totalPages should start at 0');
  assert.ok(/this\.container\s*=\s*null/.test(source), 'container should be null');
  assert.ok(/this\.maxColValue\s*=\s*1/.test(source), 'maxColValue should start at 1');
});

// ============================================================
// Constants tests
// ============================================================

test('source defines PALETTE array with 16 colors', () => {
  const paletteMatch = source.match(/const\s+PALETTE\s*=\s*\[([\s\S]*?)\];/);
  assert.ok(paletteMatch, 'should define PALETTE array');
  const colors = paletteMatch[1].match(/['"][^'"]+['"]/g);
  assert.ok(colors, 'PALETTE should contain color strings');
  assert.equal(colors.length, 16, 'PALETTE should have 16 colors');
});

test('source sets MAX_COLUMNS_PER_PAGE to 10', () => {
  assert.ok(
    /const\s+MAX_COLUMNS_PER_PAGE\s*=\s*10/.test(source),
    'MAX_COLUMNS_PER_PAGE should be 10'
  );
});

test('source defines BOTTOM_LABEL_HEIGHT as 140', () => {
  assert.ok(
    /const\s+BOTTOM_LABEL_HEIGHT\s*=\s*140/.test(source),
    'BOTTOM_LABEL_HEIGHT should be 140'
  );
});

test('source defines TOP_PADDING as 20', () => {
  assert.ok(/const\s+TOP_PADDING\s*=\s*20/.test(source), 'TOP_PADDING should be 20');
});

test('source defines COL_GAP as 6', () => {
  assert.ok(/const\s+COL_GAP\s*=\s*6/.test(source), 'COL_GAP should be 6');
});

test('source defines MIN_COL_WIDTH as 80', () => {
  assert.ok(/const\s+MIN_COL_WIDTH\s*=\s*80/.test(source), 'MIN_COL_WIDTH should be 80');
});

test('source defines FONT_SIZE_LABEL as 16', () => {
  assert.ok(/const\s+FONT_SIZE_LABEL\s*=\s*16/.test(source), 'FONT_SIZE_LABEL should be 16');
});

test('source defines FONT_SIZE_BOTTOM as 15', () => {
  assert.ok(/const\s+FONT_SIZE_BOTTOM\s*=\s*15/.test(source), 'FONT_SIZE_BOTTOM should be 15');
});

test('source defines MIN_ROW_HEIGHT from FONT_SIZE_LABEL', () => {
  assert.ok(
    /const\s+MIN_ROW_HEIGHT\s*=\s*FONT_SIZE_LABEL\s*\+\s*8/.test(source),
    'MIN_ROW_HEIGHT should be FONT_SIZE_LABEL + 8'
  );
});

test('source defines MIN_COL_HEIGHT from FONT_SIZE_LABEL', () => {
  assert.ok(
    /const\s+MIN_COL_HEIGHT\s*=\s*FONT_SIZE_LABEL\s*\+\s*10/.test(source),
    'MIN_COL_HEIGHT should be FONT_SIZE_LABEL + 10'
  );
});

// ============================================================
// Method declarations tests
// ============================================================

test('source declares _colorForBar method', () => {
  assert.ok(
    /_colorForBar\s*\(\s*colIndex\s*,\s*rowIndex\s*,\s*rowCount\s*\)/.test(source),
    'should have _colorForBar method'
  );
});

test('source declares render method', () => {
  assert.ok(
    /render\s*\(\s*selector\s*,\s*topicNode\s*\)/.test(source),
    'should have render method with selector and topicNode'
  );
});

test('source declares _getPageColumns method', () => {
  assert.ok(/_getPageColumns\s*\(\s*\)/.test(source), 'should have _getPageColumns method');
});

test('source declares _renderPage method', () => {
  assert.ok(/_renderPage\s*\(\s*\)/.test(source), 'should have _renderPage method');
});

test('source declares _buildNav method', () => {
  assert.ok(/_buildNav\s*\(\s*\)/.test(source), 'should have _buildNav method');
});

test('source declares _buildSvg method', () => {
  assert.ok(/_buildSvg\s*\(\s*columns\s*\)/.test(source), 'should have _buildSvg method');
});

test('source declares _computeRowHeights method', () => {
  assert.ok(
    /_computeRowHeights\s*\(\s*rows\s*,\s*colHeight\s*\)/.test(source),
    'should have _computeRowHeights method'
  );
});

// ============================================================
// _colorForBar logic tests
// ============================================================

test('_colorForBar uses PALETTE with modulo for cycling', () => {
  assert.ok(
    /PALETTE\[colIndex\s*%\s*PALETTE\.length\]/.test(source),
    'should cycle through palette'
  );
});

test('_colorForBar parses hex color with parseInt and slice', () => {
  assert.ok(
    /parseInt\s*\(\s*base\.slice\s*\(\s*1\s*,\s*3/.test(source),
    'should parse R component'
  );
  assert.ok(
    /parseInt\s*\(\s*base\.slice\s*\(\s*3\s*,\s*5/.test(source),
    'should parse G component'
  );
  assert.ok(
    /parseInt\s*\(\s*base\.slice\s*\(\s*5\s*,\s*7/.test(source),
    'should parse B component'
  );
});

test('_colorForBar computes factor based on rowIndex and rowCount', () => {
  assert.ok(
    /0\.7\s*\+\s*0\.6\s*\*\s*\(\s*rowIndex\s*\/\s*\(\s*rowCount\s*-\s*1/.test(source),
    'should compute factor for brightness'
  );
});

test('_colorForBar uses clamp to limit RGB to 0-255', () => {
  assert.ok(
    /const\s+clamp\s*=\s*\(\s*v\s*\)\s*=>\s*Math\.min\s*\(\s*255\s*,\s*Math\.max\s*\(\s*0/.test(
      source
    ),
    'should define clamp'
  );
});

test('_colorForBar returns rgb() string', () => {
  assert.ok(/`rgb\(\$\{clamp/.test(source), 'should return rgb() template string');
});

// ============================================================
// render method tests
// ============================================================

test('render uses document.querySelector to find container', () => {
  assert.ok(/document\.querySelector\s*\(\s*selector\s*\)/.test(source), 'should query selector');
});

test('render returns early when container not found', () => {
  assert.ok(/if\s*\(!container\)\s*return/.test(source), 'should return early');
});

test('render stores container as this.container', () => {
  assert.ok(/this\.container\s*=\s*container/.test(source), 'should store container');
});

test('render handles empty children array', () => {
  assert.ok(/children\.length\s*===\s*0/.test(source), 'should check children length');
});

test('render shows "No subtopics." for empty topic', () => {
  assert.ok(
    /container\.textContent\s*=\s*['"]No subtopics\.['"]/.test(source),
    'should show no subtopics message'
  );
});

test('render handles null topicNode', () => {
  assert.ok(
    /\(\s*topicNode\s*&&\s*topicNode\.children\s*\)\s*\|\|\s*\[\]/.test(source),
    'should handle null topicNode'
  );
});

// ============================================================
// Column building tests
// ============================================================

test('render maps children to columns with name, width, rows, originalIndex', () => {
  assert.ok(/\.map\s*\(\s*\(\s*sub\s*,\s*i\s*\)/.test(source), 'should map with index');
  assert.ok(/originalIndex\s*:\s*i/.test(source), 'should store original index');
});

test('render calculates column width from subChildren length', () => {
  assert.ok(
    /const\s+width\s*=\s*subChildren\.length\s*>\s*0\s*\?\s*subChildren\.length\s*:\s*1/.test(
      source
    ),
    'should calculate width from children'
  );
});

test('render uses text_length as primary value source', () => {
  assert.ok(/c\.text_length\s*!==\s*undefined/.test(source), 'should check text_length first');
  assert.ok(/c\.text_length\s*!==\s*null/.test(source), 'should check text_length not null');
});

test('render uses value as fallback when text_length missing', () => {
  assert.ok(/c\.value\s*!==\s*undefined/.test(source), 'should check value as fallback');
});

test('render uses count as final fallback for value', () => {
  assert.ok(/c\.count\s*!==\s*undefined/.test(source), 'should check count as final fallback');
});

test('render defaults value to 1 when nothing provided', () => {
  assert.ok(/return\s+1/.test(source), 'should default to 1');
});

test('render handles leaf subtopics without children as single row', () => {
  assert.ok(/subChildren\.length\s*>\s*0\s*\?/.test(source), 'should branch on children presence');
});

test('render computes maxColValue using Math.max', () => {
  assert.ok(/this\.maxColValue\s*=\s*Math\.max/.test(source), 'should use Math.max');
  assert.ok(
    /c\.rows\.reduce\s*\(\s*\(\s*s\s*,\s*r\s*\)\s*=>\s*s\s*\+\s*r\.value/.test(source),
    'should sum row values'
  );
});

// ============================================================
// Pagination tests
// ============================================================

test('render computes totalPages with Math.ceil', () => {
  assert.ok(
    /this\.totalPages\s*=\s*Math\.ceil\s*\(\s*this\.allColumns\.length\s*\/\s*MAX_COLUMNS_PER_PAGE/.test(
      source
    ),
    'should calculate totalPages'
  );
});

test('_getPageColumns uses slice with MAX_COLUMNS_PER_PAGE', () => {
  assert.ok(
    /this\.currentPage\s*\*\s*MAX_COLUMNS_PER_PAGE/.test(source),
    'should calculate start index'
  );
  assert.ok(
    /\.slice\s*\(\s*start\s*,\s*start\s*\+\s*MAX_COLUMNS_PER_PAGE/.test(source),
    'should slice columns'
  );
});

test('_renderPage clears container innerHTML', () => {
  assert.ok(/container\.innerHTML\s*=\s*[''][''"]/.test(source), 'should clear container');
});

test('_renderPage appends nav when totalPages > 1', () => {
  assert.ok(/this\.totalPages\s*>\s*1/.test(source), 'should check totalPages');
  assert.ok(
    /container\.appendChild\s*\(\s*this\._buildNav\s*\(\s*\)\s*\)/.test(source),
    'should append nav'
  );
});

test('_renderPage appends SVG from _buildSvg', () => {
  assert.ok(
    /container\.appendChild\s*\(\s*this\._buildSvg\s*\(\s*columns\s*\)\s*\)/.test(source),
    'should append SVG'
  );
});

// ============================================================
// _buildNav tests
// ============================================================

test('_buildNav creates div with marimekko-nav class', () => {
  assert.ok(/nav\.className\s*=\s*['"]marimekko-nav['"]/.test(source), 'should set nav class');
});

test('_buildNav creates Previous button with arrow unicode', () => {
  assert.ok(
    /prevBtn\.textContent\s*=\s*['"]\\u2190\s*Previous['"]/.test(source),
    'should create Previous button'
  );
  assert.ok(
    /prevBtn\.className\s*=\s*['"]marimekko-nav-btn['"]/.test(source),
    'should set button class'
  );
});

test('_buildNav creates Next button with arrow unicode', () => {
  assert.ok(
    /nextBtn\.textContent\s*=\s*['"]Next\s*\\u2192['"]/.test(source),
    'should create Next button'
  );
  assert.ok(
    /nextBtn\.className\s*=\s*['"]marimekko-nav-btn['"]/.test(source),
    'should set button class'
  );
});

test('_buildNav creates info span with marimekko-nav-info class', () => {
  assert.ok(
    /info\.className\s*=\s*['"]marimekko-nav-info['"]/.test(source),
    'should set info class'
  );
});

test('_buildNav info shows page and range text', () => {
  assert.ok(/Page\s*\$\{this\.currentPage/.test(source), 'should show page number');
  assert.ok(/subtopics\s*\$\{start/.test(source), 'should show subtopic range');
});

test('_buildNav Previous button disabled on page 0', () => {
  assert.ok(
    /prevBtn\.disabled\s*=\s*this\.currentPage\s*===\s*0/.test(source),
    'should disable prev on page 0'
  );
});

test('_buildNav Next button disabled on last page', () => {
  assert.ok(
    /nextBtn\.disabled\s*=\s*this\.currentPage\s*>=\s*this\.totalPages\s*-\s*1/.test(source),
    'should disable next on last page'
  );
});

test('_buildNav Previous button decrements currentPage', () => {
  assert.ok(/this\.currentPage--/.test(source), 'should decrement currentPage');
  assert.ok(/this\._renderPage\(\)/.test(source), 'should re-render page');
});

test('_buildNav Next button increments currentPage', () => {
  assert.ok(/this\.currentPage\+\+/.test(source), 'should increment currentPage');
});

// ============================================================
// _buildSvg tests
// ============================================================

test('_buildSvg calculates chartWidth from container.clientWidth', () => {
  assert.ok(/this\.container\.clientWidth/.test(source), 'should read container clientWidth');
  assert.ok(/Math\.max\s*\(\s*this\.container\.clientWidth/.test(source), 'should use Math.max');
});

test('_buildSvg calculates barAreaHeight from window.innerHeight', () => {
  assert.ok(/window\.innerHeight\s*\*\s*0\.85/.test(source), 'should use 85% of innerHeight');
});

test('_buildSvg creates SVG with createElementNS', () => {
  assert.ok(/createElementNS\s*\(\s*svgNs/.test(source), 'should use createElementNS');
  assert.ok(/http:\/\/www\.w3\.org\/2000\/svg/.test(source), 'should use SVG namespace');
});

test('_buildSvg sets SVG width and height attributes', () => {
  assert.ok(
    /svg\.setAttribute\s*\(\s*['"]width['"]\s*,\s*chartWidth/.test(source),
    'should set width'
  );
  assert.ok(
    /svg\.setAttribute\s*\(\s*['"]height['"]\s*,\s*chartHeight/.test(source),
    'should set height'
  );
});

test('_buildSvg sets SVG display:block style', () => {
  assert.ok(/svg\.style\.display\s*=\s*['"]block['"]/.test(source), 'should set display block');
});

test('_buildSvg creates rect elements with fill from _colorForBar', () => {
  assert.ok(/rect\.setAttribute\s*\(\s*['"]fill['"]/.test(source), 'should set rect fill');
  assert.ok(/this\._colorForBar\s*\(\s*colorIdx/.test(source), 'should use _colorForBar');
});

test('_buildSvg creates title elements as tooltips', () => {
  assert.ok(
    /const\s+title\s*=\s*document\.createElementNS/.test(source),
    'should create title element'
  );
  assert.ok(/title\.textContent\s*=/.test(source), 'should set title text');
});

test('_buildSvg creates text labels with rotation', () => {
  assert.ok(
    /label\.setAttribute\s*\(\s*['"]transform['"]\s*,\s*['"`]rotate/.test(source),
    'should set rotation transform'
  );
});

test('_buildSvg creates clickable links for rows with topicPath', () => {
  assert.ok(/\/post-grouped-snippets\/\$\{/.test(source), 'should create snippets URL');
  assert.ok(/encodeURIComponent\s*\(\s*topicPath/.test(source), 'should encode topic path');
});

test('_buildSvg adds click handler that triggers anthology on shift-click', () => {
  assert.ok(/e\.shiftKey/.test(source), 'should check shift key');
  assert.ok(/triggerAnthology\s*\(\s*row\.name/.test(source), 'should trigger anthology');
});

test('_buildSvg truncates long labels with ellipsis', () => {
  assert.ok(
    /\.slice\s*\(\s*0\s*,\s*maxChars\s*-\s*1\s*\)\s*\+\s*['"]\\u2026['"]/.test(source),
    'should truncate with ellipsis'
  );
});

// ============================================================
// _computeRowHeights tests
// ============================================================

test('_computeRowHeights returns empty array for no rows', () => {
  assert.ok(
    /if\s*\(\s*rowCount\s*===\s*0\s*\)\s*\{[\s\S]*return\s*\[\]/.test(source),
    'should return empty for no rows'
  );
});

test('_computeRowHeights distributes equally when colHeight <= minTotal', () => {
  assert.ok(
    /new\s+Array\s*\(\s*rowCount\s*\)\.fill\s*\(\s*colHeight\s*\/\s*rowCount/.test(source),
    'should distribute equally for small height'
  );
});

test('_computeRowHeights uses proportional distribution with extra height', () => {
  assert.ok(
    /const\s+extraHeight\s*=\s*colHeight\s*-\s*minTotal/.test(source),
    'should compute extra height'
  );
  assert.ok(
    /MIN_ROW_HEIGHT\s*\+\s*\(\s*value\s*\/\s*valueSum\s*\)\s*\*\s*extraHeight/.test(source),
    'should distribute proportionally'
  );
});

test('_computeRowHeights handles zero valueSum by distributing equally', () => {
  assert.ok(/if\s*\(\s*valueSum\s*<=\s*0\s*\)/.test(source), 'should check zero sum');
  assert.ok(
    /new\s+Array\s*\(\s*rowCount\s*\)\.fill\s*\(\s*colHeight\s*\/\s*rowCount/.test(source),
    'should distribute equally for zero sum'
  );
});

// ============================================================
// Extract and test pure function
// ============================================================

test('_colorForBar returns valid RGB string format', () => {
  const match = source.match(/_colorForBar\s*\([^)]*\)\s*\{[\s\S]*?return\s+`rgb\([^`]+`\s*;\s*\n/);
  assert.ok(match, 'should extract _colorForBar body');
  // Create a standalone version to test
  const fnSource = match[0].replace(/this\._colorForBar\s*=\s*/, '').replace(/^  /gm, '');
  const wrapperFn = new Function(
    'colIndex',
    'rowIndex',
    'rowCount',
    `
    const PALETTE = ${source.match(/const\s+PALETTE\s*=\s*\[[\s\S]*?\];/m)[0].replace(/const\s+PALETTE\s*=\s*/, '')};
    function _colorForBar(colIndex, rowIndex, rowCount) {
      ${fnSource.split('{').slice(1).join('{')}
    }
    return _colorForBar(colIndex, rowIndex, rowCount);
  `
  );
  const result = wrapperFn(0, 0, 1);
  assert.ok(result.startsWith('rgb('), 'should return rgb() string');
  assert.ok(/rgb\(\d+,\s*\d+,\s*\d+\)/.test(result), 'should be valid rgb format');
});
