import test from 'node:test';
import assert from 'node:assert/strict';

// visibleLayoutIndices is pure, so it imports without any DOM stubbing.
const { visibleLayoutIndices } = await import('../components/feed-canvas.js');

/** @param {Array<{top: number, height: number}>} layouts @returns {number[]} */
function bruteForce(layouts, top, bottom) {
  const indices = [];
  layouts.forEach((layout, index) => {
    if (layout.top <= bottom && layout.top + layout.height >= top) indices.push(index);
  });
  return indices;
}

/** @param {Array<{top: number, height: number}>} layouts */
function sorted(layouts) {
  return [...layouts].sort((left, right) => left.top - right.top);
}

/** @param {Array<{top: number, height: number}>} layouts */
function tallest(layouts) {
  return layouts.reduce((maximum, layout) => Math.max(maximum, layout.height), 0);
}

/** Assert the binary search agrees with a scan over every element. */
function assertMatchesBruteForce(layouts, top, bottom, message) {
  const order = sorted(layouts);
  assert.deepEqual(
    visibleLayoutIndices(order, top, bottom, tallest(order)),
    bruteForce(order, top, bottom),
    message
  );
}

test('a card taller than the gap is kept when it starts above the band', () => {
  // The search starts maxHeight early precisely so this card is not skipped.
  const layouts = [
    { top: 0, height: 5 },
    { top: 10, height: 900 },
    { top: 20, height: 5 },
    { top: 500, height: 5 },
  ];
  const visible = visibleLayoutIndices(sorted(layouts), 600, 700, tallest(layouts));

  assert.deepEqual(visible, [1]);
});

test('every band over a mixed set matches a brute-force scan', () => {
  const layouts = [
    { top: 0, height: 5 },
    { top: 10, height: 900 },
    { top: 20, height: 5 },
    { top: 500, height: 5 },
    { top: 880, height: 5 },
  ];
  for (let band = 0; band < 1000; band += 7) {
    assertMatchesBruteForce(layouts, band, band + 50, `band starting at ${band}`);
  }
});

test('boundaries, empty input and out-of-range bands', () => {
  const touching = [
    { top: 0, height: 10 },
    { top: 50, height: 10 },
  ];

  assert.deepEqual(visibleLayoutIndices([], 0, 100, 0), []);
  assertMatchesBruteForce(touching, 10, 20, 'card bottom exactly on the band top');
  assertMatchesBruteForce(touching, 40, 50, 'card top exactly on the band bottom');
  assertMatchesBruteForce(touching, -500, -400, 'band entirely above');
  assertMatchesBruteForce(touching, 5000, 6000, 'band entirely below');
  assertMatchesBruteForce(touching, 15, 15, 'zero-height band');
});

test('duplicate tops do not confuse the lower bound', () => {
  const duplicates = Array.from({ length: 40 }, () => ({ top: 100, height: 30 }));

  assertMatchesBruteForce(duplicates, 110, 120, 'band inside the duplicates');
  assertMatchesBruteForce(duplicates, 200, 300, 'band past the duplicates');
});

test('randomised layouts always match a brute-force scan', () => {
  let seed = 42;
  const random = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);

  for (let trial = 0; trial < 500; trial += 1) {
    const layouts = Array.from({ length: Math.floor(random() * 60) }, () => ({
      top: Math.floor(random() * 2000),
      height: random() < 0.1 ? Math.floor(random() * 800) : Math.floor(random() * 40),
    }));
    const top = Math.floor(random() * 2200) - 100;
    assertMatchesBruteForce(layouts, top, top + Math.floor(random() * 400), `trial ${trial}`);
  }
});

test('a viewport-sized band renders a small fraction of a large rail', () => {
  // Roughly the shape of a real canvas: ~11.7k cards over a ~385k px document.
  const documentHeight = 583 * 660;
  const layouts = sorted(
    Array.from({ length: 11715 }, (_, index) => ({
      top: (index / 11715) * documentHeight + (index % 3) * 12,
      height: 20 + (index % 9) * 11,
    }))
  );
  const maxHeight = tallest(layouts);

  // Fully zoomed out is the widest band the canvas ever asks for.
  const band = (900 + 300 * 2) / 0.15;
  const zoomedOut = visibleLayoutIndices(layouts, 100000, 100000 + band, maxHeight);
  const normal = visibleLayoutIndices(layouts, 100000, 100000 + 900 + 300 * 2, maxHeight);

  assert.ok(zoomedOut.length < 500, `zoomed out kept ${zoomedOut.length} cards`);
  assert.ok(normal.length < 100, `normal zoom kept ${normal.length} cards`);
});
