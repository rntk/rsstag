import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'categories-list.js');

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

test('class name is CategoriesList', () => {
  const src = readSource();
  assert.ok(/export default class CategoriesList/.test(src),
    'should define class CategoriesList');
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

test('constructor initializes state with cats from window.initial_cats_list', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?cats\s*:\s*window\.initial_cats_list/.test(src),
    'should set state.cats from window.initial_cats_list');
});

// ============================================================
// Method declaration tests
// ============================================================

test('source declares changeFeedsState method', () => {
  const src = readSource();
  assert.ok(/changeFeedsState\s*\(/.test(src),
    'should declare changeFeedsState() method');
});

test('changeFeedsState accepts cat_name parameter', () => {
  const src = readSource();
  assert.ok(/changeFeedsState\s*\(\s*cat_name/.test(src),
    'should accept cat_name parameter');
});

test('changeFeedsState uses Object.assign to copy state', () => {
  const src = readSource();
  assert.ok(/Object\.assign\s*\(\s*\{\s*\}/.test(src),
    'should use Object.assign for shallow copy');
});

test('changeFeedsState toggles showed flag', () => {
  const src = readSource();
  assert.ok(/showed\s*=\s*!state\.cats\[cat_name\]\.showed/.test(src) ||
    /showed\s*=\s*!.*showed/.test(src),
    'should toggle showed flag');
});

test('changeFeedsState calls setState', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src),
    'should call setState');
});

test('changeFeedsState checks category existence with in operator', () => {
  const src = readSource();
  assert.ok(/cat_name in state\.cats/.test(src),
    'should check if cat_name exists in state.cats');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render checks for state and cats existence', () => {
  const src = readSource();
  assert.ok(/this\.state && this\.state\.cats/.test(src),
    'should check state and state.cats');
});

test('render returns "No categories" paragraph when empty', () => {
  const src = readSource();
  assert.ok(/<p>No categories<\/p>/.test(src),
    'should return <p>No categories</p> when empty');
});

test('render returns ul element for categories', () => {
  const src = readSource();
  assert.ok(/return\s*<ul/.test(src),
    'should return <ul> element');
});

test('render iterates over state.cats with for...in', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let\s+cat_name\s+in\s+this\.state\.cats/.test(src),
    'should use for...in over state.cats');
});

test('render uses hasOwnProperty check', () => {
  const src = readSource();
  assert.ok(/hasOwnProperty\s*\(\s*cat_name\s*\)/.test(src),
    'should check hasOwnProperty');
});

// ============================================================
// Category rendering tests
// ============================================================

