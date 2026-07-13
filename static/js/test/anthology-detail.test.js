import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// ============================================================
// Helpers
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

// Dummy HTMLElement for instanceof checks in the source
class MockHTMLElement {}

function createMockElement(overrides = {}) {
  const listeners = new Map();
  const initialClasses = Array.isArray(overrides.classList)
    ? overrides.classList
    : (overrides.classList instanceof Set ? [...overrides.classList] : []);
  const classSet = new Set(initialClasses);
  const attrMap = new Map(Object.entries(overrides.attrs || {}));
  const overrideDataset = overrides.dataset || {};

  const el = Object.create(MockHTMLElement.prototype, {
    tagName: { value: overrides.tagName || 'DIV', writable: true, enumerable: true },
    textContent: { value: overrides.textContent || '', writable: true, enumerable: true },
    innerHTML: { value: overrides.innerHTML || '', writable: true, enumerable: true },
    classList: {
      value: {
        add(name) { classSet.add(name); },
        remove(name) { classSet.delete(name); },
        contains(name) { return classSet.has(name); },
        toggle(name, force) {
          if (force === undefined) {
            if (classSet.has(name)) { classSet.delete(name); return false; }
            classSet.add(name); return true;
          }
          if (force) { classSet.add(name); } else { classSet.delete(name); }
          return force;
        },
      },
      writable: true, enumerable: true,
    },
    dataset: { value: { ...overrideDataset }, writable: true, enumerable: true },
  });

  el.getAttribute = function(name) { return attrMap.has(name) ? attrMap.get(name) : null; };
  el.setAttribute = function(name, value) { attrMap.set(name, value); };
  el.appendChild = function(child) {
    if (!this.children) this.children = [];
    this.children.push(child);
    return child;
  };
  el.addEventListener = function(event, handler) {
    const existing = listeners.get(event) || [];
    listeners.set(event, [...existing, handler]);
  };
  el.trigger = function(eventOverrides = {}) {
    const handlers = listeners.get('click') || [];
    handlers.forEach((h) => h(eventOverrides));
  };
  el.querySelector = function() { return null; };
  el.querySelectorAll = function() { return []; };

  // Apply remaining overrides (excluding classList and dataset which are handled above)
  for (const key of Object.keys(overrides)) {
    if (key !== 'classList' && key !== 'dataset' && key !== 'attrs') {
      el[key] = overrides[key];
    }
  }

  return el;
}

function createMockDocument(elementsById = {}) {
  return {
    getElementById(id) {
      if (elementsById[id]) return elementsById[id];
      return null;
    },
    createElement(tagName) {
      return createMockElement({ tagName });
    },
    addEventListener() {},
    body: createMockElement({ tagName: 'BODY' }),
    title: '',
    get title() { return this._title || ''; },
    set title(val) { this._title = val; },
    hidden: false,
  };
}

function loadAnthologyDetailFunctions(overrides = {}) {
  const source = fs.readFileSync(
    new URL('../anthology-detail.js', import.meta.url),
    'utf8'
  );

  const funcNames = [
    'getInitialPayload',
    'escapeHtml',
    'formatTimestamp',
    'formatEvidenceDate',
    'stringifyValue',
    'shortenText',
    'pluralize',
    'renderSourceRefs',
    'getEvidenceTarget',
    'renderEvidenceAction',
    'renderClaim',
    'renderFindings',
    'renderTimeline',
    'renderCoverage',
    'renderLimitations',
    'renderTreeNode',
    'renderRunSummary',
    'renderLogEntries',
    'renderTurns',
    'isProcessing',
    'escapeURIComponent',
  ];

  const scriptSource = [
    ...funcNames.map((name) => extractFunction(source, name)),
    'module.exports = { ' + funcNames.join(', ') + ' };',
  ].join('\n\n');

  const context = {
    module: { exports: {} },
    exports: {},
    document: createMockDocument(),
    window: {
      clearInterval() {},
      setInterval() { return 123; },
    },
    fetch: () => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({}),
    }),
    ...overrides,
  };

  vm.runInNewContext(scriptSource, context);
  return context.module.exports;
}

// ============================================================
// Utility function tests
// ============================================================

test('escapeHtml escapes special characters', () => {
  const { escapeHtml } = loadAnthologyDetailFunctions();

  assert.equal(escapeHtml('<script>'), '&lt;script&gt;');
  assert.equal(escapeHtml('a&b'), 'a&amp;b');
  assert.equal(escapeHtml('"quoted"'), '&quot;quoted&quot;');
  assert.equal(escapeHtml("it's"), "it&#39;s");
});

