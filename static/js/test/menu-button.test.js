import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'menu-button.js');

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

test('class name is SettingsMenuButton', () => {
  const src = readSource();
  assert.ok(
    /export default class SettingsMenuButton/.test(src),
    'should define class SettingsMenuButton'
  );
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('constructor binds changeMenuState method', () => {
  const src = readSource();
  assert.ok(
    /this\.changeMenuState\s*=\s*this\.changeMenuState\.bind\(this\)/.test(src),
    'should bind changeMenuState'
  );
});

test('constructor does not initialize state', () => {
  const src = readSource();
  assert.ok(!/this\.state\s*=/.test(src), 'should not initialize state');
});

// ============================================================
// changeMenuState method tests
// ============================================================

test('source declares changeMenuState method', () => {
  const src = readSource();
  assert.ok(
    /changeMenuState\s*\(\s*e\s*\)\s*\{/.test(src),
    'should declare changeMenuState(e) method'
  );
});

test('changeMenuState calls getBoundingClientRect on event target', () => {
  const src = readSource();
  assert.ok(
    /e\.target\.getBoundingClientRect\s*\(\s*\)/.test(src),
    'should call e.target.getBoundingClientRect()'
  );
});

test('changeMenuState calculates top offset', () => {
  const src = readSource();
  assert.ok(
    /top\s*:\s*rect\.top\s*\+\s*rect\.height/.test(src),
    'should calculate top = rect.top + rect.height'
  );
});

test('changeMenuState calculates right offset', () => {
  const src = readSource();
  assert.ok(
    /right\s*:\s*document\.body\.offsetWidth\s*-\s*rect\.left/.test(src),
    'should calculate right = document.body.offsetWidth - rect.left'
  );
});

test('changeMenuState triggers CHANGE_SETTINGS_WINDOW_STATE event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.CHANGE_SETTINGS_WINDOW_STATE/.test(src),
    'should trigger CHANGE_SETTINGS_WINDOW_STATE'
  );
});

test('changeMenuState passes offset object as event payload', () => {
  const src = readSource();
  assert.ok(/offset\s*\)/.test(src), 'should pass offset as payload');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('render returns span element', () => {
  const src = readSource();
  assert.ok(/<span/.test(src), 'should render a span element');
});

test('render sets main_menu_button CSS class', () => {
  const src = readSource();
  assert.ok(
    /className\s*=\s*['"]main_menu_button['"]/.test(src),
    'should set className="main_menu_button"'
  );
});

test('render binds onClick to changeMenuState', () => {
  const src = readSource();
  assert.ok(
    /onClick\s*=\s*\{?\s*this\.changeMenuState/.test(src),
    'should bind onClick to changeMenuState'
  );
});

test('render displays hamburger/equiv entity', () => {
  const src = readSource();
  assert.ok(/&equiv;/.test(src), 'should render &equiv; (hamburger menu icon)');
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

test('component does not declare lifecycle methods', () => {
  const src = readSource();
  assert.ok(!/componentDidMount/.test(src), 'should not have componentDidMount');
  assert.ok(!/componentWillUnmount/.test(src), 'should not have componentWillUnmount');
});
