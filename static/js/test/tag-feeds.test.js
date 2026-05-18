import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// ============================================================
// Helpers
// ============================================================

function createMockCell(classList = []) {
  const classes = new Set(classList);
  return {
    classList: {
      add(name) { classes.add(name); },
      remove(name) { classes.delete(name); },
      contains(name) { return classes.has(name); },
    },
    tagName: 'TD',
    matches(selector) {
      // Handle compound selectors like 'td, th'
      const parts = selector.split(',').map((s) => s.trim());
      return parts.some((part) => {
        if (part === 'td') return this.tagName === 'TD';
        if (part === 'th') return this.tagName === 'TH';
        return false;
      });
    },
    cellIndex: 0,
  };
}

function createMockRow(cells = []) {
  return { cells };
}

function createMockTable(rows = []) {
  return {
    rows,
    querySelector() { return null; },
    matches() { return false; },
  };
}

function createMockDocument(overrides = {}) {
  const table = overrides.table || null;

  return {
    querySelector(sel) {
      if (sel === '.table-bordered') return table;
      return null;
    },
    addEventListener(event, handler) {
      if (event === 'DOMContentLoaded') {
        handler();
      }
    },
  };
}

function runTagFeeds(overrides = {}) {
  const source = fs.readFileSync(
    new URL('../tag-feeds.js', import.meta.url),
    'utf8'
  );

  const context = {
    document: createMockDocument(),
    ...overrides,
  };

  vm.runInNewContext(source, context);
  return context;
}

// ============================================================
// Column hover tests
// ============================================================

test('mouseover on td adds hover-column class to all cells in that column', () => {
  const cell00 = createMockCell();
  cell00.cellIndex = 0;
  const cell01 = createMockCell();
  cell01.cellIndex = 1;
  const cell02 = createMockCell();
  cell02.cellIndex = 2;

  const cell10 = createMockCell();
  cell10.cellIndex = 0;
  const cell11 = createMockCell();
  cell11.cellIndex = 1;
  const cell12 = createMockCell();
  cell12.cellIndex = 2;

  const table = createMockTable([
    createMockRow([cell00, cell01, cell02]),
    createMockRow([cell10, cell11, cell12]),
  ]);

  table.matches = function() { return false; };

  // Track registered listeners
  let mouseoverHandler = null;
  table.addEventListener = function(event, handler) {
    if (event === 'mouseover') mouseoverHandler = handler;
  };

  runTagFeeds({
    document: createMockDocument({ table }),
  });

  assert.ok(mouseoverHandler, 'mouseover handler should be registered');

  // Simulate mouseover on column 1 (second column, index > 0)
  const event = {
    target: cell01,
  };
  mouseoverHandler(event);

  // Column 1 cells should have hover-column
  assert.equal(cell01.classList.contains('hover-column'), true);
  assert.equal(cell11.classList.contains('hover-column'), true);

  // Other columns should not be affected
  assert.equal(cell00.classList.contains('hover-column'), false);
  assert.equal(cell02.classList.contains('hover-column'), false);
  assert.equal(cell10.classList.contains('hover-column'), false);
  assert.equal(cell12.classList.contains('hover-column'), false);
});

test('mouseover on th adds hover-column class to all cells in that column', () => {
  const th0 = createMockCell();
  th0.cellIndex = 0;
  th0.tagName = 'TH';

  const th1 = createMockCell();
  th1.cellIndex = 1;
  th1.tagName = 'TH';

  const td0 = createMockCell();
  td0.cellIndex = 0;
  const td1 = createMockCell();
  td1.cellIndex = 1;

  const table = createMockTable([
    createMockRow([th0, th1]),
    createMockRow([td0, td1]),
  ]);
  table.matches = function() { return false; };

  let mouseoverHandler = null;
  table.addEventListener = function(event, handler) {
    if (event === 'mouseover') mouseoverHandler = handler;
  };

  runTagFeeds({
    document: createMockDocument({ table }),
  });

  const event = { target: th1 };
  mouseoverHandler(event);

  assert.equal(th1.classList.contains('hover-column'), true);
  assert.equal(td1.classList.contains('hover-column'), true);
});