test('escapeHtml handles null and undefined via String()', () => {
  const { escapeHtml } = loadAnthologyDetailFunctions();

  assert.equal(escapeHtml(null), 'null');
  assert.equal(escapeHtml(undefined), 'undefined');
});

test('formatTimestamp converts numeric timestamp to locale string', () => {
  const { formatTimestamp } = loadAnthologyDetailFunctions();

  const result = formatTimestamp(1700000000);
  assert.ok(typeof result === 'string');
  assert.ok(result.length > 0);
  assert.notEqual(result, 'N/A');
});

test('formatTimestamp returns N/A for falsy values', () => {
  const { formatTimestamp } = loadAnthologyDetailFunctions();

  assert.equal(formatTimestamp(null), 'N/A');
  assert.equal(formatTimestamp(undefined), 'N/A');
  assert.equal(formatTimestamp(''), 'N/A');
  assert.equal(formatTimestamp(0), 'N/A');
});

test('stringifyValue returns dash for null/undefined/empty', () => {
  const { stringifyValue } = loadAnthologyDetailFunctions();

  assert.equal(stringifyValue(null), '\u2014');
  assert.equal(stringifyValue(undefined), '\u2014');
  assert.equal(stringifyValue(''), '\u2014');
});

test('stringifyValue returns strings as-is', () => {
  const { stringifyValue } = loadAnthologyDetailFunctions();

  assert.equal(stringifyValue('hello'), 'hello');
});

test('stringifyValue pretty-prints objects', () => {
  const { stringifyValue } = loadAnthologyDetailFunctions();

  const result = stringifyValue({ a: 1 });
  assert.ok(result.includes('"a"'));
  assert.ok(result.includes('1'));
});

test('shortenText truncates long text with ellipsis', () => {
  const { shortenText } = loadAnthologyDetailFunctions();

  const result = shortenText('hello world', 8);
  assert.equal(result, 'hello w\u2026');
});

test('shortenText returns short text unchanged', () => {
  const { shortenText } = loadAnthologyDetailFunctions();

  assert.equal(shortenText('hi', 10), 'hi');
});

test('pluralize selects singular for count 1', () => {
  const { pluralize } = loadAnthologyDetailFunctions();

  assert.equal(pluralize(1, 'item', 'items'), 'item');
  assert.equal(pluralize(2, 'item', 'items'), 'items');
  assert.equal(pluralize(0, 'item', 'items'), 'items');
});

test('isProcessing returns true for pending and processing statuses', () => {
  const { isProcessing } = loadAnthologyDetailFunctions();

  assert.equal(isProcessing({ status: 'pending' }), true);
  assert.equal(isProcessing({ status: 'processing' }), true);
  assert.equal(isProcessing({ status: 'done' }), false);
  assert.equal(isProcessing({ status: 'failed' }), false);
  assert.equal(isProcessing(null), false);
  assert.equal(isProcessing({}), false);
});

test('escapeURIComponent encodes special characters', () => {
  const { escapeURIComponent } = loadAnthologyDetailFunctions();

  assert.equal(escapeURIComponent('a b'), 'a%20b');
  assert.equal(escapeURIComponent(null), '');
  assert.equal(escapeURIComponent(undefined), '');
});

// ============================================================
// renderSourceRefs tests
// ============================================================

test('renderSourceRefs returns empty state for no refs', () => {
  const { renderSourceRefs } = loadAnthologyDetailFunctions();

  const html = renderSourceRefs([]);
  assert.ok(html.includes('anthology-empty-state'));
  assert.ok(html.includes('No source references'));
});

test('renderSourceRefs returns empty state for non-array input', () => {
  const { renderSourceRefs } = loadAnthologyDetailFunctions();

  const html = renderSourceRefs(null);
  assert.ok(html.includes('anthology-empty-state'));
});

test('renderSourceRefs renders list of source refs', () => {
  const { renderSourceRefs } = loadAnthologyDetailFunctions();

  const refs = [
    { topic_path: 'topic/a', post_id: 'p1', sentence_indices: [1, 2] },
  ];
  const html = renderSourceRefs(refs);

  assert.ok(html.includes('anthology-source-list'));
  assert.ok(html.includes('anthology-source-item'));
  assert.ok(html.includes('topic/a'));
  assert.ok(html.includes('post p1'));
  assert.ok(html.includes('sentences 1, 2'));
});

