import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'tag-net-tools.js');

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

test('class name is TagNetTools', () => {
  const src = readSource();
  assert.ok(/export default class TagNetTools/.test(src),
    'should define class TagNetTools');
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

test('constructor binds changeTagSettings method', () => {
  const src = readSource();
  assert.ok(/this\.changeTagSettings\s*=\s*this\.changeTagSettings\.bind\(this\)/.test(src),
    'should bind changeTagSettings');
});

test('constructor binds renderTools method', () => {
  const src = readSource();
  assert.ok(/this\.renderTools\s*=\s*this\.renderTools\.bind\(this\)/.test(src),
    'should bind renderTools');
});

// ============================================================
// changeTagSettings method tests
// ============================================================

test('source declares changeTagSettings method', () => {
  const src = readSource();
  assert.ok(/changeTagSettings\s*\(\s*e\s*\)/.test(src),
    'should declare changeTagSettings(e) method');
});

test('changeTagSettings checks selected_tag exists in tags Map', () => {
  const src = readSource();
  assert.ok(/this\.state\.tags\.has\s*\(\s*this\.state\.selected_tag\s*\)/.test(src),
    'should check tags.has(selected_tag)');
});

test('changeTagSettings retrieves tag from tags Map using get', () => {
  const src = readSource();
  assert.ok(/this\.state\.tags\.get\s*\(\s*this\.state\.selected_tag\s*\)/.test(src),
    'should use tags.get(selected_tag)');
});

test('changeTagSettings sets tag.hidden from checkbox checked state', () => {
  const src = readSource();
  assert.ok(/tag\.hidden\s*=\s*e\.target\.checked/.test(src),
    'should set tag.hidden = e.target.checked');
});

test('changeTagSettings triggers NET_TAG_CHANGE event', () => {
  const src = readSource();
  assert.ok(/NET_TAG_CHANGE/.test(src),
    'should reference NET_TAG_CHANGE');
  assert.ok(/this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.NET_TAG_CHANGE/.test(src),
    'should trigger NET_TAG_CHANGE event');
});

test('changeTagSettings passes tag as payload to trigger', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.trigger\s*\([^,]+,\s*tag\s*\)/.test(src),
    'should pass tag as event payload');
});

// ============================================================
// renderTools method tests
// ============================================================

test('source declares renderTools method', () => {
  const src = readSource();
  assert.ok(/renderTools\s*\(\s*state\s*\)/.test(src),
    'should declare renderTools(state) method');
});

test('renderTools calls setState with state parameter', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src),
    'should call setState(state)');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)/.test(src),
    'should declare componentDidMount() method');
});

test('componentDidMount binds TAGS_NET_UPDATED event', () => {
  const src = readSource();
  assert.ok(/TAGS_NET_UPDATED/.test(src),
    'should reference TAGS_NET_UPDATED');
  assert.ok(/this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.TAGS_NET_UPDATED/.test(src),
    'should bind TAGS_NET_UPDATED event');
});

test('componentDidMount binds renderTools as handler', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.bind\s*\([^,]+,\s*this\.renderTools\s*\)/.test(src),
    'should bind renderTools as the event handler');
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentWillUnmount\s*\(\s*\)/.test(src),
    'should declare componentWillUnmount() method');
});

test('componentWillUnmount unbinds TAGS_NET_UPDATED event', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.TAGS_NET_UPDATED/.test(src),
    'should unbind TAGS_NET_UPDATED event');
});

test('componentWillUnmount unbinds renderTools as handler', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.unbind\s*\([^,]+,\s*this\.renderTools\s*\)/.test(src),
    'should unbind renderTools as the event handler');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render initializes tools variable to empty span', () => {
  const src = readSource();
  assert.ok(/let tools\s*=\s*<span><\/span>/.test(src),
    'should initialize tools as empty span');
});

test('render checks for this.state existence', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*this\.state\s*\)/.test(src),
    'should check this.state');
});

test('render iterates over this.state.tags', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let\s+tag_data\s+of\s+this\.state\.tags/.test(src),
    'should iterate over state.tags');
});

// ============================================================
// Statistics display tests
// ============================================================

test('render counts showed_tags (non-hidden tags)', () => {
  const src = readSource();
  assert.ok(/showed_tags\s*=\s*0/.test(src),
    'should initialize showed_tags counter');
  assert.ok(/!tag_data\[1\]\.hidden/.test(src),
    'should check !tag.hidden');
  assert.ok(/showed_tags\+\+/.test(src),
    'should increment showed_tags');
});

test('render shows "showed / total" statistic', () => {
  const src = readSource();
  assert.ok(/this\.state\.tags\.size/.test(src),
    'should reference tags.size for total');
});

test('render uses span for statistic display', () => {
  const src = readSource();
  assert.ok(/stat\s*=\s*\(/.test(src),
    'should define stat JSX');
});

// ============================================================
// Tag-specific tools tests
// ============================================================

test('render checks if selected_tag exists in tags', () => {
  const src = readSource();
  assert.ok(/this\.state\.tags\.has\s*\(\s*this\.state\.selected_tag\s*\)/.test(src),
    'should check selected_tag in tags');
});

test('render displays tag name with "Tag:" label', () => {
  const src = readSource();
  assert.ok(/Tag:\s*\{?\s*tag\.tag/.test(src),
    'should display tag.tag with "Tag:" label');
});

test('render creates a checkbox input', () => {
  const src = readSource();
  assert.ok(/type\s*=\s*['"]checkbox['"]/.test(src),
    'should create checkbox input');
});

test('checkbox has id="hidden"', () => {
  const src = readSource();
  assert.ok(/id\s*=\s*['"]hidden['"]/.test(src),
    'should set id="hidden"');
});

test('checkbox checked bound to tag.hidden', () => {
  const src = readSource();
  assert.ok(/checked\s*=\s*\{?\s*tag\.hidden/.test(src),
    'should bind checked to tag.hidden');
});

test('checkbox onChange bound to changeTagSettings', () => {
  const src = readSource();
  assert.ok(/onChange\s*=\s*\{?\s*this\.changeTagSettings/.test(src),
    'should bind onChange to changeTagSettings');
});

test('checkbox has htmlFor="hidden" label', () => {
  const src = readSource();
  assert.ok(/htmlFor\s*=\s*['"]hidden['"]/.test(src),
    'should set htmlFor="hidden"');
});

test('render includes "Hide tag" text', () => {
  const src = readSource();
  assert.ok(/Hide tag/.test(src),
    'should include "Hide tag" text');
});

test('render wraps tools in a div when selected tag exists', () => {
  const src = readSource();
  assert.ok(/tools\s*=\s*\(\s*<div>/.test(src),
    'should wrap tools in div');
});

test('render shows stat when no selected tag in tags', () => {
  const src = readSource();
  assert.ok(/} else {\s*tools\s*=\s*stat;/.test(src) || /else\s*\{[\s\n]*tools\s*=\s*stat/.test(src),
    'should set tools to stat as fallback');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});

test('source uses strict mode', () => {
  const src = readSource();
  assert.ok(/'use strict'/.test(src),
    'should use strict mode');
});
