import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'geomap-tools.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class extending React.Component', () => {
  const src = readSource();
  assert.ok(
    /export default class \w+ extends React\.Component/.test(src),
    'should export a default class extending React.Component'
  );
});

test('class name is GeoMap', () => {
  const src = readSource();
  assert.ok(/export default class GeoMap/.test(src), 'should define class GeoMap');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('constructor initializes cities as new Map', () => {
  const src = readSource();
  assert.ok(/cities\s*:\s*new Map\s*\(\s*\)/.test(src), 'should set state.cities to new Map()');
});

test('constructor initializes countries as new Map', () => {
  const src = readSource();
  assert.ok(
    /countries\s*:\s*new Map\s*\(\s*\)/.test(src),
    'should set state.countries to new Map()'
  );
});

test('constructor initializes show_countries to false', () => {
  const src = readSource();
  assert.ok(/show_countries\s*:\s*false/.test(src), 'should set state.show_countries to false');
});

test('constructor initializes show_cities to false', () => {
  const src = readSource();
  assert.ok(/show_cities\s*:\s*false/.test(src), 'should set state.show_cities to false');
});

test('constructor binds updateTools method', () => {
  const src = readSource();
  assert.ok(
    /this\.updateTools\s*=\s*this\.updateTools\.bind\(this\)/.test(src),
    'should bind updateTools'
  );
});

test('constructor binds changeVisibilityState method', () => {
  const src = readSource();
  assert.ok(
    /this\.changeVisibilityState\s*=\s*this\.changeVisibilityState\.bind\(this\)/.test(src),
    'should bind changeVisibilityState'
  );
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)\s*\{/.test(src), 'should declare componentDidMount()');
});

test('componentDidMount binds MAP_UPDATED event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.MAP_UPDATED\s*,\s*this\.updateTools/.test(src),
    'should bind MAP_UPDATED to updateTools'
  );
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(
    /componentWillUnmount\s*\(\s*\)\s*\{/.test(src),
    'should declare componentWillUnmount()'
  );
});

test('componentWillUnmount unbinds MAP_UPDATED event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.MAP_UPDATED\s*,\s*this\.updateTools/.test(src),
    'should unbind MAP_UPDATED from updateTools'
  );
});

// ============================================================
// updateTools method tests
// ============================================================

test('source declares updateTools method', () => {
  const src = readSource();
  assert.ok(
    /updateTools\s*\(\s*state\s*\)\s*\{/.test(src),
    'should declare updateTools(state) method'
  );
});

test('updateTools calls this.setState', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src), 'should call this.setState(state)');
});

// ============================================================
// changeVisibilityState method tests
// ============================================================

test('source declares changeVisibilityState method', () => {
  const src = readSource();
  assert.ok(
    /changeVisibilityState\s*\(\s*e\s*\)\s*\{/.test(src),
    'should declare changeVisibilityState(e) method'
  );
});

test('changeVisibilityState gets event target element', () => {
  const src = readSource();
  assert.ok(/let el\s*=\s*e\.target/.test(src), 'should get e.target');
});

test('changeVisibilityState creates visibility_state as Object.assign copy', () => {
  const src = readSource();
  assert.ok(
    /Object\.assign\s*\(\s*\{\s*\}\s*,\s*this\.state\s*\)/.test(src),
    'should copy state with Object.assign'
  );
});

test('changeVisibilityState tracks changed flag', () => {
  const src = readSource();
  assert.ok(/changed\s*=\s*false/.test(src), 'should initialize changed = false');
});

test('changeVisibilityState handles countries_checkbox', () => {
  const src = readSource();
  assert.ok(
    /el\.id\s*===\s*['"]countries_checkbox['"]/.test(src),
    'should check for countries_checkbox'
  );
  assert.ok(
    /visibility_state\.show_countries\s*=\s*!\s*this\.state\.show_countries/.test(src),
    'should toggle show_countries'
  );
});

test('changeVisibilityState handles cities_checkbox', () => {
  const src = readSource();
  assert.ok(/el\.id\s*===\s*['"]cities_checkbox['"]/.test(src), 'should check for cities_checkbox');
  assert.ok(
    /visibility_state\.show_cities\s*=\s*!\s*this\.state\.show_cities/.test(src),
    'should toggle show_cities'
  );
});

test('changeVisibilityState triggers CHANGE_MAP_OBJECTS_VISIBILITY only when changed', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*changed\s*\)/.test(src), 'should check if(changed)');
  assert.ok(
    /this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.CHANGE_MAP_OBJECTS_VISIBILITY/.test(src),
    'should trigger CHANGE_MAP_OBJECTS_VISIBILITY'
  );
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('render returns div wrapper', () => {
  const src = readSource();
  assert.ok(/return\s*\(\s*<div>/.test(src), 'should render wrapper div');
});

test('render includes countries checkbox input', () => {
  const src = readSource();
  assert.ok(/type\s*=\s*['"]checkbox['"]/.test(src), 'should render checkbox input');
  assert.ok(/id\s*=\s*['"]countries_checkbox['"]/.test(src), 'should set id="countries_checkbox"');
});

test('render includes cities checkbox input', () => {
  const src = readSource();
  assert.ok(/id\s*=\s*['"]cities_checkbox['"]/.test(src), 'should set id="cities_checkbox"');
});

test('render binds checked state to show_countries', () => {
  const src = readSource();
  assert.ok(
    /checked\s*=\s*\{\s*this\.state\.show_countries\s*\}/.test(src),
    'should bind checked to state.show_countries'
  );
});

test('render binds checked state to show_cities', () => {
  const src = readSource();
  assert.ok(
    /checked\s*=\s*\{\s*this\.state\.show_cities\s*\}/.test(src),
    'should bind checked to state.show_cities'
  );
});

test('render binds onChange to changeVisibilityState', () => {
  const src = readSource();
  assert.ok(
    /onChange\s*=\s*\{?\s*this\.changeVisibilityState/.test(src),
    'should bind onChange to changeVisibilityState'
  );
});

test('render displays countries count using Map.size', () => {
  const src = readSource();
  assert.ok(/\{this\.state\.countries\.size\}/.test(src), 'should render countries.size');
});

test('render displays cities count using Map.size', () => {
  const src = readSource();
  assert.ok(/\{this\.state\.cities\.size\}/.test(src), 'should render cities.size');
});

test('render uses label with htmlFor for countries', () => {
  const src = readSource();
  assert.ok(
    /htmlFor\s*=\s*['"]countries_checkbox['"]/.test(src),
    'should set htmlFor="countries_checkbox"'
  );
});

test('render uses label with htmlFor for cities', () => {
  const src = readSource();
  assert.ok(
    /htmlFor\s*=\s*['"]cities_checkbox['"]/.test(src),
    'should set htmlFor="cities_checkbox"'
  );
});

test('render displays "Show countries" text', () => {
  const src = readSource();
  assert.ok(/Show countries/.test(src), 'should include "Show countries" text');
});

test('render displays "Show cities" text', () => {
  const src = readSource();
  assert.ok(/Show cities/.test(src), 'should include "Show cities" text');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src), 'should import React');
});

test('source has no additional imports', () => {
  const src = readSource();
  const importCount = (src.match(/^import /gm) || []).length;
  assert.equal(importCount, 1, 'should only have the React import');
});