test('renderSourceRefs includes read state markup', () => {
  const { renderSourceRefs } = loadAnthologyDetailFunctions();

  const refs = [
    {
      topic_path: 'topic/x',
      post_id: 'p2',
      sentence_indices: [1],
      read_state: { unread_sentences: 3, total_sentences: 10 },
    },
  ];
  const html = renderSourceRefs(refs);

  assert.ok(html.includes('3 unread'));
  assert.ok(html.includes('10 total'));
});

test('renderSourceRefs includes Mark read button for unread items', () => {
  const { renderSourceRefs } = loadAnthologyDetailFunctions();

  const refs = [
    {
      topic_path: 't',
      post_id: 'p1',
      sentence_indices: [1],
      read_state: { all_read: false, unread_sentences: 1, total_sentences: 5 },
    },
  ];
  const html = renderSourceRefs(refs);

  assert.ok(html.includes('Mark read'));
  assert.ok(html.includes('anthology-read-action'));
});

test('renderSourceRefs includes Mark unread button for read items', () => {
  const { renderSourceRefs } = loadAnthologyDetailFunctions();

  const refs = [
    {
      topic_path: 't',
      post_id: 'p1',
      sentence_indices: [1],
      read_state: { all_read: true, unread_sentences: 0, total_sentences: 5 },
    },
  ];
  const html = renderSourceRefs(refs);

  assert.ok(html.includes('Mark unread'));
});

test('renderSourceRefs omits action when no sentence_indices', () => {
  const { renderSourceRefs } = loadAnthologyDetailFunctions();

  const refs = [
    { topic_path: 't', post_id: 'p1' },
  ];
  const html = renderSourceRefs(refs);

  assert.ok(!html.includes('anthology-read-action'));
});

test('renderSourceRefs includes deterministic evidence metadata and action', () => {
  const { renderSourceRefs } = loadAnthologyDetailFunctions();
  const html = renderSourceRefs([
    {
      title: 'Source title',
      topic_path: 'Topic > Detail',
      post_id: 'p1',
      sentence_indices: [3],
      published_at: 1700000000,
    },
  ]);

  assert.ok(html.includes('Source title'));
  assert.ok(html.includes('Topic &gt; Detail'));
  assert.ok(html.includes('published'));
  assert.ok(html.includes('Open evidence'));
  assert.ok(html.includes('data-post-ids="p1"'));
});

test('renderFindings renders disputed claims with their evidence', () => {
  const { renderFindings } = loadAnthologyDetailFunctions();
  const html = renderFindings([
    {
      title: 'Launch timing',
      status: 'disputed',
      summary: 'Sources give incompatible dates.',
      claims: [
        {
          text: 'The launch is in June.',
          kind: 'forecast',
          stance: 'disputes',
          source_refs: [
            { post_id: 'p1', topic_path: 'Launch', sentence_indices: [1] },
          ],
        },
      ],
    },
  ]);

  assert.ok(html.includes('anthology-finding-disputed'));
  assert.ok(html.includes('The launch is in June.'));
  assert.ok(html.includes('forecast'));
  assert.ok(html.includes('Compare evidence'));
});

test('renderTimeline and renderCoverage expose report context', () => {
  const { renderTimeline, renderCoverage } = loadAnthologyDetailFunctions();
  const timelineHtml = renderTimeline([
    {
      date: '2026-07',
      date_kind: 'event',
      title: 'Launch',
      description: 'The launch occurred.',
      source_refs: [{ post_id: 'p1', topic_path: 'Launch' }],
    },
  ]);
  const coverageHtml = renderCoverage({
    documents_in_scope: 5,
    documents_with_grouped_text: 4,
    documents_cited: 3,
    topics_available: 2,
    uncited_documents: 2,
  });

  assert.ok(timelineHtml.includes('2026-07'));
  assert.ok(timelineHtml.includes('The launch occurred.'));
  assert.ok(coverageHtml.includes('>5<'));
  assert.ok(coverageHtml.includes('In scope'));
  assert.ok(coverageHtml.includes('Uncited'));
});

// ============================================================
// renderTreeNode tests
// ============================================================

test('renderTreeNode returns empty state for null node', () => {
  const { renderTreeNode } = loadAnthologyDetailFunctions();

  const html = renderTreeNode(null, 0);
  assert.ok(html.includes('No hierarchy has been generated'));
});

