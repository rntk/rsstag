import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'topics-river-chart.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Class structure tests
// ============================================================

test('source declares TopicsRiverChart as a default export class', () => {
  assert.ok(
    /export\s+default\s+class\s+TopicsRiverChart\b/.test(source),
    'should export default class TopicsRiverChart'
  );
});

test('source declares constructor with containerSelector and options params', () => {
  assert.ok(
    /constructor\s*\(\s*containerSelector\s*,\s*options\s*=\s*\{/.test(source),
    'constructor should accept containerSelector and options'
  );
});

test('source imports calculateBins, smoothBins, estimateCharacterCounts, getRiverColorScale from chart-utils', () => {
  assert.ok(/import\s*\{[^}]*calculateBins[^}]*\}/.test(source), 'should import calculateBins');
  assert.ok(/smoothBins/.test(source), 'should import smoothBins');
  assert.ok(/estimateCharacterCounts/.test(source), 'should import estimateCharacterCounts');
  assert.ok(/getRiverColorScale/.test(source), 'should import getRiverColorScale');
});

test('source imports RiverLegend', () => {
  assert.ok(/import\s+RiverLegend\s+from/.test(source), 'should import RiverLegend');
});

// ============================================================
// Constructor state tests
// ============================================================

test('source handles both string selector and element for container', () => {
  assert.ok(
    /typeof\s+containerSelector\s*===\s*['"]string['"]/.test(source),
    'should check if selector is string'
  );
  assert.ok(
    /document\.querySelector\s*\(\s*containerSelector\s*\)/.test(source),
    'should query selector if string'
  );
});

test('source reads topics from options', () => {
  assert.ok(
    /this\.topics\s*=\s*options\.topics\s*\|\|\s*\[\]/.test(source),
    'should set topics from options'
  );
});

test('source reads articleLength from options', () => {
  assert.ok(
    /this\.articleLength\s*=\s*options\.articleLength\s*\|\|\s*0/.test(source),
    'should set articleLength from options'
  );
});

test('source initializes activeTopic to null', () => {
  assert.ok(/this\.activeTopic\s*=\s*null/.test(source), 'activeTopic should be null');
});

test('source initializes legend to null', () => {
  assert.ok(/this\.legend\s*=\s*null/.test(source), 'legend should be null');
});

test('source initializes svg to null', () => {
  assert.ok(/this\.svg\s*=\s*null/.test(source), 'svg should be null');
});

test('source calls _calculateEffectiveLength in constructor', () => {
  assert.ok(
    /this\.effectiveLength\s*=\s*this\._calculateEffectiveLength\(\)/.test(source),
    'should call _calculateEffectiveLength'
  );
});

test('source derives keys from topic names', () => {
  assert.ok(
    /this\.keys\s*=\s*this\.topics\.map\s*\(\s*\(\s*t\s*\)\s*=>\s*t\.name\s*\)/.test(source),
    'should map topic names to keys'
  );
});

test('source creates colorScale with getRiverColorScale', () => {
  assert.ok(
    /this\.colorScale\s*=\s*getRiverColorScale\s*\(\s*this\.keys\s*\)/.test(source),
    'should create color scale from keys'
  );
});

test('constructor calls init', () => {
  assert.ok(/this\.init\(\)/.test(source), 'constructor should call init');
});

// ============================================================
// Method declarations tests
// ============================================================

test('source declares _calculateEffectiveLength method', () => {
  assert.ok(
    /_calculateEffectiveLength\s*\(\s*\)/.test(source),
    'should have _calculateEffectiveLength method'
  );
});

test('source declares init method', () => {
  assert.ok(/\binit\s*\(\s*\)/.test(source), 'should have init method');
});

test('source declares setActiveTopic method', () => {
  assert.ok(/\bsetActiveTopic\s*\(\s*name\s*\)/.test(source), 'should have setActiveTopic method');
});

test('source declares _updateStyles method', () => {
  assert.ok(/_updateStyles\s*\(\s*\)/.test(source), 'should have _updateStyles method');
});

test('source declares render method', () => {
  assert.ok(/\brender\s*\(\s*\)/.test(source), 'should have render method');
});

// ============================================================
// _calculateEffectiveLength logic tests
// ============================================================

test('_calculateEffectiveLength returns 0 for empty topics', () => {
  assert.ok(
    /if\s*\(!this\.topics\s*\|\|\s*this\.topics\.length\s*===\s*0\)\s*return\s*0/.test(source),
    'should return 0 for empty topics'
  );
});

test('_calculateEffectiveLength finds max sentence index', () => {
  assert.ok(
    /Math\.max\s*\(\s*\.\.\.\s*topic\.sentences/.test(source),
    'should use Math.max with spread on sentences'
  );
});

test('_calculateEffectiveLength adds 5 to max sentence index', () => {
  assert.ok(/maxSentenceIndex\s*\+\s*5/.test(source), 'should add 5 to max index');
});

test('_calculateEffectiveLength caps at valid articleLength', () => {
  assert.ok(
    /Math\.min\s*\(\s*maxSentenceIndex\s*\+\s*5\s*,\s*validArticleLength/.test(source),
    'should cap at articleLength'
  );
});

test('_calculateEffectiveLength validates articleLength is positive number', () => {
  assert.ok(
    /typeof\s+this\.articleLength\s*===\s*['"]number['"]\s*&&\s*this\.articleLength\s*>\s*0/.test(
      source
    ),
    'should validate articleLength'
  );
});

test('_calculateEffectiveLength uses Infinity for invalid articleLength', () => {
  assert.ok(/:\s*Infinity/.test(source), 'should use Infinity as fallback');
});

// ============================================================
// init method tests
// ============================================================

test('init returns early when container is falsy', () => {
  assert.ok(/if\s*\(!this\.container\)\s*return/.test(source), 'should return if no container');
});

test('init checks for d3 availability', () => {
  assert.ok(
    /typeof\s+d3\s*===\s*['"]undefined['"]/.test(source),
    'should check if d3 is undefined'
  );
});

test('init shows error message when D3 is not loaded', () => {
  assert.ok(/D3\.js is not loaded/.test(source), 'should show D3 error message');
});

test('init clears container innerHTML', () => {
  assert.ok(/this\.container\.innerHTML\s*=\s*['']{2}/.test(source), 'should clear container');
});

test('init sets container styles with Object.assign', () => {
  assert.ok(
    /Object\.assign\s*\(\s*this\.container\.style/.test(source),
    'should use Object.assign for styles'
  );
});

test('init sets container display to flex', () => {
  assert.ok(/display\s*:\s*['"]flex['"]/.test(source), 'should set display flex');
});

test('init sets container flexDirection to column', () => {
  assert.ok(/flexDirection\s*:\s*['"]column['"]/.test(source), 'should set flex-direction column');
});

test('init sets container backgroundColor to #fafafa', () => {
  assert.ok(/backgroundColor\s*:\s*['"]#fafafa['"]/.test(source), 'should set background color');
});

test('init sets container borderRadius to 8px', () => {
  assert.ok(/borderRadius\s*:\s*['"]8px['"]/.test(source), 'should set border radius');
});

test('init creates chart wrapper with height 520px', () => {
  assert.ok(
    /chartWrapper\.style\.height\s*=\s*['"]520px['"]/.test(source),
    'chart wrapper should be 520px'
  );
});

test('init creates SVG element using createElementNS', () => {
  assert.ok(
    /createElementNS\s*\(\s*['"]http:\/\/www\.w3\.org\/2000\/svg['"]/.test(source),
    'should create SVG via createElementNS'
  );
});

test('init creates RiverLegend with topics, colorScale, onActivate', () => {
  assert.ok(/new\s+RiverLegend\s*\(\s*legendContainer/.test(source), 'should create RiverLegend');
  assert.ok(/items\s*:\s*this\.topics/.test(source), 'should pass topics as items');
  assert.ok(/colorScale\s*:\s*this\.colorScale/.test(source), 'should pass colorScale');
  assert.ok(/onActivate\s*:/.test(source), 'should pass onActivate callback');
});

test('init registers window resize listener', () => {
  assert.ok(
    /window\.addEventListener\s*\(\s*['"]resize['"]/.test(source),
    'should register resize listener'
  );
});

test('init calls render', () => {
  assert.ok(/this\.render\(\)/.test(source), 'init should call render');
});

// ============================================================
// setActiveTopic method tests
// ============================================================

test('setActiveTopic updates this.activeTopic', () => {
  assert.ok(/this\.activeTopic\s*=\s*name/.test(source), 'should update activeTopic');
});

test('setActiveTopic calls _updateStyles', () => {
  assert.ok(/this\._updateStyles\(\)/.test(source), 'should call _updateStyles');
});

test('setActiveTopic calls legend.update when legend available', () => {
  assert.ok(
    /if\s*\(\s*this\.legend\s*\)\s*this\.legend\.update\s*\(\s*name\s*\)/.test(source),
    'should update legend'
  );
});

// ============================================================
// _updateStyles method tests
// ============================================================

test('_updateStyles returns early when svg is null', () => {
  assert.ok(/if\s*\(!this\.svg\)\s*return/.test(source), 'should return if no svg');
});

test('_updateStyles selects .stream-layer paths', () => {
  assert.ok(
    /this\.svg\.selectAll\s*\(\s*['"]\.stream-layer['"]/.test(source),
    'should select stream-layer paths'
  );
});

test('_updateStyles dims inactive topics to opacity 0.2', () => {
  assert.ok(
    /opacity['"]\s*,\s*\(\s*d\s*\)\s*=>\s*\(\s*d\.key\s*===\s*this\.activeTopic\s*\?\s*1\s*:\s*0\.2/.test(
      source
    ),
    'should dim inactive to 0.2'
  );
});

test('_updateStyles sets active topic stroke to #333', () => {
  assert.ok(
    /stroke['"]\s*,\s*\(d\)\s*=>\s*\(\s*d\.key\s*===\s*this\.activeTopic\s*\?\s*['"]#333['"]/.test(
      source
    ),
    'should set active stroke'
  );
});

test('_updateStyles resets all paths when no active topic', () => {
  assert.ok(
    /\.transition\(\)\.duration\(200\)\.style\('opacity',\s*0\.85\)/.test(source),
    'should reset opacity to 0.85'
  );
});

// ============================================================
// render method tests
// ============================================================

test('render returns early when effectiveLength is falsy', () => {
  assert.ok(/!this\.effectiveLength/.test(source), 'should check effectiveLength');
});

test('render returns early when topics is empty', () => {
  assert.ok(
    /!this\.topics\s*\|\|\s*this\.topics\.length\s*===\s*0/.test(source),
    'should check topics'
  );
});

test('render calculates binCount from containerWidth', () => {
  assert.ok(
    /Math\.max\s*\(\s*15\s*,\s*Math\.min\s*\(\s*60\s*,\s*Math\.floor\s*\(\s*containerWidth\s*\/\s*40/.test(
      source
    ),
    'should calculate binCount between 15 and 60'
  );
});

test('render calls calculateBins', () => {
  assert.ok(
    /calculateBins\s*\(\s*binCount\s*,\s*this\.topics/.test(source),
    'should call calculateBins'
  );
});

test('render calls smoothBins', () => {
  assert.ok(/smoothBins\s*\(\s*data/.test(source), 'should call smoothBins');
});

test('render calls estimateCharacterCounts', () => {
  assert.ok(
    /estimateCharacterCounts\s*\(\s*data/.test(source),
    'should call estimateCharacterCounts'
  );
});

// ============================================================
// D3 rendering structure tests
// ============================================================

test('render creates SVG with d3.select', () => {
  assert.ok(
    /this\.svg\s*=\s*d3\.select\s*\(\s*svgEl\s*\)/.test(source),
    'should use d3.select on SVG element'
  );
});

test('render sets viewBox with width and height', () => {
  assert.ok(/\.attr\s*\(\s*['"]viewBox['"]\s*,/.test(source), 'should set viewBox');
});

test('render uses d3.stack with stackOffsetWiggle and stackOrderInsideOut', () => {
  assert.ok(/d3\s*\.\s*stack\(\)/.test(source), 'should use d3.stack');
  assert.ok(/d3\.stackOffsetWiggle/.test(source), 'should use wiggle offset');
  assert.ok(/d3\.stackOrderInsideOut/.test(source), 'should use inside-out order');
});

test('render uses d3.area with curveBasis', () => {
  assert.ok(/d3\s*\.\s*area\(\)/.test(source), 'should use d3.area');
  assert.ok(/d3\.curveBasis/.test(source), 'should use curveBasis');
});

test('render appends .stream-layer paths with fill from colorScale', () => {
  assert.ok(
    /\.attr\s*\(\s*['"]class['"]\s*,\s*['"]stream-layer['"]/.test(source),
    'should set stream-layer class'
  );
  assert.ok(
    /\.style\s*\(\s*['"]fill['"]\s*,\s*\(\s*d\s*\)\s*=>\s*this\.colorScale\s*\(\s*d\.key\s*\)/.test(
      source
    ),
    'should use colorScale for fill'
  );
});

test('render creates tooltip with river-tooltip class', () => {
  assert.ok(/['"]river-tooltip['"]/.test(source), 'should create river-tooltip class');
  assert.ok(
    /position['"]\s*,\s*['"]absolute['"]/.test(source),
    'tooltip should be absolute positioned'
  );
});

test('render adds mouseover, mousemove, mouseout handlers on stream layers', () => {
  assert.ok(/['"]mouseover['"]/.test(source), 'should have mouseover handler');
  assert.ok(/['"]mousemove['"]/.test(source), 'should have mousemove handler');
  assert.ok(/['"]mouseout['"]/.test(source), 'should have mouseout handler');
});

test('render tooltip shows topic name and total sentences', () => {
  assert.ok(/totalSentences/.test(source), 'should show total sentences');
  assert.ok(/sentences/.test(source), 'should reference sentences in tooltip');
});

// ============================================================
// Axis and label tests
// ============================================================

test('render creates x-axis with axisBottom', () => {
  assert.ok(/d3\s*\.\s*axisBottom/.test(source), 'should use d3.axisBottom');
  assert.ok(
    /\.attr\s*\(\s*['"]class['"]\s*,\s*['"]x-axis['"]/.test(source),
    'should set x-axis class'
  );
});

test('render creates y-axis with axisLeft', () => {
  assert.ok(/d3\s*\.\s*axisLeft/.test(source), 'should use d3.axisLeft');
  assert.ok(
    /\.attr\s*\(\s*['"]class['"]\s*,\s*['"]y-axis['"]/.test(source),
    'should set y-axis class'
  );
});

test('render adds x-axis label "Number of Sentences"', () => {
  assert.ok(/['"]Number of Sentences['"]/.test(source), 'should have x-axis label');
});

test('render adds y-axis label "Number of Characters (Estimated)"', () => {
  assert.ok(/['"]Number of Characters \(Estimated\)['"]/.test(source), 'should have y-axis label');
});

// ============================================================
// Stream label tests
// ============================================================

test('render creates stream labels at thickest point', () => {
  assert.ok(
    /\.attr\s*\(\s*['"]class['"]\s*,\s*['"]stream-label['"]/.test(source),
    'should set stream-label class'
  );
});

test('render limits stream labels to top 8 by thickness', () => {
  assert.ok(
    /\.slice\s*\(\s*0\s*,\s*Math\.min\s*\(\s*8/.test(source),
    'should limit to top 8 labels'
  );
});

test('render stream labels use text shadow for readability', () => {
  assert.ok(/text-shadow/.test(source), 'should set text-shadow');
  assert.ok(/white/.test(source), 'should use white text shadow');
});

// ============================================================
// Title tests
// ============================================================

test('render adds title text "Topic Distribution Across Article"', () => {
  assert.ok(/['"]Topic Distribution Across Article['"]/.test(source), 'should set chart title');
  assert.ok(/font-size['"]\s*,\s*['"]14px['"]/.test(source), 'title should be 14px');
  assert.ok(/font-weight['"]\s*,\s*['"]bold['"]/.test(source), 'title should be bold');
});

// ============================================================
// Legend rendering tests
// ============================================================

test('render calls this.legend.render()', () => {
  assert.ok(/this\.legend\.render\(\)/.test(source), 'should call legend.render');
});
