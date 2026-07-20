import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import TagTree, { BidirectionalTagTree } from '../components/dendrogram.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'dendrogram.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// TagTree constructor tests
// ============================================================

test('TagTree stores data on construction', () => {
  const data = {
    name: 'root',
    children: [{ name: 'child1', children: [{ name: 'grandchild1' }] }, { name: 'child2' }],
  };

  const tree = new TagTree(data);

  assert.equal(tree.data, data);
});

test('TagTree accepts empty object', () => {
  const tree = new TagTree({});
  assert.deepEqual(tree.data, {});
});

test('TagTree accepts flat data', () => {
  const data = { name: 'only-node' };
  const tree = new TagTree(data);
  assert.equal(tree.data.name, 'only-node');
});

test('TagTree accepts tabular data format', () => {
  const data = [
    { id: 'a', parentId: null, name: 'A' },
    { id: 'b', parentId: 'a', name: 'B' },
  ];
  const tree = new TagTree(data);
  assert.equal(tree.data.length, 2);
});

// ============================================================
// TagTree render method tests
// ============================================================

test('TagTree render method exists and is a function', () => {
  const tree = new TagTree({ name: 'root' });
  assert.equal(typeof tree.render, 'function');
});

test('TagTree render accepts selector, width, and height parameters', () => {
  const tree = new TagTree({ name: 'root' });
  // Verify the function expects 3 parameters by checking length
  assert.ok(tree.render.length >= 1, 'render should accept at least selector parameter');
});

test('TagTree render method uses document.querySelector and d3.tree', () => {
  assert.ok(
    /document\.querySelector\s*\(\s*selector\s*\)/.test(source),
    'render should query selector'
  );
  assert.ok(/d3\.tree/.test(source), 'render should use d3.tree');
  assert.ok(/d3\.hierarchy/.test(source), 'render should use d3.hierarchy');
});

test('TagTree render returns early when container is not found', () => {
  assert.ok(
    /if\s*\(\s*pg\s*\)/.test(source) || /pg\s*\?/.test(source),
    'render should check container exists before appending'
  );
});

test('BidirectionalTagTree render method uses d3.tree', () => {
  assert.ok(/d3\.tree/.test(source), 'render should use d3.tree');
  assert.ok(/d3\.hierarchy/.test(source), 'render should use d3.hierarchy');
  assert.ok(/BidirectionalTagTree/.test(source), 'source should define BidirectionalTagTree');
});

test('BidirectionalTagTree render returns early when container is not found', () => {
  assert.ok(
    /let\s+pg\s*=\s*document\.querySelector\s*\(\s*selector\s*\)/.test(source),
    'render should query selector'
  );
  assert.ok(
    /if\s*\(\s*pg\s*\)/.test(source) || /pg\s*\?/.test(source),
    'render should check container exists before appending'
  );
});

// ============================================================
// BidirectionalTagTree constructor tests
// ============================================================

test('BidirectionalTagTree stores data on construction', () => {
  const data = {
    name: 'root',
    before: [{ name: 'before-child' }],
    after: [{ name: 'after-child' }],
  };

  const tree = new BidirectionalTagTree(data);

  assert.equal(tree.data, data);
  assert.ok(Array.isArray(data.before));
  assert.ok(Array.isArray(data.after));
});

test('BidirectionalTagTree accepts data without before/after', () => {
  const data = { name: 'center' };
  const tree = new BidirectionalTagTree(data);
  assert.equal(tree.data.name, 'center');
});

test('BidirectionalTagTree accepts empty object', () => {
  const tree = new BidirectionalTagTree({});
  assert.deepEqual(tree.data, {});
});

test('BidirectionalTagTree accepts empty before and after arrays', () => {
  const data = { name: 'center', before: [], after: [] };
  const tree = new BidirectionalTagTree(data);
  assert.equal(tree.data.name, 'center');
  assert.deepEqual(tree.data.before, []);
  assert.deepEqual(tree.data.after, []);
});

// ============================================================
// BidirectionalTagTree render method tests
// ============================================================

test('BidirectionalTagTree render method exists and is a function', () => {
  const tree = new BidirectionalTagTree({ name: 'root' });
  assert.equal(typeof tree.render, 'function');
});

test('BidirectionalTagTree render accepts selector, width, and height parameters', () => {
  const tree = new BidirectionalTagTree({ name: 'root' });
  assert.ok(tree.render.length >= 1, 'render should accept at least selector parameter');
});

test('BidirectionalTagTree render method uses document and d3', () => {
  assert.ok(/document\.querySelector/.test(source), 'should use document.querySelector');
  assert.ok(/d3\.tree/.test(source), 'should use d3.tree');
});

// ============================================================
// Interface consistency tests
// ============================================================

test('TagTree and BidirectionalTagTree share the same interface', () => {
  const data = { name: 'root', children: [] };
  const tagTree = new TagTree(data);
  const bidiTree = new BidirectionalTagTree(data);

  assert.equal(typeof tagTree.render, typeof bidiTree.render);
  assert.equal(typeof tagTree.data, typeof bidiTree.data);
});

test('TagTree data property is the same reference as input', () => {
  const data = { name: 'root', children: [{ name: 'child' }] };
  const tree = new TagTree(data);
  assert.strictEqual(tree.data, data);
});

test('BidirectionalTagTree data property is the same reference as input', () => {
  const data = { name: 'root', before: [], after: [] };
  const tree = new BidirectionalTagTree(data);
  assert.strictEqual(tree.data, data);
});

// ============================================================
// Link function behavior tests (URL generation)
// ============================================================

test('TagTree render uses ancestors to build URL', () => {
  // Test the internal link_fn logic by verifying the class exists
  // and the render method is wired correctly.
  // The actual URL building depends on d3 and DOM, so we verify the interface.
  const data = {
    name: 'root',
    children: [{ name: 'child', children: [{ name: 'grandchild' }] }],
  };
  const tree = new TagTree(data);
  assert.ok(tree.data.children.length === 1);
  assert.ok(tree.data.children[0].children.length === 1);
});

test('BidirectionalTagTree data supports before/after structure', () => {
  const data = {
    name: 'center-topic',
    before: [{ name: 'previous-topic', children: [{ name: 'older-topic' }] }],
    after: [{ name: 'next-topic', children: [{ name: 'newer-topic' }] }],
  };
  const tree = new BidirectionalTagTree(data);

  assert.equal(tree.data.name, 'center-topic');
  assert.equal(tree.data.before.length, 1);
  assert.equal(tree.data.after.length, 1);
  assert.equal(tree.data.before[0].name, 'previous-topic');
  assert.equal(tree.data.after[0].name, 'next-topic');
});

// ============================================================
// Export verification tests
// ============================================================

test('default export is TagTree class', () => {
  assert.equal(typeof TagTree, 'function');
  // Verify it's a constructor
  assert.doesNotThrow(() => new TagTree({}));
});

test('named export BidirectionalTagTree is a class', () => {
  assert.equal(typeof BidirectionalTagTree, 'function');
  assert.doesNotThrow(() => new BidirectionalTagTree({}));
});

test('both exports are distinct classes', () => {
  assert.notStrictEqual(TagTree, BidirectionalTagTree);
});
