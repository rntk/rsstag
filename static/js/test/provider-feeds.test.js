import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// ============================================================
// Helpers
// ============================================================

function createMockElement(overrides = {}) {
  const listeners = new Map();
  const checkedState = { value: overrides.checked || false };

  return {
    tagName: overrides.tagName || 'INPUT',
    id: overrides.id || '',
    get checked() {
      return checkedState.value;
    },
    set checked(val) {
      checkedState.value = val;
    },
    addEventListener(event, handler) {
      listeners.set(event, handler);
    },
    _listeners: listeners,
    trigger(event) {
      const handler = listeners.get(event);
      if (handler) handler();
    },
  };
}

function createMockDocument(elementsById = {}) {
  const elements = {};
  const allItems = [];

  for (const [id, el] of Object.entries(elementsById)) {
    if (el.classList && el.classList.includes('selection-item')) {
      allItems.push(el);
    }
    elements[id] = el;
  }

  return {
    getElementById(id) {
      return elements[id] || null;
    },
    querySelectorAll(sel) {
      if (sel === '.selection-item') {
        return allItems;
      }
      return [];
    },
  };
}

function runProviderFeeds(overrides = {}) {
  const source = fs.readFileSync(new URL('../provider-feeds.js', import.meta.url), 'utf8');

  const context = {
    document: createMockDocument(),
    ...overrides,
  };

  vm.runInNewContext(source, context);
  return context;
}

// ============================================================
// Select-all checkbox tests
// ============================================================

test('select-all checkbox checks all items when changed to checked', () => {
  const selectAll = createMockElement({
    id: 'select_all',
    checked: false,
  });

  const items = [
    createMockElement({ checked: false }),
    createMockElement({ checked: false }),
    createMockElement({ checked: false }),
  ];

  for (const item of items) {
    item.classList = { includes: () => true };
  }

  const doc = createMockDocument({
    select_all: selectAll,
  });
  // Manually add items to the document's allItems
  doc.querySelectorAll = function (sel) {
    if (sel === '.selection-item') return items;
    return [];
  };

  runProviderFeeds({ document: doc });

  // Simulate the change event
  selectAll.checked = true;
  selectAll.trigger('change');

  for (const item of items) {
    assert.equal(item.checked, true, 'all items should be checked');
  }
});

test('select-all checkbox unchecks all items when changed to unchecked', () => {
  const selectAll = createMockElement({
    id: 'select_all',
    checked: true,
  });

  const items = [createMockElement({ checked: true }), createMockElement({ checked: true })];

  for (const item of items) {
    item.classList = { includes: () => true };
  }

  const doc = createMockDocument({
    select_all: selectAll,
  });
  doc.querySelectorAll = function (sel) {
    if (sel === '.selection-item') return items;
    return [];
  };

  runProviderFeeds({ document: doc });

  selectAll.checked = false;
  selectAll.trigger('change');

  for (const item of items) {
    assert.equal(item.checked, false, 'all items should be unchecked');
  }
});

test('no error when select_all element is missing', () => {
  const doc = createMockDocument({});

  assert.doesNotThrow(() => {
    runProviderFeeds({ document: doc });
  });
});