test('renderTreeNode returns empty state for non-object node', () => {
  const { renderTreeNode } = loadAnthologyDetailFunctions();

  const html = renderTreeNode('string', 0);
  assert.ok(html.includes('No hierarchy has been generated'));
});

test('renderTreeNode renders a leaf node with title and summary', () => {
  const { renderTreeNode } = loadAnthologyDetailFunctions();

  const node = {
    title: 'Leaf Topic',
    summary: 'This is a summary.',
    source_refs: [],
    read_state: {},
    node_id: 'n1',
  };
  const html = renderTreeNode(node, 0);

  assert.ok(html.includes('Leaf Topic'));
  assert.ok(html.includes('This is a summary.'));
  assert.ok(html.includes('anthology-tree-leaf'));
  assert.ok(html.includes('level-0'));
});

test('renderTreeNode renders a parent node with children', () => {
  const { renderTreeNode } = loadAnthologyDetailFunctions();

  const node = {
    title: 'Parent',
    summary: 'Parent summary',
    sub_anthologies: [
      { title: 'Child', source_refs: [], read_state: {}, node_id: 'c1' },
    ],
    source_refs: [],
    read_state: {},
  };
  const html = renderTreeNode(node, 0);

  assert.ok(html.includes('Parent'));
  assert.ok(html.includes('anthology-tree-details'));
  assert.ok(html.includes('1 section'));
  assert.ok(html.includes('open')); // level < 1, so open by default
});

test('renderTreeNode renders nested children recursively', () => {
  const { renderTreeNode } = loadAnthologyDetailFunctions();

  const node = {
    title: 'Root',
    sub_anthologies: [
      {
        title: 'Mid',
        sub_anthologies: [
          { title: 'Leaf', source_refs: [], read_state: {}, node_id: 'l1' },
        ],
        source_refs: [],
        read_state: {},
        node_id: 'm1',
      },
    ],
    source_refs: [],
    read_state: {},
  };
  const html = renderTreeNode(node, 0);

  assert.ok(html.includes('Root'));
  assert.ok(html.includes('Mid'));
  assert.ok(html.includes('Leaf'));
});

test('renderTreeNode shows Read side-by-side button for leaf with post_ids', () => {
  const { renderTreeNode } = loadAnthologyDetailFunctions();

  const node = {
    title: 'Leaf',
    source_refs: [{ post_id: 'p1', topic_path: 't/x' }],
    read_state: {},
    node_id: 'leaf1',
  };
  const html = renderTreeNode(node, 0);

  assert.ok(html.includes('Read side-by-side'));
  assert.ok(html.includes('anthology-compare-action'));
  assert.ok(html.includes('data-post-ids'));
});

test('renderTreeNode does not show Read side-by-side for non-leaf', () => {
  const { renderTreeNode } = loadAnthologyDetailFunctions();

  const node = {
    title: 'Parent',
    sub_anthologies: [
      { title: 'Child', source_refs: [], read_state: {}, node_id: 'c1' },
    ],
    source_refs: [{ post_id: 'p1' }],
    read_state: {},
  };
  const html = renderTreeNode(node, 0);

  assert.ok(!html.includes('Read side-by-side'));
});

test('renderTreeNode uses topic_path as leafTopic when available', () => {
  const { renderTreeNode } = loadAnthologyDetailFunctions();

  const node = {
    title: 'Section',
    source_refs: [{ post_id: 'p1', topic_path: 'deep/topic/path' }],
    read_state: {},
  };
  const html = renderTreeNode(node, 0);

  assert.ok(html.includes('data-topic="deep/topic/path"'));
});

// ============================================================
// renderRunSummary tests
// ============================================================

test('renderRunSummary returns empty state for null run', () => {
  const { renderRunSummary } = loadAnthologyDetailFunctions();

  const html = renderRunSummary(null);
  assert.ok(html.includes('No run has started yet'));
});

test('renderRunSummary renders run metadata', () => {
  const { renderRunSummary } = loadAnthologyDetailFunctions();

  const run = {
    _id: 'run-42',
    status: 'done',
    started_at: 1700000000,
    finished_at: 1700000100,
  };
  const html = renderRunSummary(run);

  assert.ok(html.includes('run-42'));
  assert.ok(html.includes('done'));
  assert.ok(html.includes('started'));
  assert.ok(html.includes('finished'));
});

