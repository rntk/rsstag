import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'search-input.js');

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

test('class name is SearchInput', () => {
  const src = readSource();
  assert.ok(/export default class SearchInput/.test(src),
    'should define class SearchInput');
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

test('constructor initializes state with request and suggestions', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?request\s*:/.test(src),
    'should set state.request');
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?suggestions\s*:/.test(src),
    'should set state.suggestions');
});

test('constructor initializes timeout variable', () => {
  const src = readSource();
  assert.ok(/this\.t_out\s*=\s*0/.test(src),
    'should initialize t_out = 0');
});

test('constructor sets debounce timeout to 800ms', () => {
  const src = readSource();
  assert.ok(/this\.debounce_t\s*=\s*800/.test(src),
    'should set debounce_t = 800');
});

test('constructor defines URLs object with tags_search', () => {
  const src = readSource();
  assert.ok(/this\.urls\s*=\s*\{[\s\S]*?tags_search/.test(src),
    'should define urls with tags_search');
});

test('tags_search URL is /tags-search', () => {
  const src = readSource();
  assert.ok(/tags_search\s*:.*['"]\/tags-search['"]/.test(src),
    'should set tags_search to /tags-search');
});

test('constructor binds changeSearchRequest method', () => {
  const src = readSource();
  assert.ok(/this\.changeSearchRequest\s*=\s*this\.changeSearchRequest\.bind\(this\)/.test(src),
    'should bind changeSearchRequest');
});

// ============================================================
// Method declaration tests
// ============================================================

test('source declares changeSearchRequest method', () => {
  const src = readSource();
  assert.ok(/changeSearchRequest\s*\(/.test(src),
    'should declare changeSearchRequest() method');
});

test('changeSearchRequest reads e.target.value', () => {
  const src = readSource();
  assert.ok(/e\.target\.value/.test(src),
    'should read e.target.value');
});

test('changeSearchRequest clears suggestions when input is empty', () => {
  const src = readSource();
  assert.ok(/suggestions\s*=\s*\[\s*\]/.test(src),
    'should set suggestions to empty array');
});

test('changeSearchRequest uses clearTimeout', () => {
  const src = readSource();
  assert.ok(/clearTimeout/.test(src),
    'should call clearTimeout');
});

test('changeSearchRequest uses setTimeout for debounce', () => {
  const src = readSource();
  assert.ok(/setTimeout/.test(src),
    'should call setTimeout');
});

test('changeSearchRequest uses debounce_t for delay', () => {
  const src = readSource();
  assert.ok(/this\.debounce_t/.test(src),
    'should use this.debounce_t as timeout delay');
});

test('changeSearchRequest calls fetchSuggestions', () => {
  const src = readSource();
  assert.ok(/this\.fetchSuggestions/.test(src),
    'should call fetchSuggestions');
});

test('source declares fetchSuggestions method', () => {
  const src = readSource();
  assert.ok(/fetchSuggestions\s*\(/.test(src),
    'should declare fetchSuggestions() method');
});

test('fetchSuggestions checks request is non-empty', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*request\s*\)/.test(src) || /if\s*\(\s*!?\s*request/.test(src),
    'should check request is truthy');
});

test('fetchSuggestions creates FormData', () => {
  const src = readSource();
  assert.ok(/new FormData/.test(src),
    'should create FormData');
});

test('fetchSuggestions appends req to FormData', () => {
  const src = readSource();
  assert.ok(/\.append\s*\(\s*['"]req['"]/.test(src),
    'should append req to FormData');
});

test('fetchSuggestions uses POST method', () => {
  const src = readSource();
  assert.ok(/method\s*:\s*['"]POST['"]/.test(src),
    'should use POST method');
});

test('fetchSuggestions uses credentials include', () => {
  const src = readSource();
  assert.ok(/credentials\s*:\s*['"]include['"]/.test(src),
    'should include credentials');
});

test('fetchSuggestions sends body as FormData', () => {
  const src = readSource();
  assert.ok(/body\s*:\s*form/.test(src),
    'should send FormData as body');
});

test('fetchSuggestions uses this.urls.tags_search', () => {
  const src = readSource();
  assert.ok(/this\.urls\.tags_search/.test(src),
    'should use this.urls.tags_search as endpoint');
});

test('fetchSuggestions updates suggestions in state', () => {
  const src = readSource();
  assert.ok(/suggestions\s*:\s*data\.data/.test(src),
    'should set suggestions from data.data');
});

test('fetchSuggestions handles error response', () => {
  const src = readSource();
  assert.ok(/data\.error/.test(src),
    'should check data.error');
});

test('fetchSuggestions uses rsstag_utils.fetchJSON', () => {
  const src = readSource();
  assert.ok(/rsstag_utils\s*\.\s*fetchJSON/.test(src),
    'should use rsstag_utils.fetchJSON');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render includes search_tools CSS class', () => {
  const src = readSource();
  assert.ok(/search_tools/.test(src),
    'should use search_tools CSS class');
});

test('render includes search_field CSS class', () => {
  const src = readSource();
  assert.ok(/search_field/.test(src),
    'should use search_field CSS class');
});

test('render input has type="text"', () => {
  const src = readSource();
  assert.ok(/type\s*=\s*['"]text['"]/.test(src),
    'should set input type to text');
});

test('render input has Search placeholder', () => {
  const src = readSource();
  assert.ok(/placeholder\s*=\s*['"]Search['"]/.test(src),
    'should have Search placeholder');
});

test('render input value bound to state.request', () => {
  const src = readSource();
  assert.ok(/value\s*=\s*\{?\s*this\.state\.request/.test(src),
    'should bind input value to state.request');
});

test('render input onChange bound to changeSearchRequest', () => {
  const src = readSource();
  assert.ok(/onChange\s*=\s*\{?\s*this\.changeSearchRequest/.test(src),
    'should bind onChange to changeSearchRequest');
});

test('render includes search_result CSS class', () => {
  const src = readSource();
  assert.ok(/search_result/.test(src),
    'should use search_result CSS class');
});

test('render maps suggestions to paragraphs', () => {
  const src = readSource();
  assert.ok(/this\.state\.suggestions\.map/.test(src),
    'should map suggestions to elements');
});

test('render includes search_result_item CSS class', () => {
  const src = readSource();
  assert.ok(/search_result_item/.test(src),
    'should use search_result_item CSS class for each suggestion');
});

test('render suggestion links to sugg.url', () => {
  const src = readSource();
  assert.ok(/sugg\.url/.test(src),
    'should link to sugg.url');
});

test('render suggestion displays tag, unread, and all counts', () => {
  const src = readSource();
  assert.ok(/sugg\.tag/.test(src),
    'should display sugg.tag');
  assert.ok(/sugg\.unread/.test(src),
    'should display sugg.unread');
  assert.ok(/sugg\.all/.test(src),
    'should display sugg.all');
});

test('render suggestion includes info_url link', () => {
  const src = readSource();
  assert.ok(/sugg\.info_url/.test(src),
    'should include link to sugg.info_url');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});

test('source imports rsstag_utils', () => {
  const src = readSource();
  assert.ok(/import.*rsstag_utils/.test(src),
    'should import rsstag_utils');
});
