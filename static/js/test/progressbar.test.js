import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'progressbar.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class extending React.Component', () => {
  const src = readSource();
  assert.ok(/export default class \w+ extends React\.Component/.test(src),
    'should export a default class extending React.Component');
});

test('class name is ProgressBar', () => {
  const src = readSource();
  assert.ok(/export default class ProgressBar/.test(src),
    'should define class ProgressBar');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src),
    'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src),
    'should call super(props)');
});

test('constructor initializes state with tasks array and progress 0', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?tasks\s*:\s*\[\]/.test(src),
    'should set state.tasks to empty array');
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?progress\s*:\s*0/.test(src),
    'should set state.progress to 0');
});

test('constructor binds changeFilling method', () => {
  const src = readSource();
  assert.ok(/this\.changeFilling\s*=\s*this\.changeFilling\.bind\(this\)/.test(src),
    'should bind changeFilling');
});

test('constructor binds animationEnd method', () => {
  const src = readSource();
  assert.ok(/this\.animationEnd\s*=\s*this\.animationEnd\.bind\(this\)/.test(src),
    'should bind animationEnd');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)\s*\{/.test(src),
    'should declare componentDidMount()');
});

test('componentDidMount binds CHANGE_PROGRESSBAR event', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.CHANGE_PROGRESSBAR\s*,\s*this\.changeFilling/.test(src),
    'should bind CHANGE_PROGRESSBAR to changeFilling');
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentWillUnmount\s*\(\s*\)\s*\{/.test(src),
    'should declare componentWillUnmount()');
});

test('componentWillUnmount unbinds CHANGE_PROGRESSBAR event', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.CHANGE_PROGRESSBAR\s*,\s*this\.changeFilling/.test(src),
    'should unbind CHANGE_PROGRESSBAR from changeFilling');
});

// ============================================================
// animationEnd method tests
// ============================================================

test('source declares animationEnd method', () => {
  const src = readSource();
  assert.ok(/animationEnd\s*\(\s*\)\s*\{/.test(src),
    'should declare animationEnd() method');
});

test('animationEnd triggers PROGRESSBAR_ANIMATION_END event', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.PROGRESSBAR_ANIMATION_END/.test(src),
    'should trigger PROGRESSBAR_ANIMATION_END');
});

// ============================================================
// changeFilling method tests
// ============================================================

test('source declares changeFilling method', () => {
  const src = readSource();
  assert.ok(/changeFilling\s*\(\s*state\s*\)\s*\{/.test(src),
    'should declare changeFilling(state) method');
});

test('changeFilling calls this.setState with state parameter', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src),
    'should call this.setState(state)');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render returns div with filling CSS class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]filling['"]/.test(src),
    'should set className="filling"');
});

test('render uses onTransitionEnd for animationEnd', () => {
  const src = readSource();
  assert.ok(/onTransitionEnd\s*=\s*\{?\s*this\.animationEnd/.test(src),
    'should bind onTransitionEnd to animationEnd');
});

test('render sets display based on progress > 0', () => {
  const src = readSource();
  assert.ok(/this\.state\.progress\s*>\s*0\s*\?\s*['"]block['"]/.test(src),
    'should display "block" when progress > 0');
  assert.ok(/:\s*['"]none['"]/.test(src),
    'should display "none" when progress <= 0');
});

test('render sets width to progress percentage', () => {
  const src = readSource();
  assert.ok(/width\s*:\s*this\.state\.progress\s*\+\s*['"]%['"]/.test(src),
    'should set width to progress + "%"');
});

test('render style object contains display and width', () => {
  const src = readSource();
  assert.ok(/display\s*:/.test(src),
    'should have display in style');
  assert.ok(/width\s*:/.test(src),
    'should have width in style');
});

test('render div is self-closing (no children)', () => {
  const src = readSource();
  assert.ok(/<div className="filling"[^>]*><\/div>/.test(src),
    'should render empty div');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});

test('source has no additional imports', () => {
  const src = readSource();
  const importCount = (src.match(/^import /gm) || []).length;
  assert.equal(importCount, 1,
    'should only have the React import');
});