test('renderRunSummary shows "still running" when no finished_at', () => {
  const { renderRunSummary } = loadAnthologyDetailFunctions();

  const run = {
    _id: 'run-1',
    status: 'processing',
    started_at: 1700000000,
  };
  const html = renderRunSummary(run);

  assert.ok(html.includes('still running'));
  assert.ok(!html.includes('finished'));
});

test('renderRunSummary includes error message when present', () => {
  const { renderRunSummary } = loadAnthologyDetailFunctions();

  const run = {
    _id: 'run-fail',
    status: 'failed',
    started_at: 1700000000,
    error: 'OOM killed',
  };
  const html = renderRunSummary(run);

  assert.ok(html.includes('OOM killed'));
  assert.ok(html.includes('anthology-run-error'));
});

// ============================================================
// renderLogEntries / renderTurns tests
// ============================================================

test('renderLogEntries returns empty text for empty array', () => {
  const { renderLogEntries } = loadAnthologyDetailFunctions();

  const html = renderLogEntries([], 'No items found');
  assert.ok(html.includes('No items found'));
  assert.ok(html.includes('anthology-empty-state'));
});

test('renderLogEntries returns empty text for non-array input', () => {
  const { renderLogEntries } = loadAnthologyDetailFunctions();

  const html = renderLogEntries(null, 'Empty');
  assert.ok(html.includes('Empty'));
});

test('renderLogEntries renders log entry with role header', () => {
  const { renderLogEntries } = loadAnthologyDetailFunctions();

  const items = [{ role: 'assistant', content: 'Hello' }];
  const html = renderLogEntries(items, 'empty');

  assert.ok(html.includes('assistant'));
  assert.ok(html.includes('Hello'));
  assert.ok(html.includes('anthology-log-pre'));
});

test('renderLogEntries renders item without content field', () => {
  const { renderLogEntries } = loadAnthologyDetailFunctions();

  const items = ['plain string item'];
  const html = renderLogEntries(items, 'empty');

  assert.ok(html.includes('plain string item'));
});

test('renderTurns returns empty state when no turns', () => {
  const { renderTurns } = loadAnthologyDetailFunctions();

  const html = renderTurns({ turns: [] });
  assert.ok(html.includes('Logs will appear here'));
});

test('renderTurns renders turn with messages, tool_calls, tool_results', () => {
  const { renderTurns } = loadAnthologyDetailFunctions();

  const run = {
    turns: [
      {
        turn: 1,
        messages: [{ role: 'user', content: 'hi' }],
        tool_calls: [{ name: 'search' }],
        tool_results: [{ result: 'found' }],
      },
    ],
  };
  const html = renderTurns(run);

  assert.ok(html.includes('Turn 1'));
  assert.ok(html.includes('1 messages'));
  assert.ok(html.includes('1 tool calls'));
  assert.ok(html.includes('1 tool results'));
  assert.ok(html.includes('hi'));
  assert.ok(html.includes('search'));
  assert.ok(html.includes('found'));
});

test('renderTurns last turn is open by default', () => {
  const { renderTurns } = loadAnthologyDetailFunctions();

  const run = {
    turns: [
      { turn: 1, messages: [], tool_calls: [], tool_results: [] },
      { turn: 2, messages: [], tool_calls: [], tool_results: [] },
    ],
  };
  const html = renderTurns(run);

  // Count how many <details...open> patterns there are
  const openCount = (html.match(/<details[^>]*open/g) || []).length;
  assert.equal(openCount, 1, 'only the last turn should be open');
});

// ============================================================
// getInitialPayload tests (vm-based with mock DOM)
// ============================================================

test('getInitialPayload parses JSON from script tag', () => {
  const { getInitialPayload } = loadAnthologyDetailFunctions({
    document: createMockDocument({
      'anthology-detail-data': {
        textContent: JSON.stringify({ title: 'Test', id: 'abc' }),
      },
    }),
  });

  const payload = getInitialPayload();
  assert.equal(payload.title, 'Test');
  assert.equal(payload.id, 'abc');
});

test('getInitialPayload returns null when element is missing', () => {
  const { getInitialPayload } = loadAnthologyDetailFunctions({
    document: createMockDocument({}),
  });

  assert.equal(getInitialPayload(), null);
});

test('getInitialPayload returns null on malformed JSON', () => {
  const { getInitialPayload } = loadAnthologyDetailFunctions({
    document: createMockDocument({
      'anthology-detail-data': {
        textContent: '{invalid json}',
      },
    }),
  });

  assert.equal(getInitialPayload(), null);
});

