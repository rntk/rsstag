import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'tag-item.js');

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

test('class name is TagItem', () => {
  const src = readSource();
  assert.ok(/export default class TagItem/.test(src),
    'should define class TagItem');
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

test('constructor initializes state with tag from props', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{\s*tag\s*:\s*props\.tag/.test(src),
    'should set state.tag from props.tag');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render returns li element', () => {
  const src = readSource();
  assert.ok(/<li\s+className/.test(src),
    'should return <li> element');
});

test('render uses cloud_item CSS class', () => {
  const src = readSource();
  assert.ok(/['"]cloud_item['"]/.test(src) || /cloud_item/.test(src),
    'should use cloud_item CSS class');
});

test('render appends sentiment to className', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*\{?\s*['"]cloud_item\s*['"].*\+.*sentiment/.test(src),
    'should concatenate sentiment to className');
});

test('render extracts sentiment from tag.sentiment array', () => {
  const src = readSource();
  assert.ok(/this\.state\.tag\.sentiment/.test(src),
    'should read tag.sentiment');
  assert.ok(/sentiment\[0\]/.test(src),
    'should use sentiment[0]');
});

test('render uses replace to normalize sentiment', () => {
  const src = readSource();
  assert.ok(/replace\s*\(\s*['"]\/['"]/.test(src),
    'should replace / with _ in sentiment');
});

test('render includes cloud_item_header CSS class', () => {
  const src = readSource();
  assert.ok(/cloud_item_header/.test(src),
    'should use cloud_item_header CSS class');
});

test('render includes anchor with tag name', () => {
  const src = readSource();
  assert.ok(/<a name\s*=\s*\{?\s*this\.state\.tag\.tag/.test(src),
    'should include anchor with tag name');
});

test('render includes cloud_item_title CSS class', () => {
  const src = readSource();
  assert.ok(/cloud_item_title/.test(src),
    'should use cloud_item_title CSS class');
});

test('render links to state.tag.url', () => {
  const src = readSource();
  assert.ok(/href\s*=\s*\{?\s*this\.state\.tag\.url/.test(src),
    'should link to state.tag.url');
});

test('render displays tag text', () => {
  const src = readSource();
  assert.ok(/\{?\s*this\.state\.tag\.tag/.test(src),
    'should display tag text');
});

test('render includes cloud_item_count CSS class', () => {
  const src = readSource();
  assert.ok(/cloud_item_count/.test(src),
    'should use cloud_item_count CSS class');
});

test('render displays tag count', () => {
  const src = readSource();
  assert.ok(/this\.state\.tag\.count/.test(src),
    'should display tag.count');
});

test('render includes cloud_item_info CSS class', () => {
  const src = readSource();
  assert.ok(/cloud_item_info/.test(src),
    'should use cloud_item_info CSS class');
});

test('render includes cloud_item_tools CSS class', () => {
  const src = readSource();
  assert.ok(/cloud_item_tools/.test(src),
    'should use cloud_item_tools CSS class');
});

// ============================================================
// Sub-tags (bigram) tests
// ============================================================

test('render checks is_bigram prop', () => {
  const src = readSource();
  assert.ok(/this\.props\.is_bigram/.test(src),
    'should check is_bigram prop');
});

test('render checks is_entity prop', () => {
  const src = readSource();
  assert.ok(/this\.props\.is_entity/.test(src),
    'should check is_entity prop');
});

test('render searches for space in tag for is_entity', () => {
  const src = readSource();
  assert.ok(/\.search\s*\(\s*\/\\s\/\s*\)/.test(src) || /\.search.*\\s/.test(src),
    'should search for whitespace in tag for is_entity');
});

test('render sets hide_tag_info_link variable', () => {
  const src = readSource();
  assert.ok(/hide_tag_info_link/.test(src),
    'should define hide_tag_info_link variable');
});

test('render splits bigram tag into sub-tags', () => {
  const src = readSource();
  assert.ok(/\.split\s*\(\s*['"] ['"]/.test(src),
    'should split tag by space for sub-tags');
});

test('render creates sub-tag links with cloud_sub_item_title class', () => {
  const src = readSource();
  assert.ok(/cloud_sub_item_title/.test(src),
    'should use cloud_sub_item_title for sub-tag links');
});

test('render encodes sub-tag in URL', () => {
  const src = readSource();
  assert.ok(/encodeURIComponent/.test(src),
    'should use encodeURIComponent for URLs');
});

// ============================================================
// Action links tests
// ============================================================

test('render includes sentences link', () => {
  const src = readSource();
  assert.ok(/sentences/.test(src),
    'should include sentences link text');
  assert.ok(/tag_sentences_link/.test(src),
    'should use tag_sentences_link CSS class');
});

test('sentences link uses /sentences/with/tags/ path', () => {
  const src = readSource();
  assert.ok(/\/sentences\/with\/tags\//.test(src),
    'should use /sentences/with/tags/ path');
});

test('render includes ctx link', () => {
  const src = readSource();
  assert.ok(/ctx/.test(src),
    'should include ctx link text');
  assert.ok(/context_tags_link/.test(src),
    'should use context_tags_link CSS class');
});

test('ctx link uses /context-tags/ path', () => {
  const src = readSource();
  assert.ok(/\/context-tags\//.test(src),
    'should use /context-tags/ path');
});

test('render includes get_tag_siblings link', () => {
  const src = readSource();
  assert.ok(/get_tag_siblings/.test(src),
    'should use get_tag_siblings CSS class');
});

test('render includes get_tag_sunburst link', () => {
  const src = readSource();
  assert.ok(/get_tag_sunburst/.test(src),
    'should use get_tag_sunburst CSS class');
  assert.ok(/\/sunburst\//.test(src),
    'should use /sunburst/ path');
});

test('render includes get_tag_chains link', () => {
  const src = readSource();
  assert.ok(/get_tag_chains/.test(src),
    'should use get_tag_chains CSS class');
  assert.ok(/\/chain\//.test(src),
    'should use /chain/ path');
});

test('render includes get_tag_context_tree link', () => {
  const src = readSource();
  assert.ok(/get_tag_context_tree/.test(src),
    'should use get_tag_context_tree CSS class');
  assert.ok(/\/tag-context-tree\//.test(src),
    'should use /tag-context-tree/ path');
});

test('render includes sunburst link text', () => {
  const src = readSource();
  assert.ok(/sunburst/.test(src),
    'should include sunburst link text');
});

test('render includes chain link text', () => {
  const src = readSource();
  assert.ok(/chain/.test(src),
    'should include chain link text');
});

test('render includes tree link text', () => {
  const src = readSource();
  assert.ok(/tree/.test(src),
    'should include tree link text');
});

test('action links conditionally rendered based on hide_tag_info_link', () => {
  const src = readSource();
  assert.ok(/hide_tag_info_link\s*\?\s*null/.test(src),
    'should conditionally hide action links');
});

// ============================================================
// Words display tests
// ============================================================

test('render checks for tag.words array', () => {
  const src = readSource();
  assert.ok(/this\.state\.tag\.words/.test(src),
    'should check tag.words');
  assert.ok(/\.length/.test(src),
    'should check words length');
});

test('render joins words with comma', () => {
  const src = readSource();
  assert.ok(/\.join\s*\(\s*['"], ['"]/.test(src),
    'should join words with comma separator');
});

// ============================================================
// Info section conditional tests
// ============================================================

test('render conditionally shows info div', () => {
  const src = readSource();
  assert.ok(/sub_tags\.length\s*>\s*0/.test(src),
    'should check sub_tags length for info display');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});
