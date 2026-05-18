import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'letters-list.js');

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

test('class name is LettersList', () => {
  const src = readSource();
  assert.ok(/export default class LettersList/.test(src),
    'should define class LettersList');
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

test('constructor initializes state from window.initial_letters_list', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?letters\s*:\s*window\.initial_letters_list/.test(src),
    'should set state.letters from window.initial_letters_list');
});

test('constructor does not bind any methods', () => {
  const src = readSource();
  assert.ok(!/\.bind\s*\(/.test(src),
    'should not bind any methods');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render checks this.state and this.state.letters for truthy path', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*this\.state\s*&&\s*this\.state\.letters\s*\)/.test(src),
    'should check if(this.state && this.state.letters)');
});

test('render maps over letters array', () => {
  const src = readSource();
  assert.ok(/this\.state\.letters\.map/.test(src),
    'should map over state.letters');
});

test('render returns div with letters CSS class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]letters['"]/.test(src),
    'should set className="letters"');
});

test('render returns p element as fallback', () => {
  const src = readSource();
  assert.ok(/<p><\/p>/.test(src),
    'should render empty p as fallback');
});

// ============================================================
// Letter rendering tests
// ============================================================

test('render wraps each letter in span with key', () => {
  const src = readSource();
  assert.ok(/key\s*=\s*\{\s*letter\.letter\s*\}/.test(src),
    'should use letter.letter as key');
});

test('render uses letter.local_url for href', () => {
  const src = readSource();
  assert.ok(/href\s*=\s*\{\s*letter\.local_url\s*\}/.test(src),
    'should set href to letter.local_url');
});

test('render sets letter CSS class on anchor', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]letter['"]/.test(src),
    'should set className="letter"');
});

test('render displays letter.letter as link text', () => {
  const src = readSource();
  assert.ok(/\{\s*letter\.letter\s*\}/.test(src),
    'should render letter.letter as link content');
});

// ============================================================
// Splitter logic tests
// ============================================================

test('render initializes splitter to false', () => {
  const src = readSource();
  assert.ok(/let splitter\s*=\s*false/.test(src),
    'should initialize splitter = false');
});

test('render uses switch statement for splitter logic', () => {
  const src = readSource();
  assert.ok(/switch\s*\(\s*letter\.letter\s*\)/.test(src),
    'should use switch(letter.letter)');
});

test('render sets splitter for Cyrillic ё letter', () => {
  const src = readSource();
  assert.ok(/case\s*['"]ё['"]/.test(src),
    'should have case for ё');
});

test('render sets splitter for z letter', () => {
  const src = readSource();
  assert.ok(/case\s*['"]z['"]/.test(src),
    'should have case for z');
});

test('render sets splitter for 9 digit', () => {
  const src = readSource();
  assert.ok(/case\s*['"]9['"]/.test(src),
    'should have case for 9');
});

test('render renders br element as splitter', () => {
  const src = readSource();
  assert.ok(/<br\s*\/>/.test(src),
    'should render <br /> as splitter');
});

test('render uses space as default separator', () => {
  const src = readSource();
  assert.ok(/splitter\s*\?\s*.*<br\s*\/>\s*:\s*['"]\s+['"]/.test(src),
    'should use space as default separator');
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

test('component does not declare lifecycle methods', () => {
  const src = readSource();
  assert.ok(!/componentDidMount/.test(src),
    'should not have componentDidMount');
  assert.ok(!/componentWillUnmount/.test(src),
    'should not have componentWillUnmount');
});
