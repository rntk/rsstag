import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'openai.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a named class OpenAITool (not default)', () => {
  const src = readSource();
  assert.ok(/export class OpenAITool/.test(src), 'should export a named class OpenAITool');
  assert.ok(!/export default class OpenAITool/.test(src), 'should not be a default export');
});

test('class extends React.Component', () => {
  const src = readSource();
  assert.ok(/class OpenAITool extends React\.Component/.test(src), 'should extend React.Component');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('constructor initializes state with user and response empty strings', () => {
  const src = readSource();
  assert.ok(
    /this\.state\s*=\s*\{[\s\S]*?user\s*:\s*['']/.test(src),
    'should set state.user to empty string'
  );
  assert.ok(
    /this\.state\s*=\s*\{[\s\S]*?response\s*:\s*['']/.test(src),
    'should set state.response to empty string'
  );
});

test('constructor binds updateResponse method', () => {
  const src = readSource();
  assert.ok(
    /this\.updateResponse\s*=\s*this\.updateResponse\.bind\(this\)/.test(src),
    'should bind updateResponse'
  );
});

test('constructor binds changeRequest method', () => {
  const src = readSource();
  assert.ok(
    /this\.changeRequest\s*=\s*this\.changeRequest\.bind\(this\)/.test(src),
    'should bind changeRequest'
  );
});

test('constructor binds getResponse method', () => {
  const src = readSource();
  assert.ok(
    /this\.getResponse\s*=\s*this\.getResponse\.bind\(this\)/.test(src),
    'should bind getResponse'
  );
});

// ============================================================
// updateResponse method tests
// ============================================================

test('source declares updateResponse method', () => {
  const src = readSource();
  assert.ok(
    /updateResponse\s*\(\s*state\s*\)\s*\{/.test(src),
    'should declare updateResponse(state) method'
  );
});

test('updateResponse calls this.setState', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src), 'should call this.setState(state)');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)\s*\{/.test(src), 'should declare componentDidMount()');
});

test('componentDidMount binds OPENAI_GOT_RESPONSE event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.OPENAI_GOT_RESPONSE\s*,\s*this\.updateResponse/.test(
      src
    ),
    'should bind OPENAI_GOT_RESPONSE to updateResponse'
  );
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(
    /componentWillUnmount\s*\(\s*\)\s*\{/.test(src),
    'should declare componentWillUnmount()'
  );
});

test('componentWillUnmount unbinds OPENAI_GOT_RESPONSE event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.OPENAI_GOT_RESPONSE\s*,\s*this\.updateResponse/.test(
      src
    ),
    'should unbind OPENAI_GOT_RESPONSE from updateResponse'
  );
});

// ============================================================
// getResponse method tests
// ============================================================

test('source declares getResponse method', () => {
  const src = readSource();
  assert.ok(/getResponse\s*\(\s*e\s*\)\s*\{/.test(src), 'should declare getResponse(e) method');
});

test('getResponse creates data payload with user state', () => {
  const src = readSource();
  assert.ok(/user\s*:\s*this\.state\.user/.test(src), 'should pass this.state.user in payload');
});

test('getResponse triggers OPENAI_GET_RESPONSE event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.OPENAI_GET_RESPONSE/.test(src),
    'should trigger OPENAI_GET_RESPONSE'
  );
});

// ============================================================
// changeRequest method tests
// ============================================================

test('source declares changeRequest method', () => {
  const src = readSource();
  assert.ok(/changeRequest\s*\(\s*e\s*\)\s*\{/.test(src), 'should declare changeRequest(e) method');
});

test('changeRequest updates user from event target value', () => {
  const src = readSource();
  assert.ok(/user\s*:\s*e\.target\.value/.test(src), 'should set user from e.target.value');
});

test('changeRequest preserves current response', () => {
  const src = readSource();
  assert.ok(/response\s*:\s*this\.state\.response/.test(src), 'should preserve state.response');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('render returns table with openai_tool_table class', () => {
  const src = readSource();
  assert.ok(
    /<table className="openai_tool_table">/.test(src),
    'should render table with openai_tool_table class'
  );
});

test('render includes tbody element', () => {
  const src = readSource();
  assert.ok(/<tbody>/.test(src), 'should render tbody');
});

test('render has exactly 3 table rows', () => {
  const src = readSource();
  const trMatches = (src.match(/<tr>/g) || []).length;
  assert.equal(trMatches, 3, 'should have 3 tr elements');
});

test('render displays response in pre element', () => {
  const src = readSource();
  assert.ok(/<pre>/.test(src), 'should render a pre element');
  assert.ok(
    /this\.state\s*\?\s*this\.state\.response\s*:\s*['']/.test(src),
    'should render state.response or empty string'
  );
});

test('response cell has tag_prompt_response class', () => {
  const src = readSource();
  assert.ok(
    /className\s*=\s*['"]tag_prompt_response['"]/.test(src),
    'should set tag_prompt_response class'
  );
});

test('render includes textarea for user input', () => {
  const src = readSource();
  assert.ok(/<textarea/.test(src), 'should render a textarea');
  assert.ok(
    /onChange\s*=\s*\{?\s*this\.changeRequest/.test(src),
    'should bind onChange to changeRequest'
  );
  assert.ok(/this\.state\.user/.test(src), 'should reference state.user in textarea');
});

test('textarea cell has tag_prompt_field class', () => {
  const src = readSource();
  assert.ok(
    /className\s*=\s*['"]tag_prompt_field['"]/.test(src),
    'should set tag_prompt_field class'
  );
});

test('render includes "Get response" button', () => {
  const src = readSource();
  assert.ok(
    /<button onClick=\{this\.getResponse\}>Get response<\/button>/.test(src),
    'should render "Get response" button'
  );
});

test('button cell uses colSpan of 2', () => {
  const src = readSource();
  assert.ok(/colSpan\s*=\s*\{\s*['"]2['"]\s*\}/.test(src), 'should set colSpan to "2"');
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
