import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

import {
  hashString,
  hierarchyHighlightColor,
  hierarchyAccentColor,
  countRenderedRows,
} from '../topics-hierarchy.js';

test('hashString returns a non-negative integer', () => {
  const result = hashString('test');
  assert.equal(typeof result, 'number');
  assert.ok(Number.isInteger(result));
  assert.ok(result >= 0);
});

test('hashString is deterministic', () => {
  assert.equal(hashString('hello'), hashString('hello'));
});

test('hashString returns different values for different inputs', () => {
  assert.notEqual(hashString('abc'), hashString('xyz'));
});

test('hashString handles empty string', () => {
  const result = hashString('');
  assert.equal(typeof result, 'number');
  assert.ok(result >= 0);
});

test('hashString handles numeric input', () => {
  const result = hashString('123');
  assert.equal(typeof result, 'number');
  assert.ok(result >= 0);
});

test('hierarchyHighlightColor returns a valid HSL string', () => {
  const color = hierarchyHighlightColor('root', 0);
  assert.ok(color.startsWith('hsl('));
  assert.ok(color.endsWith('%)'));
  assert.ok(color.includes('hsl'));
});

test('hierarchyHighlightColor gets lighter with depth', () => {
  const shallow = hierarchyHighlightColor('root', 0);
  const deep = hierarchyHighlightColor('root', 5);
  const shallowLightness = parseInt(shallow.match(/(\d+)%\)$/)[1]);
  const deepLightness = parseInt(deep.match(/(\d+)%\)$/)[1]);
  assert.ok(deepLightness >= shallowLightness);
});

test('hierarchyHighlightColor is deterministic for same root and depth', () => {
  assert.equal(hierarchyHighlightColor('root', 2), hierarchyHighlightColor('root', 2));
});

test('hierarchyAccentColor returns a valid HSL string', () => {
  const color = hierarchyAccentColor('root', 0);
  assert.ok(color.startsWith('hsl('));
  assert.ok(color.endsWith('%)'));
});

test('hierarchyAccentColor is deterministic', () => {
  assert.equal(hierarchyAccentColor('tech', 1), hierarchyAccentColor('tech', 1));
});

test('countRenderedRows returns 1 for a leaf node', () => {
  const leaf = { name: 'leaf', value: 5 };
  assert.equal(countRenderedRows(leaf), 1);
});

test('countRenderedRows returns children count for nodes with children', () => {
  const parent = {
    name: 'parent',
    children: [
      { name: 'child1', value: 1 },
      { name: 'child2', value: 2 },
    ],
  };
  assert.equal(countRenderedRows(parent), 2);
});

test('countRenderedRows sums recursively for nested children', () => {
  const grandparent = {
    name: 'gp',
    children: [
      {
        name: 'parent',
        children: [
          { name: 'child1', value: 1 },
          { name: 'child2', value: 2 },
        ],
      },
      { name: 'child3', value: 3 },
    ],
  };
  assert.equal(countRenderedRows(grandparent), 3);
});

test('countRenderedRows handles node with no children array', () => {
  const node = { name: 'test' };
  assert.equal(countRenderedRows(node), 1);
});

test('countRenderedRows handles node with empty children array', () => {
  const node = { name: 'test', children: [] };
  assert.equal(countRenderedRows(node), 1);
});

// ---------------------------------------------------------------------------
// DOM-based tests (buildNode, renderTopicsHierarchy)
// ---------------------------------------------------------------------------

function extractFunction(source, name) {
  const patterns = [`export function ${name}`, `function ${name}`];
  let start = -1;
  for (const p of patterns) {
    start = source.indexOf(p);
    if (start !== -1) break;
  }
  if (start === -1) {
    throw new Error(`Unable to find function ${name}`);
  }

  const bodyStart = source.indexOf('{', start);
  let depth = 0;
  let end = bodyStart;

  for (; end < source.length; end += 1) {
    const char = source[end];
    if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        break;
      }
    }
  }

  return source.slice(start, end + 1).replace(/^export function /, 'function ');
}

function createMockDocument() {
  class MockStyle {
    constructor() {
      this.props = {};
    }
    setProperty(name, value) {
      this.props[name] = value;
    }
  }

  class MockElement {
    constructor(tagName) {
      this.tagName = tagName;
      this.className = '';
      this.textContent = '';
      this.title = '';
      this.href = '';
      this.innerHTML = '';
      this.children = [];
      this.style = new MockStyle();
      this.childNodes = [];
    }
    appendChild(child) {
      this.children.push(child);
      this.childNodes.push(child);
      return child;
    }
    setAttribute(name, value) {
      this[name] = value;
    }
    getAttribute(name) {
      return this[name];
    }
    querySelector(sel) {
      return null;
    }
    querySelectorAll(sel) {
      return [];
    }
    addEventListener() {}
    removeEventListener() {}
    focus() {}
    closest() {
      return null;
    }
    getBoundingClientRect() {
      return { top: 0, right: 0, bottom: 0, left: 0, width: 0, height: 0 };
    }
  }

  return {
    createElement(tagName) {
      return new MockElement(tagName);
    },
  };
}

function loadTopicsHierarchyDOM(overrides = {}) {
  const source = fs.readFileSync(new URL('../topics-hierarchy.js', import.meta.url), 'utf8');
  const funcs = [
    'hashString',
    'hierarchyHighlightColor',
    'hierarchyAccentColor',
    'countRenderedRows',
    'buildNode',
    'renderTopicsHierarchy',
  ];
  const scriptSource = [
    ...funcs.map((name) => extractFunction(source, name)),
    'module.exports = { buildNode, renderTopicsHierarchy };',
  ].join('\n\n');

  const mockDoc = createMockDocument();
  const context = {
    module: { exports: {} },
    exports: {},
    document: mockDoc,
    ...overrides,
  };

  vm.runInNewContext(scriptSource, context);
  return context.module.exports;
}