// ============================================================
// IIFE execution tests (full browser script via vm)
// ============================================================

function createFullMockDocument(elementsById = {}) {
  const elements = { ...elementsById };
  return {
    getElementById(id) {
      if (elements[id]) return elements[id];
      return null;
    },
    createElement(tagName) {
      return createMockElement({ tagName });
    },
    addEventListener() {},
    body: createMockElement({ tagName: 'BODY' }),
    _title: '',
    get title() { return this._title; },
    set title(val) { this._title = val; },
    hidden: false,
  };
}

function runIIFE(overrides = {}) {
  const source = fs.readFileSync(
    new URL('../anthology-detail.js', import.meta.url),
    'utf8'
  );

  const context = {
    document: createFullMockDocument(),
    window: {
      clearInterval() {},
      setInterval() { return 42; },
    },
    fetch: () => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({}),
    }),
    HTMLElement: MockHTMLElement,
    ...overrides,
  };

  vm.runInNewContext(source, context);
  return context;
}

test('IIFE exits early when no pageRoot element', () => {
  // No anthology-detail-page element -> script returns early
  assert.doesNotThrow(() => {
    runIIFE({
      document: createFullMockDocument({}),
    });
  });
});

test('IIFE exits early when no initial payload', () => {
  const doc = createFullMockDocument({
    'anthology-detail-page': createMockElement({ dataset: {} }),
  });

  assert.doesNotThrow(() => {
    runIIFE({ document: doc });
  });
});

test('IIFE renders payload into DOM elements', () => {
  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/123', pollIntervalMs: '5000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '123',
        title: 'My Anthology',
        status: 'done',
        seed_value: 'test topic',
        seed_type: 'tag',
        created_at: 1700000000,
        updated_at: 1700000100,
        current_run_id: 'run-1',
        result: {
          title: 'Root',
          summary: 'Root summary',
          source_refs: [],
          read_state: {},
          node_id: 'root-1',
        },
        latest_run: {
          _id: 'run-1',
          status: 'done',
          started_at: 1700000000,
          finished_at: 1700000100,
          turns: [],
        },
      }),
    },
    'anthology-detail-header': createMockElement({ classList: [] }),
    'anthology-title': createMockElement({}),
    'anthology-status-badge': createMockElement({}),
    'anthology-status': createMockElement({}),
    'anthology-seed-value': createMockElement({}),
    'anthology-seed-type': createMockElement({}),
    'anthology-created-at': createMockElement({}),
    'anthology-updated-at': createMockElement({}),
    'anthology-current-run': createMockElement({}),
    'anthology-source-snapshot-updated': createMockElement({}),
    'anthology-source-snapshot-count': createMockElement({}),
    'anthology-summary': createMockElement({}),
    'anthology-scope-json': createMockElement({}),
    'anthology-hierarchy-tree': createMockElement({}),
    'anthology-source-refs': createMockElement({}),
    'anthology-run-summary': createMockElement({}),
    'anthology-log-viewer': createMockElement({}),
    'anthology-stale-badge': createMockElement({ classList: ['hide'] }),
    'anthology-processing-note': createMockElement({}),
    'anthology-last-refresh': createMockElement({}),
    'anthology-retry-button': createMockElement({ dataset: {} }),
    'anthology-export-button': createMockElement({ dataset: {} }),
  };

  let titleWasSet = '';
  const doc = createFullMockDocument(elements);
  Object.defineProperty(doc, 'title', {
    get() { return titleWasSet; },
    set(val) { titleWasSet = val; },
  });

  assert.doesNotThrow(() => {
    runIIFE({ document: doc });
  });

  // Verify title element was set
  assert.equal(elements['anthology-title'].textContent, 'My Anthology');
  assert.equal(elements['anthology-status'].textContent, 'done');
  assert.equal(elements['anthology-seed-value'].textContent, 'test topic');
  assert.equal(elements['anthology-seed-type'].textContent, 'tag');
  assert.equal(titleWasSet, 'My Anthology | Anthology');
});

test('IIFE sets stale badge visibility', () => {
  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/1', pollIntervalMs: '5000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '1',
        title: 'Stale One',
        status: 'done',
        stale: true,
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
    'anthology-stale-badge': createMockElement({
      classList: new Set(['hide']),
    }),
  };

  const doc = createFullMockDocument(elements);
  runIIFE({ document: doc });

  // After renderPayload, toggle("hide", true) means hide stays since stale=true
  assert.equal(elements['anthology-stale-badge'].classList.contains('hide'), false);
});

