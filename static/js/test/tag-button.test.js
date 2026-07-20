import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'tag-button.js');

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

test('class name is TagTool', () => {
  const src = readSource();
  assert.ok(/export default class TagTool/.test(src), 'should define class TagTool');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('constructor initializes state with list_hidden true', () => {
  const src = readSource();
  assert.ok(
    /this\.state\s*=\s*\{[\s\S]*?list_hidden\s*:\s*true/.test(src),
    'should set state.list_hidden to true'
  );
});

test('constructor binds loadData method', () => {
  const src = readSource();
  assert.ok(/this\.loadData\s*=\s*this\.loadData\.bind\(this\)/.test(src), 'should bind loadData');
});

// ============================================================
// loadData method tests
// ============================================================

test('source declares loadData method', () => {
  const src = readSource();
  assert.ok(/loadData\s*\(\s*\)\s*\{/.test(src), 'should declare loadData() method');
});

test('loadData toggles list_hidden state', () => {
  const src = readSource();
  assert.ok(
    /this\.setState\s*\(\s*\{\s*list_hidden\s*:\s*!\s*this\.state\.list_hidden\s*\}\s*\)/.test(src),
    'should toggle list_hidden in setState'
  );
});

test('loadData triggers CHANGE_TAGS_LOAD_BUTTON_STATE event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.CHANGE_TAGS_LOAD_BUTTON_STATE/.test(src),
    'should trigger CHANGE_TAGS_LOAD_BUTTON_STATE'
  );
});

test('loadData passes tag from props', () => {
  const src = readSource();
  assert.ok(/tag\s*:\s*this\.props\.tag\.tag/.test(src), 'should pass this.props.tag.tag');
});

test('loadData passes hide_list as toggled state', () => {
  const src = readSource();
  assert.ok(
    /hide_list\s*:\s*!\s*this\.state\.list_hidden/.test(src),
    'should pass hide_list as negation of current list_hidden'
  );
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('render returns a button element', () => {
  const src = readSource();
  assert.ok(/<button/.test(src), 'should render a button element');
});

test('render binds onClick to loadData', () => {
  const src = readSource();
  assert.ok(/onClick\s*=\s*\{?\s*this\.loadData/.test(src), 'should bind onClick to loadData');
});

test('render calculates prefix based on list_hidden', () => {
  const src = readSource();
  assert.ok(
    /const prefix\s*=\s*this\.state\.list_hidden\s*\?\s*['"]Load\s*['"]/.test(src),
    'should set prefix to "Load " when list_hidden is true'
  );
  assert.ok(
    /:\s*['"]Hide\s*['"]/.test(src),
    'should set prefix to "Hide " when list_hidden is false'
  );
});

test('render concatenates prefix with props.title', () => {
  const src = readSource();
  assert.ok(
    /\{prefix\s*\+\s*this\.props\.title\}/.test(src),
    'should concatenate prefix with this.props.title'
  );
});

test('render button text changes based on list_hidden', () => {
  const src = readSource();
  assert.ok(/prefix/.test(src), 'should use prefix variable for button text');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('component does not declare componentDidMount', () => {
  const src = readSource();
  assert.ok(!/componentDidMount/.test(src), 'should not have componentDidMount');
});

test('component does not declare componentWillUnmount', () => {
  const src = readSource();
  assert.ok(!/componentWillUnmount/.test(src), 'should not have componentWillUnmount');
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
