import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'bigrams-tabs.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Constants and imports tests
// ============================================================

test('source defines TAB_CLOUD constant', () => {
  const src = readSource();
  assert.ok(/TAB_CLOUD\s*=\s*['"]cloud['"]/.test(src),
    'should define TAB_CLOUD = "cloud"');
});

test('source defines TAB_TABLE constant', () => {
  const src = readSource();
  assert.ok(/TAB_TABLE\s*=\s*['"]table['"]/.test(src),
    'should define TAB_TABLE = "table"');
});

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports named BiGramsTabs class extending React.Component', () => {
  const src = readSource();
  assert.ok(/export class BiGramsTabs extends React\.Component/.test(src),
    'should export BiGramsTabs class extending React.Component');
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

test('constructor creates tabs Map', () => {
  const src = readSource();
  assert.ok(/this\.tabs\s*=\s*new Map/.test(src),
    'should create this.tabs as Map');
});

test('constructor sets cloud tab', () => {
  const src = readSource();
  assert.ok(/this\.tabs\.set\s*\(\s*TAB_CLOUD/.test(src),
    'should set cloud tab');
});

test('cloud tab title is "Tags Cloud"', () => {
  const src = readSource();
  assert.ok(/TAB_CLOUD.*['"]Tags Cloud['"]/.test(src),
    'should set cloud tab title to "Tags Cloud"');
});

test('constructor sets table tab', () => {
  const src = readSource();
  assert.ok(/this\.tabs\.set\s*\(\s*TAB_TABLE/.test(src),
    'should set table tab');
});

test('table tab title is "Tags Table"', () => {
  const src = readSource();
  assert.ok(/TAB_TABLE.*['"]Tags Table['"]/.test(src),
    'should set table tab title to "Tags Table"');
});

test('constructor sets current tab to cloud', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?current\s*:\s*TAB_CLOUD/.test(src),
    'should set state.current to TAB_CLOUD');
});

test('constructor binds onTabClick method', () => {
  const src = readSource();
  assert.ok(/this\.onTabClick\s*=\s*this\.onTabClick\.bind\(this\)/.test(src),
    'should bind onTabClick');
});

// ============================================================
// Method declaration tests
// ============================================================

test('source declares onTabClick method', () => {
  const src = readSource();
  assert.ok(/onTabClick\s*\(/.test(src),
    'should declare onTabClick() method');
});

test('onTabClick reads data-tab attribute', () => {
  const src = readSource();
  assert.ok(/getAttribute\s*\(\s*['"]data-tab['"]/.test(src),
    'should read data-tab attribute');
});

test('onTabClick calls changeTab', () => {
  const src = readSource();
  assert.ok(/this\.changeTab/.test(src),
    'should call changeTab');
});

test('source declares changeTab method', () => {
  const src = readSource();
  assert.ok(/changeTab\s*\(/.test(src),
    'should declare changeTab() method');
});

test('changeTab updates current in state', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*\{\s*current\s*:/.test(src),
    'should set state.current');
});

test('source declares updateVisibility method', () => {
  const src = readSource();
  assert.ok(/updateVisibility\s*\(\s*\)/.test(src),
    'should declare updateVisibility() method');
});

test('updateVisibility queries tags_page element', () => {
  const src = readSource();
  assert.ok(/getElementById\s*\(\s*['"]tags_page['"]/.test(src),
    'should getElementById("tags_page")');
});

test('updateVisibility queries bigrams_table_page element', () => {
  const src = readSource();
  assert.ok(/getElementById\s*\(\s*['"]bigrams_table_page['"]/.test(src),
    'should getElementById("bigrams_table_page")');
});

test('updateVisibility shows tags page when cloud is active', () => {
  const src = readSource();
  assert.ok(/tagsPage\.style\.display\s*=\s*['"]block['"]/.test(src),
    'should set tagsPage display to "block"');
});

test('updateVisibility hides table page when cloud is active', () => {
  const src = readSource();
  assert.ok(/bigramsTablePage\.style\.display\s*=\s*['"]none['"]/.test(src),
    'should set bigramsTablePage display to "none"');
});

test('updateVisibility hides tags page when table is active', () => {
  const src = readSource();
  assert.ok(/display\s*=\s*['"]none['"]/.test(src),
    'should set display to "none"');
});

test('updateVisibility shows table page when table is active', () => {
  const src = readSource();
  assert.ok(/bigramsTablePage\.style\.display\s*=\s*['"]block['"]/.test(src),
    'should set bigramsTablePage display to "block"');
});

test('updateVisibility checks both elements exist before modifying', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*tagsPage && bigramsTablePage/.test(src),
    'should check both elements exist');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)/.test(src),
    'should declare componentDidMount() method');
});

test('componentDidMount calls updateVisibility', () => {
  const src = readSource();
  assert.ok(/componentDidMount[\s\S]*?updateVisibility/.test(src),
    'should call updateVisibility in componentDidMount');
});

test('source declares componentDidUpdate lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidUpdate\s*\(\s*\)/.test(src),
    'should declare componentDidUpdate() method');
});

test('componentDidUpdate calls updateVisibility', () => {
  const src = readSource();
  assert.ok(/componentDidUpdate[\s\S]*?updateVisibility/.test(src),
    'should call updateVisibility in componentDidUpdate');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render returns div with bigrams_tabs_container class', () => {
  const src = readSource();
  assert.ok(/bigrams_tabs_container/.test(src),
    'should use bigrams_tabs_container CSS class');
});

test('render includes ul with post_tabs_list class', () => {
  const src = readSource();
  assert.ok(/post_tabs_list/.test(src),
    'should use post_tabs_list CSS class');
});

test('render maps tabs to li elements', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let\s+\[.*name.*title.*\]\s+of\s+this\.tabs/.test(src) ||
    /this\.tabs/.test(src),
    'should iterate over tabs Map');
  assert.ok(/<li/.test(src),
    'should render li elements');
});

test('render uses post_tab CSS class', () => {
  const src = readSource();
  assert.ok(/post_tab/.test(src),
    'should use post_tab CSS class');
});

test('render uses post_tab_active CSS class conditionally', () => {
  const src = readSource();
  assert.ok(/post_tab_active/.test(src),
    'should conditionally apply post_tab_active class');
});

test('render tab has data-tab attribute', () => {
  const src = readSource();
  assert.ok(/data-tab\s*=\s*\{?\s*name/.test(src),
    'should set data-tab attribute from tab name');
});

test('render tab has onClick handler', () => {
  const src = readSource();
  assert.ok(/onClick\s*=\s*\{?\s*this\.onTabClick/.test(src),
    'should bind onClick to onTabClick');
});

test('render displays tab title text', () => {
  const src = readSource();
  assert.ok(/\{?\s*title\s*\}/.test(src),
    'should display tab title');
});

test('render tab key includes tab_ prefix', () => {
  const src = readSource();
  assert.ok(/['"]tab_['"]/.test(src) || /tab_\s*\+/.test(src),
    'should use "tab_" prefix for keys');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});

test('source uses document.getElementById', () => {
  const src = readSource();
  assert.ok(/document\.getElementById/.test(src),
    'should use document.getElementById');
});