test('mouseover on first column (cellIndex 0) does not add hover-column', () => {
  const cell00 = createMockCell();
  cell00.cellIndex = 0;
  const cell01 = createMockCell();
  cell01.cellIndex = 1;

  const table = createMockTable([
    createMockRow([cell00, cell01]),
  ]);
  table.matches = function() { return false; };

  let mouseoverHandler = null;
  table.addEventListener = function(event, handler) {
    if (event === 'mouseover') mouseoverHandler = handler;
  };

  runTagFeeds({
    document: createMockDocument({ table }),
  });

  const event = { target: cell00 };
  mouseoverHandler(event);

  assert.equal(cell00.classList.contains('hover-column'), false);
  assert.equal(cell01.classList.contains('hover-column'), false);
});

test('mouseout removes hover-column from all cells in that column', () => {
  const cell00 = createMockCell();
  cell00.cellIndex = 0;
  const cell01 = createMockCell(['hover-column']);
  cell01.cellIndex = 1;
  const cell02 = createMockCell();
  cell02.cellIndex = 2;

  const cell10 = createMockCell();
  cell10.cellIndex = 0;
  const cell11 = createMockCell(['hover-column']);
  cell11.cellIndex = 1;
  const cell12 = createMockCell();
  cell12.cellIndex = 2;

  const table = createMockTable([
    createMockRow([cell00, cell01, cell02]),
    createMockRow([cell10, cell11, cell12]),
  ]);
  table.matches = function() { return false; };

  let mouseoverHandler = null;
  let mouseoutHandler = null;
  table.addEventListener = function(event, handler) {
    if (event === 'mouseover') mouseoverHandler = handler;
    if (event === 'mouseout') mouseoutHandler = handler;
  };

  runTagFeeds({
    document: createMockDocument({ table }),
  });

  // Simulate mouseout on column 1
  const event = { target: cell01 };
  mouseoutHandler(event);

  assert.equal(cell01.classList.contains('hover-column'), false);
  assert.equal(cell11.classList.contains('hover-column'), false);

  // Other columns should not be affected
  assert.equal(cell02.classList.contains('hover-column'), false);
});

test('mouseout on first column does not remove hover-column', () => {
  const cell00 = createMockCell(['hover-column']);
  cell00.cellIndex = 0;
  const cell01 = createMockCell(['hover-column']);
  cell01.cellIndex = 1;

  const table = createMockTable([
    createMockRow([cell00, cell01]),
  ]);
  table.matches = function() { return false; };

  let mouseoutHandler = null;
  table.addEventListener = function(event, handler) {
    if (event === 'mouseout') mouseoutHandler = handler;
  };

  runTagFeeds({
    document: createMockDocument({ table }),
  });

  const event = { target: cell00 };
  mouseoutHandler(event);

  // First column should not be affected
  assert.equal(cell00.classList.contains('hover-column'), true);
  assert.equal(cell01.classList.contains('hover-column'), true);
});

test('no error when table element is missing', () => {
  assert.doesNotThrow(() => {
    runTagFeeds({
      document: createMockDocument({ table: null }),
    });
  });
});

test('no error when document.querySelector returns null', () => {
  assert.doesNotThrow(() => {
    runTagFeeds({
      document: {
        querySelector() { return null; },
        addEventListener() {},
      },
    });
  });
});

test('mouseover on non-cell element does not add hover-column', () => {
  const cell00 = createMockCell();
  cell00.cellIndex = 0;
  const cell01 = createMockCell();
  cell01.cellIndex = 1;

  const table = createMockTable([
    createMockRow([cell00, cell01]),
  ]);
  table.matches = function() { return false; };

  let mouseoverHandler = null;
  table.addEventListener = function(event, handler) {
    if (event === 'mouseover') mouseoverHandler = handler;
  };

  runTagFeeds({
    document: createMockDocument({ table }),
  });

  // Target is a div, not td or th
  const fakeTarget = {
    tagName: 'DIV',
    matches(sel) { return false; },
    cellIndex: 1,
  };

  assert.doesNotThrow(() => {
    mouseoverHandler({ target: fakeTarget });
  });

  assert.equal(cell01.classList.contains('hover-column'), false);
});