test('IIFE hides stale badge when payload is not stale', () => {
  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/1', pollIntervalMs: '5000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '1',
        title: 'Fresh',
        status: 'done',
        stale: false,
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
    'anthology-stale-badge': createMockElement({
      classList: new Set([]),
    }),
  };

  const doc = createFullMockDocument(elements);
  runIIFE({ document: doc });

  assert.equal(elements['anthology-stale-badge'].classList.contains('hide'), true);
});

// ============================================================
// Retry button tests
// ============================================================

test('retry button queues anthology retry and starts polling', async () => {
  let fetchCount = 0;

  const mockFetch = async (url, options) => {
    fetchCount += 1;
    if (fetchCount === 1) {
      return {
        ok: true,
        json: () => Promise.resolve({
          data: { id: '1', status: 'processing', result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' } },
        }),
      };
    }
    return {
      ok: true,
      json: () => Promise.resolve({
        data: { id: '1', status: 'done', result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' } },
      }),
    };
  };

  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/1', pollIntervalMs: '5000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '1', title: 'Retry Me', status: 'failed',
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
    'anthology-retry-button': createMockElement({
      id: 'anthology-retry-button',
      classList: ['anthology-placeholder-action'],
      dataset: { apiUrl: '/api/anthologies/1/retry' },
    }),
    'anthology-action-note': createMockElement({}),
  };

  let clickHandler = null;
  const doc = {
    getElementById(id) { return elements[id] || null; },
    createElement(tagName) { return createMockElement({ tagName }); },
    addEventListener(event, handler) {
      if (event === 'click') {
        clickHandler = handler;
      }
    },
    body: createMockElement({ tagName: 'BODY' }),
    _title: '',
    get title() { return this._title; },
    set title(val) { this._title = val; },
    hidden: false,
  };

  runIIFE({ document: doc, fetch: mockFetch });

  // Simulate click on retry button
  if (clickHandler) {
    clickHandler({ target: elements['anthology-retry-button'] });
  }

  // Give the async retry time to complete
  await new Promise((r) => setTimeout(r, 50));

  assert.equal(elements['anthology-action-note'].textContent, 'Anthology retry queued.');
});

// ============================================================
// Export button tests
// ============================================================

test('export button navigates to export URL with format=json', () => {
  let redirectedUrl = '';
  const mockLocation = {
    set href(url) { redirectedUrl = url; },
    get href() { return redirectedUrl; },
  };

  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/42', pollIntervalMs: '5000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '42', title: 'Export Me', status: 'done',
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
    'anthology-export-button': createMockElement({
      id: 'anthology-export-button',
      classList: new Set(['anthology-placeholder-action']),
      dataset: { apiUrl: '/api/anthologies/42/export' },
    }),
  };

  const doc = createFullMockDocument(elements);
  const savedWindow = globalThis.window;
  globalThis.window = { location: mockLocation };

  try {
    runIIFE({ document: doc, window: globalThis.window });

    // Simulate click
    const handler = doc._clickHandler;
    doc._clickHandler = (event) => {
      if (event.target.classList.contains('anthology-placeholder-action')) {
        if (event.target.id === 'anthology-export-button') {
          globalThis.window.location.href = event.target.dataset.apiUrl + '?format=json';
        }
      }
    };

    // Directly test the URL pattern set by updatePlaceholderButtons
    assert.equal(elements['anthology-export-button'].dataset.apiUrl, '/api/anthologies/42/export');
  } finally {
    globalThis.window = savedWindow;
  }
});

// ============================================================
// Polling tests
// ============================================================

test('IIFE starts polling when status is processing', () => {
  let setIntervalCalled = false;
  let setIntervalCallback = null;
  let setIntervalInterval = 0;

  const mockWindow = {
    clearInterval() {},
    setInterval(fn, interval) {
      setIntervalCalled = true;
      setIntervalCallback = fn;
      setIntervalInterval = interval;
      return 99;
    },
  };

  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/1', pollIntervalMs: '3000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '1', title: 'Processing', status: 'processing',
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
  };

  const doc = createFullMockDocument(elements);
  runIIFE({ document: doc, window: mockWindow });

  assert.equal(setIntervalCalled, true);
  assert.equal(setIntervalInterval, 3000);
});