test('buildNode creates a leaf div with correct class and title', () => {
  const { buildNode } = loadTopicsHierarchyDOM();
  const node = { name: 'test-topic', value: 42 };
  const result = buildNode(node, 'root', 0);

  assert.equal(result.className, 'th-leaf');
  assert.ok(result.title.startsWith('test-topic'));
  assert.equal(typeof result.style.backgroundColor, 'string');
  assert.equal(typeof result.style.borderLeftColor, 'string');
});

test('buildNode leaf includes label and count elements', () => {
  const { buildNode } = loadTopicsHierarchyDOM();
  const node = { name: 'test', value: 7 };
  const result = buildNode(node, 'root', 0);

  const label = result.children.find((c) => c.className === 'th-leaf__label');
  assert.ok(label, 'leaf should have a label element');
  assert.equal(label.textContent, 'test');

  const count = result.children.find((c) => c.className === 'th-leaf__count');
  assert.ok(count, 'leaf with value > 0 should have a count element');
  assert.equal(count.textContent, '7');
});

test('buildNode leaf with zero count omits count element', () => {
  const { buildNode } = loadTopicsHierarchyDOM();
  const node = { name: 'empty', value: 0 };
  const result = buildNode(node, 'root', 0);

  const count = result.children.find((c) => c.className === 'th-leaf__count');
  assert.equal(count, undefined, 'leaf with value 0 should not have count element');
});

test('buildNode leaf with _url creates a link inside label', () => {
  const { buildNode } = loadTopicsHierarchyDOM();
  const node = { name: 'linked', value: 1, _url: '/topics/linked' };
  const result = buildNode(node, 'root', 0);

  const label = result.children.find((c) => c.className === 'th-leaf__label');
  assert.ok(label, 'leaf should have a label element');
  const link = label.children.find((c) => c.tagName === 'a');
  assert.ok(link, 'label with _url should contain an anchor');
  assert.equal(link.href, '/topics/linked');
  assert.equal(link.textContent, 'linked');
});

test('buildNode non-leaf creates a node div with label and children container', () => {
  const { buildNode } = loadTopicsHierarchyDOM();
  const node = {
    name: 'parent',
    value: 10,
    children: [
      { name: 'child1', value: 3 },
      { name: 'child2', value: 5 },
    ],
  };
  const result = buildNode(node, 'root', 0);

  assert.equal(result.className, 'th-node');

  const label = result.children.find((c) => c.className === 'th-node__label');
  assert.ok(label, 'non-leaf should have a label panel');

  const childrenContainer = result.children.find((c) => c.className === 'th-node__children');
  assert.ok(childrenContainer, 'non-leaf should have a children container');
  assert.equal(childrenContainer.children.length, 2, 'should have 2 child elements');
});

test('buildNode non-leaf with _url creates a link in the label text', () => {
  const { buildNode } = loadTopicsHierarchyDOM();
  const node = {
    name: 'parent',
    value: 5,
    _url: '/topics/parent',
    children: [{ name: 'child', value: 1 }],
  };
  const result = buildNode(node, 'root', 0);

  const labelSticky = result.children[0].children.find(
    (c) => c.className === 'th-node__label-sticky'
  );
  assert.ok(labelSticky, 'label should contain a sticky wrapper');

  const labelText = labelSticky.children.find((c) => c.className === 'th-node__label-text');
  assert.ok(labelText, 'label sticky should contain label text');
  const link = labelText.children.find((c) => c.tagName === 'a');
  assert.ok(link, 'label text with _url should contain an anchor');
  assert.equal(link.href, '/topics/parent');
});

test('renderTopicsHierarchy does nothing with null container', () => {
  const { renderTopicsHierarchy } = loadTopicsHierarchyDOM();
  assert.doesNotThrow(() => {
    renderTopicsHierarchy(null, { children: [] });
  });
});

test('renderTopicsHierarchy renders empty state when no children', () => {
  const { renderTopicsHierarchy } = loadTopicsHierarchyDOM();
  const container = {
    innerHTML: '',
    children: [],
    childNodes: [],
    appendChild(child) {
      this.children.push(child);
      this.childNodes.push(child);
    },
  };
  renderTopicsHierarchy(container, { name: 'root', children: [] });

  const empty = container.children.find((c) => c.className === 'th-empty');
  assert.ok(empty, 'should render empty state when no children');
  assert.equal(empty.textContent, 'No topics available for this page.');
});

test('renderTopicsHierarchy renders topic roots into container', () => {
  const { renderTopicsHierarchy } = loadTopicsHierarchyDOM();
  const container = {
    innerHTML: '',
    children: [],
    childNodes: [],
    appendChild(child) {
      this.children.push(child);
      this.childNodes.push(child);
    },
  };
  const data = {
    name: 'root',
    children: [
      { name: 'topic1', value: 10, children: [{ name: 'sub1', value: 3 }] },
      { name: 'topic2', value: 5 },
    ],
  };

  renderTopicsHierarchy(container, data);

  const rootEl = container.children.find((c) => c.className === 'th-root');
  assert.ok(rootEl, 'should render a root wrapper element');
  assert.equal(rootEl.children.length, 2, 'should render 2 topic roots');
});

test('renderTopicsHierarchy handles data with no children gracefully', () => {
  const { renderTopicsHierarchy } = loadTopicsHierarchyDOM();
  const container = {
    innerHTML: '',
    children: [],
    childNodes: [],
    appendChild(child) {
      this.children.push(child);
      this.childNodes.push(child);
    },
  };
  assert.doesNotThrow(() => {
    renderTopicsHierarchy(container, {});
  });
});
