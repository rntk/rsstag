import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'river-legend.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class', () => {
  const src = readSource();
  assert.ok(/export default class RiverLegend/.test(src),
    'should export a default class RiverLegend');
});

test('class does not extend React.Component (vanilla JS)', () => {
  const src = readSource();
  assert.ok(!/extends React/.test(src),
    'should not extend React.Component');
});

test('constructor accepts container and options parameters', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*container\s*,\s*options\s*=\s*\{\}\s*\)/.test(src),
    'should have constructor(container, options = {})');
});

test('constructor handles string container with document.querySelector', () => {
  const src = readSource();
  assert.ok(/typeof container === ['"]string['"]/.test(src),
    'should check if container is a string');
  assert.ok(/document\.querySelector/.test(src),
    'should use document.querySelector for string containers');
});

test('constructor handles DOM element container', () => {
  const src = readSource();
  assert.ok(/:\s*container/.test(src),
    'should use container directly if not a string');
});

test('constructor sets items from options with default empty array', () => {
  const src = readSource();
  assert.ok(/this\.items\s*=\s*options\.items\s*\|\|\s*\[\]/.test(src),
    'should set items from options.items or default to []');
});

test('constructor sets colorScale from options', () => {
  const src = readSource();
  assert.ok(/this\.colorScale\s*=\s*options\.colorScale/.test(src),
    'should set colorScale from options');
});

test('constructor sets onActivate callback with default noop', () => {
  const src = readSource();
  assert.ok(/this\.onActivate\s*=\s*options\.onActivate\s*\|\|\s*\(?\s*\(\s*\)\s*=>\s*\{\}\s*\)?/.test(src),
    'should set onActivate with default noop function');
});

test('constructor initializes activeItem to null', () => {
  const src = readSource();
  assert.ok(/this\.activeItem\s*=\s*null/.test(src),
    'should initialize activeItem to null');
});

test('constructor sets variant from options with default value', () => {
  const src = readSource();
  assert.ok(/this\.variant\s*=\s*options\.variant\s*\|\|\s*['"]default['"]/.test(src),
    'should set variant from options.variant or default to "default"');
});

// ============================================================
// update method tests
// ============================================================

test('source declares update method', () => {
  const src = readSource();
  assert.ok(/update\s*\(\s*activeItem\s*\)\s*\{/.test(src),
    'should declare update(activeItem) method');
});

test('update sets this.activeItem', () => {
  const src = readSource();
  assert.ok(/this\.activeItem\s*=\s*activeItem/.test(src),
    'should set this.activeItem');
});

test('update calls this.render()', () => {
  const src = readSource();
  assert.ok(/this\.render\s*\(\s*\)/.test(src),
    'should call this.render()');
});

// ============================================================
// render method tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render returns early if container is falsy', () => {
  const src = readSource();
  assert.ok(/!this\.container/.test(src),
    'should check for falsy container');
});

test('render returns early if items is falsy', () => {
  const src = readSource();
  assert.ok(/!this\.items/.test(src),
    'should check for falsy items');
});

test('render returns early if items array is empty', () => {
  const src = readSource();
  assert.ok(/this\.items\.length\s*===\s*0/.test(src),
    'should check for empty items array');
});

test('render clears container innerHTML', () => {
  const src = readSource();
  assert.ok(/this\.container\.innerHTML\s*=\s*['']/.test(src),
    'should clear container innerHTML');
});

test('render sets CSS classes with variant', () => {
  const src = readSource();
  assert.ok(/this\.container\.className\s*=\s*`river-legend river-legend-\$\{this\.variant\}`/.test(src),
    'should set river-legend and river-legend-{variant} classes');
});

test('render applies flex layout styles', () => {
  const src = readSource();
  assert.ok(/display\s*:\s*['"]flex['"]/.test(src),
    'should set display to flex');
  assert.ok(/flexWrap\s*:\s*['"]wrap['"]/.test(src),
    'should set flexWrap to wrap');
});

test('render uses Object.assign for container styles', () => {
  const src = readSource();
  assert.ok(/Object\.assign\s*\(\s*this\.container\.style/.test(src),
    'should use Object.assign for container styles');
});

// ============================================================
// Legend item rendering tests
// ============================================================

test('render iterates over items with forEach', () => {
  const src = readSource();
  assert.ok(/this\.items\.forEach/.test(src),
    'should iterate over items with forEach');
});

test('render resolves item name from item.name or item itself', () => {
  const src = readSource();
  assert.ok(/const name\s*=\s*item\.name\s*\|\|\s*item/.test(src),
    'should get name from item.name or item');
});

test('render calculates isActive based on activeItem match', () => {
  const src = readSource();
  assert.ok(/const isActive\s*=\s*this\.activeItem\s*===\s*name/.test(src),
    'should calculate isActive');
});

test('render calculates isDimmed for non-active items', () => {
  const src = readSource();
  assert.ok(/const isDimmed\s*=\s*this\.activeItem\s*&&\s*this\.activeItem\s*!==\s*name/.test(src),
    'should calculate isDimmed');
});

test('render creates legend item div', () => {
  const src = readSource();
  assert.ok(/document\.createElement\s*\(\s*['"]div['"]\s*\)/.test(src),
    'should create div for legend item');
});

test('render sets river-legend-item class on item', () => {
  const src = readSource();
  assert.ok(/el\.className\s*=\s*['"]river-legend-item['"]/.test(src),
    'should set river-legend-item class');
});

// ============================================================
// Variant-specific styling tests
// ============================================================

test('render handles pill variant padding', () => {
  const src = readSource();
  assert.ok(/this\.variant\s*===\s*['"]pill['"]/.test(src),
    'should check for pill variant');
  assert.ok(/['"]6px 12px['"]/.test(src),
    'should use 6px 12px padding for pill');
  assert.ok(/['"]4px 8px['"]/.test(src),
    'should use 4px 8px padding for default');
});

test('render handles pill variant border and borderRadius', () => {
  const src = readSource();
  assert.ok(/['"]1px solid #ddd['"]/.test(src),
    'should set border for pill variant');
  assert.ok(/['"]20px['"]/.test(src),
    'should set borderRadius 20px for pill');
  assert.ok(/['"]4px['"]/.test(src),
    'should set borderRadius 4px for default');
});

test('render handles pill variant colorBox shape', () => {
  const src = readSource();
  assert.ok(/borderRadius\s*:\s*this\.variant\s*===\s*['"]pill['"]\s*\?\s*['"]50%['"]/.test(src),
    'should set circular colorBox for pill');
  assert.ok(/['"]2px['"]/.test(src),
    'should set square colorBox for default');
});

// ============================================================
// Color and label rendering tests
// ============================================================

test('render creates colorBox element', () => {
  const src = readSource();
  assert.ok(/const colorBox\s*=\s*document\.createElement\s*\(\s*['"]div['"]\s*\)/.test(src),
    'should create colorBox div');
});

test('render calls colorScale(name) for background color', () => {
  const src = readSource();
  assert.ok(/this\.colorScale\s*\(\s*name\s*\)/.test(src),
    'should call colorScale(name) for color');
});

test('colorBox has 12px dimensions', () => {
  const src = readSource();
  assert.ok(/width\s*:\s*['"]12px['"]/.test(src),
    'should set 12px width');
  assert.ok(/height\s*:\s*['"]12px['"]/.test(src),
    'should set 12px height');
});

test('render creates label span element', () => {
  const src = readSource();
  assert.ok(/const label\s*=\s*document\.createElement\s*\(\s*['"]span['"]\s*\)/.test(src),
    'should create label span');
});

test('render sets label textContent to name', () => {
  const src = readSource();
  assert.ok(/label\.textContent\s*=\s*name/.test(src),
    'should set label textContent');
});

test('render appends colorBox and label to item', () => {
  const src = readSource();
  assert.ok(/el\.appendChild\s*\(\s*colorBox\s*\)/.test(src),
    'should append colorBox');
  assert.ok(/el\.appendChild\s*\(\s*label\s*\)/.test(src),
    'should append label');
});

test('render appends item to container', () => {
  const src = readSource();
  assert.ok(/this\.container\.appendChild\s*\(\s*el\s*\)/.test(src),
    'should append item to container');
});

// ============================================================
// Event handling tests
// ============================================================

test('render adds mouseenter event listener', () => {
  const src = readSource();
  assert.ok(/addEventListener\s*\(\s*['"]mouseenter['"]/.test(src),
    'should add mouseenter listener');
  assert.ok(/this\.onActivate\s*\(\s*name\s*\)/.test(src),
    'should call onActivate(name) on mouseenter');
});

test('render adds mouseleave event listener', () => {
  const src = readSource();
  assert.ok(/addEventListener\s*\(\s*['"]mouseleave['"]/.test(src),
    'should add mouseleave listener');
  assert.ok(/this\.onActivate\s*\(\s*null\s*\)/.test(src),
    'should call onActivate(null) on mouseleave');
});

// ============================================================
// Import and structure tests
// ============================================================

test('source has no React import', () => {
  const src = readSource();
  assert.ok(!/import.*React/.test(src),
    'should not import React');
});

test('source has no import statements (pure vanilla JS)', () => {
  const src = readSource();
  assert.ok(!/^import /m.test(src),
    'should have no imports');
});