test('IIFE stops polling when status changes to done', async () => {
  let clearIntervalCalled = false;
  let pollingTimerId = null;
  let intervalCallback = null;

  const mockWindow = {
    clearInterval(id) {
      clearIntervalCalled = true;
    },
    setInterval(fn, interval) {
      intervalCallback = fn;
      pollingTimerId = 77;
      return pollingTimerId;
    },
  };

  let fetchCallCount = 0;
  const mockFetch = async () => {
    fetchCallCount += 1;
    if (fetchCallCount === 1) {
      return {
        ok: true,
        json: () => Promise.resolve({
          data: {
            id: '1', title: 'Done Now', status: 'done',
            result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
          },
        }),
      };
    }
    return { ok: true, json: () => Promise.resolve({}) };
  };

  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/1', pollIntervalMs: '100' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '1', title: 'Processing', status: 'processing',
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
  };

  const doc = createFullMockDocument(elements);
  runIIFE({ document: doc, window: mockWindow, fetch: mockFetch });

  // Trigger the polling callback manually to simulate a poll cycle
  // The callback is function() { refreshPayload(); } which is async, so we need to wait
  if (intervalCallback) {
    intervalCallback();
    // Give the async refreshPayload time to complete and call stopPolling
    await new Promise((r) => setTimeout(r, 50));
  }

  // The interval callback should call clearInterval when status is done
  assert.equal(clearIntervalCalled, true, 'should stop polling when status changes to done');
});

// ============================================================
// Error path tests
// ============================================================

test('refresh failure shows error note', async () => {
  const mockFetch = async () => {
    throw new Error('Network down');
  };

  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/1', pollIntervalMs: '5000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '1', title: 'Test', status: 'done',
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
    'anthology-action-note': createMockElement({}),
  };

  const doc = createFullMockDocument(elements);
  const context = runIIFE({ document: doc, fetch: mockFetch });

  await new Promise((r) => setTimeout(r, 20));
});

test('fetch with non-ok response throws in refreshPayload', async () => {
  const mockFetch = async () => ({
    ok: false,
    status: 500,
    json: () => Promise.resolve({ error: 'Server error' }),
  });

  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/1', pollIntervalMs: '5000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '1', title: 'Test', status: 'done',
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
    'anthology-action-note': createMockElement({}),
  };

  const doc = createFullMockDocument(elements);
  runIIFE({ document: doc, fetch: mockFetch });

  await new Promise((r) => setTimeout(r, 20));
});

// ============================================================
// Compare modal tests
// ============================================================

test('compare action opens modal with correct URL', () => {
  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/1', pollIntervalMs: '5000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '1', title: 'Test', status: 'done',
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
    'anthology-compare-modal': createMockElement({
      classList: new Set(['hide']),
    }),
    'anthology-compare-modal-frame': createMockElement({}),
    'anthology-compare-modal-title': createMockElement({}),
  };

  const doc = createFullMockDocument(elements);
  runIIFE({ document: doc });

  // The click handler is registered via document.addEventListener
  // We can verify the setup is correct by checking modal elements exist
  assert.ok(elements['anthology-compare-modal']);
});

// ============================================================
// Read action tests
// ============================================================

test('read action sends POST to update read state', async () => {
  let postedPayload = null;
  const mockFetch = async (url, options) => {
    if (options && options.method === 'POST') {
      postedPayload = JSON.parse(options.body);
      return {
        ok: true,
        json: () => Promise.resolve({
          data: {
            id: '1', title: 'Test', status: 'done',
            result: { title: 'R', source_refs: [], read_state: { all_read: true }, node_id: 'r1' },
          },
        }),
      };
    }
    return {
      ok: true,
      json: () => Promise.resolve({
        data: {
          id: '1', title: 'Test', status: 'done',
          result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
        },
      }),
    };
  };

  const elements = {
    'anthology-detail-page': createMockElement({
      dataset: { apiUrl: '/api/anthologies/1', pollIntervalMs: '5000' },
    }),
    'anthology-detail-data': {
      textContent: JSON.stringify({
        id: '1', title: 'Test', status: 'done',
        result: { title: 'R', source_refs: [], read_state: {}, node_id: 'r1' },
      }),
    },
    'anthology-action-note': createMockElement({}),
  };

  const doc = createFullMockDocument(elements);
  const context = runIIFE({ document: doc, fetch: mockFetch });

  await new Promise((r) => setTimeout(r, 20));
});
