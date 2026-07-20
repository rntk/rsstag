import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'load-posts.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a named class LoadPosts (not default)', () => {
  const src = readSource();
  assert.ok(/export class LoadPosts/.test(src), 'should export a named class LoadPosts');
  assert.ok(!/export default class LoadPosts/.test(src), 'should not be a default export');
});

test('class extends React.Component', () => {
  const src = readSource();
  assert.ok(/class LoadPosts extends React\.Component/.test(src), 'should extend React.Component');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('constructor binds loadMore method', () => {
  const src = readSource();
  assert.ok(/this\.loadMore\s*=\s*this\.loadMore\.bind\(this\)/.test(src), 'should bind loadMore');
});

test('constructor does not initialize state', () => {
  const src = readSource();
  assert.ok(!/this\.state\s*=/.test(src), 'should not initialize state');
});

// ============================================================
// loadMore method tests
// ============================================================

test('source declares loadMore method', () => {
  const src = readSource();
  assert.ok(/loadMore\s*\(\s*\)\s*\{/.test(src), 'should declare loadMore() method');
});

test('loadMore triggers LOAD_MORE_POSTS event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.LOAD_MORE_POSTS/.test(src),
    'should trigger LOAD_MORE_POSTS'
  );
});

test('loadMore does not pass any payload', () => {
  const src = readSource();
  assert.ok(/LOAD_MORE_POSTS\s*\)/.test(src), 'should trigger LOAD_MORE_POSTS without payload');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('render returns div with load_more_posts CSS class', () => {
  const src = readSource();
  assert.ok(
    /className\s*=\s*['"]load_more_posts['"]/.test(src),
    'should set className="load_more_posts"'
  );
});

test('render includes a button element', () => {
  const src = readSource();
  assert.ok(/<button/.test(src), 'should render a button element');
});

test('render binds onClick to loadMore', () => {
  const src = readSource();
  assert.ok(/onClick\s*=\s*\{?\s*this\.loadMore/.test(src), 'should bind onClick to loadMore');
});

test('render displays "Load more" text on button', () => {
  const src = readSource();
  assert.ok(/Load more/.test(src), 'should display "Load more" on button');
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
