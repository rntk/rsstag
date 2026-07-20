import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'showall-button.js');

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

test('class name is ShowAllButton', () => {
  const src = readSource();
  assert.ok(/export default class ShowAllButton/.test(src), 'should define class ShowAllButton');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('constructor initializes state with ids array and showed boolean', () => {
  const src = readSource();
  assert.ok(
    /this\.state\s*=\s*\{[\s\S]*?ids\s*:\s*\[\]/.test(src),
    'should set state.ids to empty array'
  );
  assert.ok(
    /this\.state\s*=\s*\{[\s\S]*?showed\s*:\s*false/.test(src),
    'should set state.showed to false'
  );
});

test('constructor binds changePostsContentState method', () => {
  const src = readSource();
  assert.ok(
    /this\.changePostsContentState\s*=\s*this\.changePostsContentState\.bind\(this\)/.test(src),
    'should bind changePostsContentState'
  );
});

test('constructor binds updatePosts method', () => {
  const src = readSource();
  assert.ok(
    /this\.updatePosts\s*=\s*this\.updatePosts\.bind\(this\)/.test(src),
    'should bind updatePosts'
  );
});

// ============================================================
// isShowed method tests
// ============================================================

test('source declares isShowed method', () => {
  const src = readSource();
  assert.ok(/isShowed\s*\(\s*state\s*\)\s*\{/.test(src), 'should declare isShowed(state) method');
});

test('isShowed iterates over state.posts', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let item of state\.posts/.test(src), 'should iterate over state.posts');
});

test('isShowed checks item[1].showed property', () => {
  const src = readSource();
  assert.ok(/item\[1\]\.showed/.test(src), 'should check item[1].showed');
});

test('isShowed breaks early when showed is true', () => {
  const src = readSource();
  assert.ok(
    /if\s*\(\s*showed\s*\)\s*\{\s*break\s*;?\s*\}/.test(src),
    'should break early when showed is found'
  );
});

test('isShowed initializes showed to false', () => {
  const src = readSource();
  assert.ok(/let showed\s*=\s*false/.test(src), 'should initialize showed = false');
});

// ============================================================
// updatePosts method tests
// ============================================================

test('source declares updatePosts method', () => {
  const src = readSource();
  assert.ok(
    /updatePosts\s*\(\s*state\s*\)\s*\{/.test(src),
    'should declare updatePosts(state) method'
  );
});

test('updatePosts extracts ids using Array.from(state.posts.keys())', () => {
  const src = readSource();
  assert.ok(
    /ids\s*:\s*Array\.from\s*\(\s*state\.posts\.keys\s*\(\s*\)\s*\)/.test(src),
    'should use Array.from(state.posts.keys()) for ids'
  );
});

test('updatePosts calls this.isShowed(state)', () => {
  const src = readSource();
  assert.ok(
    /showed\s*:\s*this\.isShowed\s*\(\s*state\s*\)/.test(src),
    'should call this.isShowed(state)'
  );
});

test('updatePosts calls this.setState', () => {
  const src = readSource();
  assert.ok(
    /this\.setState\s*\(\s*new_state\s*\)/.test(src),
    'should call this.setState(new_state)'
  );
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)\s*\{/.test(src), 'should declare componentDidMount()');
});

test('componentDidMount binds POSTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.POSTS_UPDATED\s*,\s*this\.updatePosts/.test(src),
    'should bind POSTS_UPDATED to updatePosts'
  );
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(
    /componentWillUnmount\s*\(\s*\)\s*\{/.test(src),
    'should declare componentWillUnmount()'
  );
});

test('componentWillUnmount unbinds POSTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.POSTS_UPDATED\s*,\s*this\.updatePosts/.test(
      src
    ),
    'should unbind POSTS_UPDATED from updatePosts'
  );
});

// ============================================================
// changePostsContentState method tests
// ============================================================

test('source declares changePostsContentState method', () => {
  const src = readSource();
  assert.ok(
    /changePostsContentState\s*\(\s*e\s*\)\s*\{/.test(src),
    'should declare changePostsContentState(e)'
  );
});

test('changePostsContentState creates data with ids copy and toggled showed', () => {
  const src = readSource();
  assert.ok(
    /ids\s*:\s*this\.state\.ids\.slice\s*\(\s*0\s*\)/.test(src),
    'should copy ids with slice(0)'
  );
  assert.ok(/showed\s*:\s*!\s*this\.state\.showed/.test(src), 'should toggle showed state');
});

test('changePostsContentState triggers CHANGE_POSTS_CONTENT_STATE event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.CHANGE_POSTS_CONTENT_STATE/.test(src),
    'should trigger CHANGE_POSTS_CONTENT_STATE'
  );
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

test('render binds onClick to changePostsContentState', () => {
  const src = readSource();
  assert.ok(
    /onClick\s*=\s*\{?\s*this\.changePostsContentState/.test(src),
    'should bind onClick to changePostsContentState'
  );
});

test('render conditionally shows hide/show text', () => {
  const src = readSource();
  assert.ok(
    /this\.state\.showed\s*\?\s*['"]hide['"]/.test(src),
    'should show "hide" when showed is true'
  );
  assert.ok(/:\s*['"]show['"]/.test(src), 'should show "show" when showed is false');
});

test('render includes " all" text', () => {
  const src = readSource();
  assert.ok(
    /['"]?\s*all['"]?\s*</.test(src) || /} all</.test(src),
    'should include " all" text after hide/show'
  );
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
