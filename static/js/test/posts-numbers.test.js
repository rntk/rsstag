import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'posts-numbers.js');

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

test('class name is PostsNumbers', () => {
  const src = readSource();
  assert.ok(/export default class PostsNumbers/.test(src),
    'should define class PostsNumbers');
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

test('constructor initializes _default_state with read, unread, all', () => {
  const src = readSource();
  assert.ok(/this\._default_state\s*=\s*\{[\s\S]*?read\s*:\s*0/.test(src),
    'should set _default_state.read to 0');
  assert.ok(/this\._default_state\s*=\s*\{[\s\S]*?unread\s*:\s*0/.test(src),
    'should set _default_state.unread to 0');
  assert.ok(/this\._default_state\s*=\s*\{[\s\S]*?all\s*:\s*0/.test(src),
    'should set _default_state.all to 0');
});

test('constructor copies _default_state into state', () => {
  const src = readSource();
  assert.ok(/Object\.assign\s*\(\s*\{\s*\}\s*,\s*this\._default_state\s*\)/.test(src),
    'should use Object.assign to copy _default_state');
});

test('constructor binds updateNumbers method', () => {
  const src = readSource();
  assert.ok(/this\.updateNumbers\s*=\s*this\.updateNumbers\.bind\(this\)/.test(src),
    'should bind updateNumbers');
});

// ============================================================
// updateNumbers method tests
// ============================================================

test('source declares updateNumbers method', () => {
  const src = readSource();
  assert.ok(/updateNumbers\s*\(\s*posts_state\s*\)\s*\{/.test(src),
    'should declare updateNumbers(posts_state) method');
});

test('updateNumbers creates fresh state from _default_state', () => {
  const src = readSource();
  assert.ok(/Object\.assign\s*\(\s*\{\s*\}\s*,\s*this\._default_state\s*\)/.test(src),
    'should create new state from _default_state');
});

test('updateNumbers iterates over posts_state.posts', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let item of posts_state\.posts/.test(src),
    'should iterate over posts_state.posts');
});

test('updateNumbers accesses post via item[1]', () => {
  const src = readSource();
  assert.ok(/let post\s*=\s*item\[1\]/.test(src),
    'should get post from item[1]');
});

test('updateNumbers checks post.post.read for read/unread', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*post\.post\.read\s*\)/.test(src),
    'should check post.post.read');
});

test('updateNumbers increments state.read for read posts', () => {
  const src = readSource();
  assert.ok(/state\.read\+\+/.test(src),
    'should increment state.read');
});

test('updateNumbers increments state.unread for unread posts', () => {
  const src = readSource();
  assert.ok(/state\.unread\+\+/.test(src),
    'should increment state.unread');
});

test('updateNumbers calculates state.all as sum of read and unread', () => {
  const src = readSource();
  assert.ok(/state\.all\s*=\s*state\.unread\s*\+\s*state\.read/.test(src),
    'should calculate all = unread + read');
});

test('updateNumbers calls this.setState', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src),
    'should call this.setState(state)');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)\s*\{/.test(src),
    'should declare componentDidMount()');
});

test('componentDidMount binds POSTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.POSTS_UPDATED\s*,\s*this\.updateNumbers/.test(src),
    'should bind POSTS_UPDATED to updateNumbers');
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentWillUnmount\s*\(\s*\)\s*\{/.test(src),
    'should declare componentWillUnmount()');
});

test('componentWillUnmount unbinds POSTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.POSTS_UPDATED\s*,\s*this\.updateNumbers/.test(src),
    'should unbind POSTS_UPDATED from updateNumbers');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render checks this.state for truthy render path', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*this\.state\s*\)/.test(src),
    'should check if(this.state)');
});

test('render returns p with unread / read format', () => {
  const src = readSource();
  assert.ok(/<p>/.test(src),
    'should render a p element');
  assert.ok(/\{this\.state\.unread\}/.test(src),
    'should render state.unread');
  assert.ok(/\/ /.test(src),
    'should include " / " separator');
  assert.ok(/\{this\.state\.read\}/.test(src),
    'should render state.read');
});

test('render has fallback path showing 0/0', () => {
  const src = readSource();
  assert.ok(/<p>0\/0<\/p>/.test(src),
    'should render "0/0" fallback');
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