test('render uses category CSS class', () => {
  const src = readSource();
  assert.ok(/['"]category['"]/.test(src),
    'should use category CSS class');
});

test('render uses category-header CSS class', () => {
  const src = readSource();
  assert.ok(/category-header/.test(src),
    'should use category-header CSS class');
});

test('render uses show_btn CSS class', () => {
  const src = readSource();
  assert.ok(/show_btn/.test(src),
    'should use show_btn CSS class');
});

test('render uses not_minimized class for expanded', () => {
  const src = readSource();
  assert.ok(/not_minimized/.test(src),
    'should use not_minimized class');
});

test('render uses minimized class for collapsed', () => {
  const src = readSource();
  assert.ok(/minimized/.test(src),
    'should use minimized class');
});

test('render shows expand/collapse conditionally on showed state', () => {
  const src = readSource();
  assert.ok(/cat\.showed/.test(src),
    'should check cat.showed for visibility class');
});

test('render uses category-count CSS class', () => {
  const src = readSource();
  assert.ok(/category-count/.test(src),
    'should use category-count CSS class');
});

test('render displays unread_count', () => {
  const src = readSource();
  assert.ok(/cat\.unread_count/.test(src) || /unread_count/.test(src),
    'should display unread_count');
});

test('render links to cat.url', () => {
  const src = readSource();
  assert.ok(/cat\.url/.test(src),
    'should link to cat.url');
});

test('render displays cat.title', () => {
  const src = readSource();
  assert.ok(/cat\.title/.test(src),
    'should display cat.title');
});

test('render uses feeds CSS class', () => {
  const src = readSource();
  assert.ok(/feeds\s*\+/.test(src) || /['"]feeds['"]/.test(src) || /'feeds '/.test(src),
    'should use feeds CSS class');
});

test('render uses not_hidden class when category is expanded', () => {
  const src = readSource();
  assert.ok(/not_hidden/.test(src),
    'should use not_hidden class for expanded feeds');
});

test('render uses hidden class when category is collapsed', () => {
  const src = readSource();
  assert.ok(/['"]hidden['"]/.test(src),
    'should use hidden class for collapsed feeds');
});

// ============================================================
// Feed rendering tests
// ============================================================

test('render checks for cat.feeds existence', () => {
  const src = readSource();
  assert.ok(/cat\.feeds/.test(src),
    'should check cat.feeds');
});

test('render uses feed-item CSS class', () => {
  const src = readSource();
  assert.ok(/feed-item/.test(src),
    'should use feed-item CSS class');
});

test('render uses feed-checkbox CSS class', () => {
  const src = readSource();
  assert.ok(/feed-checkbox/.test(src),
    'should use feed-checkbox CSS class');
});

test('render uses category-checkbox CSS class', () => {
  const src = readSource();
  assert.ok(/category-checkbox/.test(src),
    'should use category-checkbox CSS class');
});

test('render feed checkbox has data-type="feed"', () => {
  const src = readSource();
  assert.ok(/data-type\s*=\s*['"]feed['"]/.test(src),
    'should set data-type="feed"');
});

test('render feed checkbox has data-id attribute', () => {
  const src = readSource();
  assert.ok(/data-id\s*=\s*\{?\s*feed\.feed_id/.test(src),
    'should set data-id to feed.feed_id');
});

test('render category checkbox has data-type="category"', () => {
  const src = readSource();
  assert.ok(/data-type\s*=\s*['"]category['"]/.test(src),
    'should set data-type="category"');
});

test('render category checkbox has data-id with category_id', () => {
  const src = readSource();
  assert.ok(/data-id\s*=\s*\{?\s*cat\.category_id/.test(src),
    'should set data-id to cat.category_id');
});

test('render feed checkbox onChange bound to window.handleCheckboxChange', () => {
  const src = readSource();
  assert.ok(/onChange\s*=\s*\{?\s*window\.handleCheckboxChange/.test(src),
    'should bind onChange to window.handleCheckboxChange');
});

test('render links to feed.url', () => {
  const src = readSource();
  assert.ok(/feed\.url/.test(src),
    'should link to feed.url');
});

test('render displays feed.title', () => {
  const src = readSource();
  assert.ok(/feed\.title/.test(src),
    'should display feed.title');
});

test('render displays feed.unread_count', () => {
  const src = readSource();
  assert.ok(/feed\.unread_count/.test(src),
    'should display feed.unread_count');
});

// ============================================================
// Special All category tests
// ============================================================

test('render conditionally hides expand button for All category', () => {
  const src = readSource();
  assert.ok(/cat_name\s*!==\s*['"]All['"]/.test(src),
    'should check if category is not "All"');
});

test('render uses inline style span for All category', () => {
  const src = readSource();
  assert.ok(/width\s*:\s*['"]20px['"]/.test(src),
    'should use width: 20px inline style for All');
});

test('render conditionally hides checkbox for All category', () => {
  const src = readSource();
  assert.ok(/['"]All['"]/.test(src) && /''/.test(src),
    'should use empty string instead of checkbox for All');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});

test('source uses window.initial_cats_list', () => {
  const src = readSource();
  assert.ok(/window\.initial_cats_list/.test(src),
    'should reference window.initial_cats_list');
});
