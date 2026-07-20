import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'readall-button.js');

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

test('class name is ReadAllButton', () => {
  const src = readSource();
  assert.ok(/export default class ReadAllButton/.test(src), 'should define class ReadAllButton');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('constructor initializes state with ids array and readed boolean', () => {
  const src = readSource();
  assert.ok(
    /this\.state\s*=\s*\{[\s\S]*?ids\s*:\s*\[\]/.test(src),
    'should set state.ids to empty array'
  );
  assert.ok(
    /this\.state\s*=\s*\{[\s\S]*?readed\s*:\s*false/.test(src),
    'should set state.readed to false'
  );
});

test('constructor binds changePostsStatus method', () => {
  const src = readSource();
  assert.ok(
    /this\.changePostsStatus\s*=\s*this\.changePostsStatus\.bind\(this\)/.test(src),
    'should bind changePostsStatus'
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

test('updatePosts sets readed from state.readed', () => {
  const src = readSource();
  assert.ok(/readed\s*:\s*state\.readed/.test(src), 'should set readed from state.readed');
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
// changePostsStatus method tests
// ============================================================

test('source declares changePostsStatus method', () => {
  const src = readSource();
  assert.ok(
    /changePostsStatus\s*\(\s*e\s*\)\s*\{/.test(src),
    'should declare changePostsStatus(e)'
  );
});

test('changePostsStatus creates data with ids copy and toggled readed', () => {
  const src = readSource();
  assert.ok(
    /ids\s*:\s*this\.state\.ids\.slice\s*\(\s*0\s*\)/.test(src),
    'should copy ids with slice(0)'
  );
  assert.ok(/readed\s*:\s*!\s*this\.state\.readed/.test(src), 'should toggle readed state');
});

test('changePostsStatus triggers CHANGE_POSTS_STATUS event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.CHANGE_POSTS_STATUS/.test(src),
    'should trigger CHANGE_POSTS_STATUS'
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

test('render binds onClick to changePostsStatus', () => {
  const src = readSource();
  assert.ok(
    /onClick\s*=\s*\{?\s*this\.changePostsStatus/.test(src),
    'should bind onClick to changePostsStatus'
  );
});

test('render conditionally shows unread/read text', () => {
  const src = readSource();
  assert.ok(
    /this\.state\.readed\s*\?\s*['"]unread['"]/.test(src),
    'should show "unread" when readed is true'
  );
  assert.ok(/:\s*['"]read['"]/.test(src), 'should show "read" when readed is false');
});

test('render includes " all" text', () => {
  const src = readSource();
  assert.ok(/['"]?\s*all['"]?\s*</.test(src) || /} all</.test(src), 'should include " all" text');
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
