import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'prefix_tree.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Class structure tests
// ============================================================

test('source declares PrefixTree as a default export class', () => {
  assert.ok(/export\s+default\s+class\s+PrefixTree\b/.test(source), 'should export default class PrefixTree');
});

test('source declares constructor with data param', () => {
  assert.ok(/constructor\s*\(\s*data\s*\)/.test(source), 'constructor should accept data');
});

test('source stores data on this.data', () => {
  assert.ok(/this\.data\s*=\s*data/.test(source), 'should store data as this.data');
});

test('source declares render method', () => {
  assert.ok(/render\s*\(\s*selector\s*\)/.test(source), 'should have render method');
});

// ============================================================
// Import/dependency tests
// ============================================================

test('source imports d3', () => {
  assert.ok(/import\s+\*\s+as\s+d3\s+from\s+['"]d3['"]/.test(source), 'should import d3');
});

// ============================================================
// Render method structure tests
// ============================================================

test('render creates link_fn as arrow function', () => {
  assert.ok(/let\s+link_fn\s*=\s*\(\s*d\s*,\s*n\s*\)\s*=>/.test(source), 'should define link_fn arrow function');
});

test('link_fn uses ancestors().reverse().map() to build path', () => {
  assert.ok(/n\s*\.\s*ancestors\(\)\s*\.\s*reverse\(\)\s*\.\s*map/.test(source), 'link_fn should traverse ancestors in reverse');
});

test('link_fn maps to d.data.name', () => {
  assert.ok(/\.map\s*\(\s*\(\s*d\s*\)\s*=>\s*d\.data\.name\s*\)/.test(source), 'link_fn should map to d.data.name');
});

test('link_fn builds URL with /prefixes/prefix/ path', () => {
  assert.ok(/['"]\/prefixes\/prefix\/['"]/.test(source), 'link_fn should use /prefixes/prefix/ path');
});

test('link_fn uses document.location.origin', () => {
  assert.ok(/document\.location\.origin/.test(source), 'link_fn should use document.location.origin');
});

test('link_fn uses encodeURIComponent for url_tag', () => {
  assert.ok(/encodeURIComponent\s*\(\s*url_tag\s*\)/.test(source), 'link_fn should encode the URL tag');
});

test('link_fn joins ancestor names with empty string', () => {
  assert.ok(/lst\.join\s*\(\s*[''][''"]/.test(source), 'link_fn should join names with empty string');
});

// ============================================================
// Tree function invocation tests
// ============================================================

test('render calls Tree function with this.data', () => {
  assert.ok(/Tree\s*\(\s*this\.data\s*,/.test(source), 'should call Tree with this.data');
});

test('Tree called with label option returning d.name', () => {
  assert.ok(/label\s*:\s*\(\s*d\s*\)\s*=>\s*d\.name/.test(source), 'should pass label option');
});

test('Tree called with title option using ancestors', () => {
  assert.ok(/title\s*:\s*\(\s*d\s*,\s*n\s*\)\s*=>/.test(source), 'should pass title option');
  assert.ok(/ancestors\(\)\s*\.\s*reverse\(\)\s*\.\s*map/.test(source), 'title should use ancestors');
  assert.ok(/\.join\s*\(\s*[''][''"]/.test(source), 'title should join ancestor names');
});

test('Tree called with link option using link_fn', () => {
  assert.ok(/link\s*:\s*link_fn/.test(source), 'should pass link_fn as link option');
});

test('Tree called with width 1152', () => {
  assert.ok(/width\s*:\s*1152/.test(source), 'Tree should use width 1152');
});

test('Tree called with height 1152', () => {
  assert.ok(/height\s*:\s*1152/.test(source), 'Tree should use height 1152');
});

test('Tree called with margin 100', () => {
  assert.ok(/margin\s*:\s*100/.test(source), 'Tree should use margin 100');
});

// ============================================================
// Render container tests
// ============================================================

test('render uses document.querySelector to find container', () => {
  assert.ok(/document\.querySelector\s*\(\s*selector\s*\)/.test(source), 'should query selector');
});

test('render appends chart via pg.appendChild', () => {
  assert.ok(/pg\.appendChild\s*\(\s*chart\s*\)/.test(source), 'should append chart to container');
});

// ============================================================
// Tree function structure tests
// ============================================================

test('source declares Tree function', () => {
  assert.ok(/function\s+Tree\s*\(\s*data\s*,/.test(source), 'should declare Tree function');
});

test('Tree function uses d3.hierarchy for hierarchical data', () => {
  assert.ok(/d3\.hierarchy\s*\(\s*data\s*,\s*children\s*\)/.test(source), 'should use d3.hierarchy');
});

test('Tree function uses d3.stratify for tabular data', () => {
  assert.ok(/d3\.stratify\(\)/.test(source), 'should support d3.stratify');
});

test('Tree function uses d3.tree layout', () => {
  assert.ok(/tree\(\)\s*\.\s*nodeSize/.test(source), 'should use d3.tree with nodeSize');
});

test('Tree function defaults width to 640', () => {
  assert.ok(/width\s*=\s*640/.test(source), 'Tree width should default to 640');
});

test('Tree function defaults r (radius) to 3', () => {
  assert.ok(/\br\s*=\s*3\b/.test(source), 'Tree node radius should default to 3');
});

test('Tree function defaults stroke to #555', () => {
  assert.ok(/stroke\s*=\s*['"]#555['"]/.test(source), 'Tree stroke should default to #555');
});

test('Tree function defaults fill to #999', () => {
  assert.ok(/fill\s*=\s*['"]#999['"]/.test(source), 'Tree fill should default to #999');
});

test('Tree function defaults strokeWidth to 1.5', () => {
  assert.ok(/strokeWidth\s*=\s*1\.5/.test(source), 'Tree strokeWidth should default to 1.5');
});

test('Tree function defaults strokeOpacity to 0.4', () => {
  assert.ok(/strokeOpacity\s*=\s*0\.4/.test(source), 'Tree strokeOpacity should default to 0.4');
});

test('Tree function defaults halo color to #d7d7af', () => {
  assert.ok(/halo\s*=\s*['"]#d7d7af['"]/.test(source), 'Tree halo should default to #d7d7af');
});

test('Tree function defaults haloWidth to 3', () => {
  assert.ok(/haloWidth\s*=\s*3/.test(source), 'Tree haloWidth should default to 3');
});

test('Tree function uses d3.curveBumpX as default curve', () => {
  assert.ok(/curve\s*=\s*d3\.curveBumpX/.test(source), 'curve should default to d3.curveBumpX');
});

// ============================================================
// SVG creation tests
// ============================================================

test('Tree creates SVG with d3.create', () => {
  assert.ok(/d3\s*\.\s*create\s*\(\s*['"]svg['"]\s*\)/.test(source), 'should create SVG via d3.create');
});

test('Tree sets viewBox attribute', () => {
  assert.ok(/\.attr\s*\(\s*['"]viewBox['"]/.test(source), 'should set viewBox');
});

test('Tree sets font-family to sans-serif', () => {
  assert.ok(/\.attr\s*\(\s*['"]font-family['"]\s*,\s*['"]sans-serif['"]/.test(source), 'should set font-family');
});

test('Tree sets font-size to 14', () => {
  assert.ok(/\.attr\s*\(\s*['"]font-size['"]\s*,\s*14/.test(source), 'should set font-size 14');
});

test('Tree SVG uses max-width: 100% and height: auto', () => {
  assert.ok(/max-width:\s*100%/.test(source), 'should set max-width 100%');
  assert.ok(/height:\s*intrinsic/.test(source), 'should set height intrinsic');
});

// ============================================================
// CSS transitions tests
// ============================================================

test('Tree adds style element with CSS transitions', () => {
  assert.ok(/\.append\s*\(\s*['"]style['"]\s*\)/.test(source), 'should append style element');
});

test('Tree sets transition on .link class', () => {
  assert.ok(/\.link\s*\{/.test(source), 'should style .link class');
  assert.ok(/transition\s*:\s*stroke-opacity\s+0\.3s/.test(source), 'should set stroke-opacity transition on links');
});

test('Tree sets transition on .node class', () => {
  assert.ok(/\.node\s*\{/.test(source), 'should style .node class');
  assert.ok(/transition\s*:\s*fill-opacity\s+0\.3s/.test(source), 'should set fill-opacity transition on nodes');
});

// ============================================================
// Mouse event handler tests
// ============================================================

test('Tree declares findConnected helper function', () => {
  assert.ok(/function\s+findConnected\s*\(\s*d\s*\)/.test(source), 'should declare findConnected');
});

test('findConnected uses ancestors() to find connected nodes', () => {
  assert.ok(/d\.ancestors\(\)\.forEach/.test(source), 'findConnected should iterate ancestors');
});

test('findConnected adds nodes and links to Sets', () => {
  assert.ok(/nodes\.add\s*\(\s*node\s*\)/.test(source), 'should add nodes to Set');
  assert.ok(/links\.add\s*\(\s*node\.parent\s*\)/.test(source), 'should add links to Set');
});

test('Tree declares handleMouseOver function', () => {
  assert.ok(/function\s+handleMouseOver\s*\(\s*event\s*,\s*d\s*\)/.test(source), 'should declare handleMouseOver');
});

test('Tree declares handleMouseOut function', () => {
  assert.ok(/function\s+handleMouseOut\s*\(\s*\)/.test(source), 'should declare handleMouseOut');
});

test('handleMouseOver dims unrelated links stroke-opacity to 0.1', () => {
  assert.ok(/stroke-opacity['"]\s*,\s*0\.1/.test(source), 'should dim stroke-opacity to 0.1');
});

test('handleMouseOver dims unrelated nodes fill-opacity to 0.1', () => {
  assert.ok(/fill-opacity['"]\s*,\s*0\.1/.test(source), 'should dim fill-opacity to 0.1');
});

test('handleMouseOut restores strokeOpacity', () => {
  assert.ok(/selectAll\s*\(\s*['"]\.link['"]\s*\)\.attr\s*\(\s*['"]stroke-opacity['"]\s*,\s*strokeOpacity/.test(source), 'should restore strokeOpacity');
});

test('handleMouseOut restores fill-opacity to 1', () => {
  assert.ok(/selectAll\s*\(\s*['"]\.node['"]\s*\)\.attr\s*\(\s*['"]fill-opacity['"]\s*,\s*1/.test(source), 'should restore fill-opacity to 1');
});

// ============================================================
// Node and link rendering tests
// ============================================================

test('Tree renders links with d3.link and curve', () => {
  assert.ok(/d3\s*\.\s*link\s*\(\s*curve\s*\)/.test(source), 'should use d3.link with curve');
});

test('Tree joins links using root.links()', () => {
  assert.ok(/root\.links\(\)/.test(source), 'should use root.links()');
});

test('Tree renders nodes using root.descendants()', () => {
  assert.ok(/root\.descendants\(\)/.test(source), 'should use root.descendants()');
});

test('Tree sets xlink:href on node anchor elements', () => {
  assert.ok(/xlink:href/.test(source), 'should set xlink:href');
});

test('Tree sets target attribute on links', () => {
  assert.ok(/['"]target['"]/.test(source), 'should set target attribute');
  assert.ok(/linkTarget/.test(source), 'should use linkTarget option');
});

test('Tree applies transform translate for node positioning', () => {
  assert.ok(/translate\(\s*\$\{d\.y\}/.test(source), 'should use transform translate with d.y');
});

test('Tree sets mouseover and mouseout on nodes', () => {
  assert.ok(/\.on\s*\(\s*['"]mouseover['"]\s*,\s*handleMouseOver/.test(source), 'should set mouseover');
  assert.ok(/\.on\s*\(\s*['"]mouseout['"]\s*,\s*handleMouseOut/.test(source), 'should set mouseout');
});

test('Tree appends circles to nodes', () => {
  assert.ok(/\.append\s*\(\s*['"]circle['"]/.test(source), 'should append circles');
});

test('Tree circles use different fill for internal vs leaf nodes', () => {
  assert.ok(/d\.children\s*\?\s*stroke\s*:\s*fill/.test(source), 'should differentiate fill for internal/leaf nodes');
});

test('Tree appends title elements for hover text', () => {
  assert.ok(/\.append\s*\(\s*['"]title['"]\)/.test(source), 'should append title elements');
});

test('Tree appends text elements for labels', () => {
  assert.ok(/\.append\s*\(\s*['"]text['"]/.test(source), 'should append text labels');
});

test('Tree labels use text-anchor for positioning', () => {
  assert.ok(/text-anchor/.test(source), 'should set text-anchor');
  assert.ok(/d\.children\s*\?\s*['"]end['"]\s*:\s*['"]start['"]/.test(source), 'should vary text-anchor by node type');
});

test('Tree labels use paint-order stroke for halo effect', () => {
  assert.ok(/paint-order/.test(source), 'should set paint-order');
  assert.ok(/stroke/.test(source), 'should use stroke for halo');
});

// ============================================================
// Error handling tests
// ============================================================

test('Tree throws error for unsupported curve', () => {
  assert.ok(/throw\s+new\s+Error\s*\(\s*['"`]Unsupported curve['"`]/.test(source), 'should throw for unsupported curve');
});

// ============================================================
// Centering logic tests
// ============================================================

test('Tree centers tree using Infinity/-Infinity bounds', () => {
  assert.ok(/let\s+x0\s*=\s*Infinity/.test(source), 'should initialize x0 to Infinity');
  assert.ok(/let\s+x1\s*=\s*-x0/.test(source), 'should initialize x1 to -x0');
});

test('Tree computes default height from x1 - x0 + dx * 2', () => {
  assert.ok(/height\s*=\s*x1\s*-\s*x0\s*\+\s*dx\s*\*\s*2/.test(source), 'should compute height from bounds');
});
