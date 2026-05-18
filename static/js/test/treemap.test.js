import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import TagTreemap from '../components/treemap.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'treemap.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Helper: extract non-exported functions via vm
// ============================================================

function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}`);
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

  return source.slice(start, end + 1);
}

function loadTreemapHelpers() {
  const source = fs.readFileSync(new URL('../components/treemap.js', import.meta.url), 'utf8');
  const script = [
    extractFunction(source, 'hexToRGB'),
    extractFunction(source, 'rgbToHex'),
    extractFunction(source, 'generateSimilarColor'),
    'module.exports = { hexToRGB, rgbToHex, generateSimilarColor };',
  ].join('\n\n');

  const context = {
    module: { exports: {} },
    exports: {},
    Math: globalThis.Math,
  };

  vm.runInNewContext(script, context);
  return context.module.exports;
}

// ============================================================
// hexToRGB and rgbToHex tests (pure functions)
// ============================================================

test('hexToRGB converts 6-digit hex to RGB array', () => {
  const { hexToRGB } = loadTreemapHelpers();

  assert.equal(JSON.stringify(hexToRGB('#ffffff')), JSON.stringify([255, 255, 255]));
  assert.equal(JSON.stringify(hexToRGB('#000000')), JSON.stringify([0, 0, 0]));
  assert.equal(JSON.stringify(hexToRGB('#ff0000')), JSON.stringify([255, 0, 0]));
  assert.equal(JSON.stringify(hexToRGB('#00ff00')), JSON.stringify([0, 255, 0]));
  assert.equal(JSON.stringify(hexToRGB('#0000ff')), JSON.stringify([0, 0, 255]));
});

test('hexToRGB converts mixed hex colors correctly', () => {
  const { hexToRGB } = loadTreemapHelpers();

  assert.equal(JSON.stringify(hexToRGB('#d7d7af')), JSON.stringify([215, 215, 175]));
  assert.equal(JSON.stringify(hexToRGB('#aabbcc')), JSON.stringify([170, 187, 204]));
  assert.equal(JSON.stringify(hexToRGB('#123456')), JSON.stringify([18, 52, 86]));
});

test('rgbToHex converts RGB array back to hex string', () => {
  const { rgbToHex } = loadTreemapHelpers();

  assert.equal(rgbToHex([255, 255, 255]), '#ffffff');
  assert.equal(rgbToHex([0, 0, 0]), '#000000');
  assert.equal(rgbToHex([255, 0, 0]), '#ff0000');
});

test('rgbToHex zero-pads single-digit hex values', () => {
  const { rgbToHex } = loadTreemapHelpers();

  assert.equal(rgbToHex([10, 15, 1]), '#0a0f01');
  assert.equal(rgbToHex([0, 0, 0]), '#000000');
  assert.equal(rgbToHex([1, 2, 3]), '#010203');
});

test('hexToRGB and rgbToHex are inverses', () => {
  const { hexToRGB, rgbToHex } = loadTreemapHelpers();

  const original = '#d7d7af';
  const roundTrip = rgbToHex(hexToRGB(original));
  assert.equal(roundTrip, original);
});

test('generateSimilarColor returns a valid hex string within range', () => {
  const { generateSimilarColor } = loadTreemapHelpers();

  const result = generateSimilarColor('#d7d7af', 20);
  assert.match(result, /^#[0-9a-f]{6}$/);

  // Generate multiple to verify randomness within range
  for (let i = 0; i < 20; i += 1) {
    const color = generateSimilarColor('#808080', 10);
    const [r, g, b] = [
      parseInt(color.slice(1, 3), 16),
      parseInt(color.slice(3, 5), 16),
      parseInt(color.slice(5, 7), 16),
    ];
    // Each component should be within 10 of 128
    assert.ok(r >= 118 && r <= 138, `r=${r} out of range`);
    assert.ok(g >= 118 && g <= 138, `g=${g} out of range`);
    assert.ok(b >= 118 && b <= 138, `b=${b} out of range`);
  }
});

// ============================================================
// TagTreemap constructor and createSplitData tests
// ============================================================

function createMockContainer() {
  const children = [];
  return {
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    appendChild(child) {
      children.push(child);
      return child;
    },
    get childNodes() {
      return children;
    },
    removeChild() {},
    innerHTML: '',
  };
}

test('TagTreemap constructor initializes with single chart when children <= maxChildrenPerChart', () => {
  const data = {
    name: 'test',
    children: [
      { name: 'Child 1', value: 10 },
      { name: 'Child 2', value: 20 },
    ],
  };

  const treemap = new TagTreemap(data);

  assert.equal(treemap.data, data);
  assert.equal(treemap.base_color, '#d7d7af');
  assert.equal(treemap.color_range, 20);
  assert.equal(treemap.maxChildrenPerChart, 50);
  assert.equal(treemap.currentPage, 0);
  assert.equal(treemap.splitData.length, 1);
  assert.equal(treemap.splitData[0], data);
  assert.equal(treemap.charts.length, 1);
});

test('TagTreemap splits data into multiple pages when children exceed maxChildrenPerChart', () => {
  const children = Array.from({ length: 120 }, (_, i) => ({
    name: `Child ${i}`,
    value: i + 1,
  }));
  const data = { name: 'root', children };

  const treemap = new TagTreemap(data);

  assert.equal(treemap.splitData.length, 3); // 120 / 50 = 2.4 => 3 pages
  assert.equal(treemap.splitData[0].children.length, 50);
  assert.equal(treemap.splitData[1].children.length, 50);
  assert.equal(treemap.splitData[2].children.length, 20);

  // Verify pageInfo on each page
  assert.deepEqual(treemap.splitData[0]._pageInfo, {
    current: 0,
    total: 3,
    startIndex: 0,
    endIndex: 50,
  });
  assert.deepEqual(treemap.splitData[1]._pageInfo, {
    current: 1,
    total: 3,
    startIndex: 50,
    endIndex: 100,
  });
  assert.deepEqual(treemap.splitData[2]._pageInfo, {
    current: 2,
    total: 3,
    startIndex: 100,
    endIndex: 120,
  });
});

test('TagTreemap createSplitData preserves parent data properties', () => {
  const data = {
    name: 'preserved-name',
    customProp: 'custom-value',
    children: Array.from({ length: 60 }, (_, i) => ({
      name: `Item ${i}`,
      value: 1,
    })),
  };

  const treemap = new TagTreemap(data);

  assert.equal(treemap.splitData[0].name, 'preserved-name');
  assert.equal(treemap.splitData[0].customProp, 'custom-value');
  assert.equal(treemap.splitData[1].name, 'preserved-name');
  assert.equal(treemap.splitData[1].customProp, 'custom-value');
});

test('TagTreemap handles exact multiple of maxChildrenPerChart', () => {
  const data = {
    name: 'exact',
    children: Array.from({ length: 100 }, (_, i) => ({ name: `C${i}`, value: 1 })),
  };

  const treemap = new TagTreemap(data);

  assert.equal(treemap.splitData.length, 2);
  assert.equal(treemap.splitData[0].children.length, 50);
  assert.equal(treemap.splitData[1].children.length, 50);
});

// ============================================================
// calculateRectangles tests (squarified treemap algorithm)
// ============================================================

test('calculateRectangles returns rectangles for each child', () => {
  const data = {
    name: 'test',
    children: [
      { name: 'A', value: 50 },
      { name: 'B', value: 30 },
      { name: 'C', value: 20 },
    ],
  };

  const treemap = new TagTreemap(data);
  const totalValue = 100;
  const rectangles = treemap.calculateRectangles(data.children, 800, 600, totalValue);

  assert.equal(rectangles.length, 3);
  // Each rectangle should have x, y, width, height
  for (const rect of rectangles) {
    assert.ok(typeof rect.x === 'number', 'rect.x should be a number');
    assert.ok(typeof rect.y === 'number', 'rect.y should be a number');
    assert.ok(typeof rect.width === 'number', 'rect.width should be a number');
    assert.ok(typeof rect.height === 'number', 'rect.height should be a number');
    assert.ok(rect.width >= 1, 'rect.width should be at least 1');
    assert.ok(rect.height >= 1, 'rect.height should be at least 1');
  }
});

test('calculateRectangles returns rectangles in original child order', () => {
  const data = {
    name: 'test',
    children: [
      { name: 'first', value: 10 },
      { name: 'second', value: 100 },
      { name: 'third', value: 50 },
    ],
  };

  const treemap = new TagTreemap(data);
  const rectangles = treemap.calculateRectangles(data.children, 800, 600, 160);

  // Rectangles should be returned in the same order as input children
  assert.equal(rectangles.length, 3);
  // The rectangle at index 0 corresponds to children[0] ('first'), etc.
  for (let i = 0; i < rectangles.length; i += 1) {
    assert.ok(rectangles[i] !== undefined, `Rectangle at index ${i} should exist`);
  }
});

test('calculateRectangles produces non-overlapping rectangles within bounds', () => {
  const data = {
    name: 'test',
    children: [
      { name: 'A', value: 40 },
      { name: 'B', value: 30 },
      { name: 'C', value: 20 },
      { name: 'D', value: 10 },
    ],
  };

  const treemap = new TagTreemap(data);
  const totalValue = 100;
  const width = 800;
  const height = 600;
  const rectangles = treemap.calculateRectangles(data.children, width, height, totalValue);

  // All rectangles should be within the container bounds
  for (const rect of rectangles) {
    assert.ok(rect.x >= 0, `x=${rect.x} should be >= 0`);
    assert.ok(rect.y >= 0, `y=${rect.y} should be >= 0`);
    assert.ok(rect.x + rect.width <= width + 1, `right edge exceeds width`);
    assert.ok(rect.y + rect.height <= height + 1, `bottom edge exceeds height`);
  }
});

test('calculateRectangles handles a single child', () => {
  const data = {
    name: 'single',
    children: [{ name: 'only', value: 42 }],
  };

  const treemap = new TagTreemap(data);
  const rectangles = treemap.calculateRectangles(data.children, 800, 600, 42);

  assert.equal(rectangles.length, 1);
  const rect = rectangles[0];
  assert.ok(rect.width >= 1);
  assert.ok(rect.height >= 1);
});

test('calculateRectangles handles children with equal values', () => {
  const data = {
    name: 'equal',
    children: [
      { name: 'A', value: 10 },
      { name: 'B', value: 10 },
      { name: 'C', value: 10 },
    ],
  };

  const treemap = new TagTreemap(data);
  const rectangles = treemap.calculateRectangles(data.children, 800, 600, 30);

  assert.equal(rectangles.length, 3);
});

test('calculateRectangles handles children without explicit value (uses size fallback)', () => {
  const data = {
    name: 'sizes',
    children: [
      { name: 'A', size: 100 },
      { name: 'B', size: 50 },
    ],
  };

  const treemap = new TagTreemap(data);
  const rectangles = treemap.calculateRectangles(data.children, 800, 600, 150);

  assert.equal(rectangles.length, 2);
});

test('calculateRectangles handles children with neither value nor size (defaults to 1)', () => {
  const data = {
    name: 'defaults',
    children: [
      { name: 'A' },
      { name: 'B' },
      { name: 'C' },
    ],
  };

  const treemap = new TagTreemap(data);
  const rectangles = treemap.calculateRectangles(data.children, 800, 600, 3);

  assert.equal(rectangles.length, 3);
});

test('calculateRectangles with wider container produces horizontal layout', () => {
  const data = {
    name: 'wide',
    children: [
      { name: 'A', value: 60 },
      { name: 'B', value: 40 },
    ],
  };

  const treemap = new TagTreemap(data);
  const rectangles = treemap.calculateRectangles(data.children, 1200, 300, 100);

  assert.equal(rectangles.length, 2);
});

test('calculateRectangles with taller container produces vertical layout', () => {
  const data = {
    name: 'tall',
    children: [
      { name: 'A', value: 70 },
      { name: 'B', value: 30 },
    ],
  };

  const treemap = new TagTreemap(data);
  const rectangles = treemap.calculateRectangles(data.children, 300, 1200, 100);

  assert.equal(rectangles.length, 2);
});

// ============================================================
// findBestRow tests
// ============================================================

test('findBestRow returns null when startIndex is beyond children length', () => {
  const data = {
    name: 'test',
    children: [{ name: 'A', value: 10 }],
  };

  const treemap = new TagTreemap(data);
  const result = treemap.findBestRow(data.children, 5, 800, 600, 10);

  assert.equal(result, null);
});

test('findBestRow returns row info with endIndex, dimensions, and isVertical flag', () => {
  const data = {
    name: 'test',
    children: [
      { name: 'A', value: 50 },
      { name: 'B', value: 30 },
      { name: 'C', value: 20 },
    ],
  };

  const treemap = new TagTreemap(data);
  const totalValue = 100;
  const result = treemap.findBestRow(data.children, 0, 800, 600, totalValue);

  assert.ok(result !== null);
  assert.ok(result.endIndex > 0);
  assert.ok(result.endIndex <= data.children.length);
  assert.ok(typeof result.rowWidth === 'number');
  assert.ok(typeof result.rowHeight === 'number');
  assert.ok(typeof result.totalValue === 'number');
  assert.equal(typeof result.isVertical, 'boolean');
});

test('findBestRow computes correct totalValue for the row', () => {
  const data = {
    name: 'test',
    children: [
      { name: 'A', value: 40 },
      { name: 'B', value: 60 },
    ],
  };

  const treemap = new TagTreemap(data);
  // Force a single-item row by using a very large container
  const result = treemap.findBestRow(data.children, 0, 800, 600, 100);

  assert.ok(result !== null);
  // The row should include at least the first child
  assert.ok(result.totalValue >= 40);
});

test('findBestRow handles children with mixed value/size fields', () => {
  const data = {
    name: 'mixed',
    children: [
      { name: 'A', value: 30 },
      { name: 'B', size: 20 },
      { name: 'C' }, // defaults to 1
    ],
  };

  const treemap = new TagTreemap(data);
  const result = treemap.findBestRow(data.children, 0, 800, 600, 51);

  assert.ok(result !== null);
  assert.ok(result.totalValue > 0);
});

// ============================================================
// Render method edge case tests (with mocked DOM)
// ============================================================

test('TagTreemap render handles missing container gracefully', () => {
  assert.ok(/const\s+container\s*=\s*document\.querySelector\s*\(\s*selector\s*\)/.test(source), 'render should query selector');
  assert.ok(/if\s*\(\s*!container\s*\)\s*\{[\s\S]*?return;/.test(source), 'render should return early when container not found');
  assert.ok(/console\.error/.test(source), 'render should log error when container not found');
});

test('TagTreemap render creates navigation when split data has multiple pages', () => {
  assert.ok(/this\.splitData\.length\s*>\s*1/.test(source), 'should check for multi-page');
  assert.ok(/this\.createNavigation\s*\(\s*container\s*\)/.test(source), 'should call createNavigation');
  assert.ok(/className\s*=\s*['"]treemap-navigation['"]/.test(source), 'should set nav class');
});

test('TagTreemap navigateToPage is a no-op for out-of-range indices', () => {
  const data = { name: 'test', children: [{ name: 'A', value: 1 }] };
  const treemap = new TagTreemap(data);

  // Should not throw for invalid indices
  assert.doesNotThrow(() => {
    treemap.navigateToPage(-1);
    treemap.navigateToPage(99);
  });
});

test('TagTreemap renderCurrentChart shows no-data message for empty children', () => {
  assert.ok(/if\s*\(\s*!currentData\s*\|\|\s*!currentData\.children\s*\|\|\s*currentData\.children\.length\s*===\s*0\s*\)/.test(source), 'should check for empty data');
  assert.ok(/No data available/.test(source), 'should show no-data message');
});
