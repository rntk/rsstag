import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HELPER_PATH = path.join(__dirname, '..', 'libs', 'render-helper.js');

function readSource() {
  return fs.readFileSync(HELPER_PATH, 'utf8');
}

// ============================================================
// Export and structure tests
// ============================================================

test('source exports a named function renderToRoot', () => {
  const src = readSource();
  assert.ok(
    /export function renderToRoot/.test(src),
    'should export a named function renderToRoot'
  );
});

test('renderToRoot is not a default export', () => {
  const src = readSource();
  assert.ok(!/export default/.test(src), 'should not have a default export');
});

test('function accepts containerId and element parameters', () => {
  const src = readSource();
  assert.ok(
    /function renderToRoot\s*\(\s*containerId\s*,\s*element\s*\)/.test(src),
    'should have function renderToRoot(containerId, element)'
  );
});

test('source imports createRoot from react-dom/client', () => {
  const src = readSource();
  assert.ok(
    /import\s*\{\s*createRoot\s*\}\s*from\s*['"]react-dom\/client['"]/.test(src),
    'should import createRoot from react-dom/client'
  );
});

// ============================================================
// Function logic tests
// ============================================================

test('function calls document.getElementById', () => {
  const src = readSource();
  assert.ok(
    /document\.getElementById\s*\(\s*containerId\s*\)/.test(src),
    'should call document.getElementById(containerId)'
  );
});

test('function assigns result to container variable', () => {
  const src = readSource();
  assert.ok(
    /const container\s*=\s*document\.getElementById/.test(src),
    'should assign to const container'
  );
});

test('function returns null when container not found', () => {
  const src = readSource();
  assert.ok(
    /if\s*\(\s*!\s*container\s*\)\s*return null/.test(src),
    'should return null if container is falsy'
  );
});

test('function calls createRoot with container', () => {
  const src = readSource();
  assert.ok(
    /const root\s*=\s*createRoot\s*\(\s*container\s*\)/.test(src),
    'should call createRoot(container)'
  );
});

test('function calls root.render with element', () => {
  const src = readSource();
  assert.ok(/root\.render\s*\(\s*element\s*\)/.test(src), 'should call root.render(element)');
});

test('function returns the root', () => {
  const src = readSource();
  assert.ok(/return root/.test(src), 'should return root');
});

// ============================================================
// Code quality tests
// ============================================================

test('function uses const declarations', () => {
  const src = readSource();
  assert.ok(/const container/.test(src), 'should use const for container');
  assert.ok(/const root/.test(src), 'should use const for root');
});

test('function is concise (under 10 lines)', () => {
  const src = readSource();
  const funcBody = src.match(/export function renderToRoot[\s\S]*/);
  if (funcBody) {
    const lineCount = funcBody[0].split('\n').length;
    assert.ok(lineCount <= 10, `function should be concise (found ${lineCount} lines)`);
  }
});

test('source has minimal imports', () => {
  const src = readSource();
  const importCount = (src.match(/^import /gm) || []).length;
  assert.equal(importCount, 1, 'should have exactly 1 import');
});
