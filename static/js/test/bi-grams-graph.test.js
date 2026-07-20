import test from 'node:test';
import assert from 'node:assert/strict';
import BiGramsGraph from '../components/bi-grams-graph.js';

// Mock window for rsstag_utils which accesses window.EVSYS
globalThis.window = {
  EVSYS: {
    trigger: () => {},
    START_TASK: 'start_task',
    END_TASK: 'end_task',
  },
  open: () => {},
};

// ============================================================
// Mock helpers
// ============================================================

function createMockContainer() {
  const children = [];
  return {
    selector: '#test-container',
    selectAll() {
      return this;
    },
    remove() {
      children.length = 0;
    },
    append() {
      const el = {
        style() {
          return this;
        },
        text() {
          return this;
        },
        html() {
          return this;
        },
        attr() {
          return this;
        },
        on() {
          return this;
        },
        append() {
          return this;
        },
        select() {
          return this;
        },
      };
      children.push(el);
      return el;
    },
    get childNodes() {
      return children;
    },
  };
}

function createMockEventSystem() {
  return {
    bindings: new Map(),
    calls: [],
    trigger(event, payload) {
      this.calls.push({ event, payload });
      const handlers = this.bindings.get(event) || [];
      handlers.forEach((h) => h(payload));
    },
    bind(event, handler) {
      const handlers = this.bindings.get(event) || [];
      handlers.push(handler);
      this.bindings.set(event, handlers);
    },
    unbind(event, handler) {
      const handlers = this.bindings.get(event) || [];
      this.bindings.set(
        event,
        handlers.filter((h) => h !== handler)
      );
    },
  };
}

// ============================================================
// Constructor tests
// ============================================================

test('BiGramsGraph constructor stores properties correctly', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#container', 'javascript', es);

  assert.equal(graph.containerSelector, '#container');
  assert.equal(graph.tag, 'javascript');
  assert.equal(graph.ES, es);
  assert.equal(graph.width, 900);
  assert.equal(graph.height, 700);
  assert.equal(graph.data, null);
  assert.equal(graph.meta, null);
  assert.equal(graph.svg, null);
  assert.equal(graph.simulation, null);
  assert.equal(graph.zoomGroup, null);
});

test('BiGramsGraph constructor accepts different tag types', () => {
  const es = createMockEventSystem();

  const g1 = new BiGramsGraph('#c1', 'my-tag', es);
  assert.equal(g1.tag, 'my-tag');

  const g2 = new BiGramsGraph('#c2', '', es);
  assert.equal(g2.tag, '');
});

// ============================================================
// normalizeGraphData tests
// ============================================================

test('normalizeGraphData with string node IDs', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
      { id: 'gamma', frequency: 3 },
    ],
    links: [
      { source: 'alpha', target: 'beta', weight: 4 },
      { source: 'alpha', target: 'gamma', weight: 2 },
    ],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.nodes.length, 3);
  assert.equal(result.links.length, 2);

  const nodeIds = result.nodes.map((n) => n.id);
  assert.ok(nodeIds.includes('alpha'));
  assert.ok(nodeIds.includes('beta'));
  assert.ok(nodeIds.includes('gamma'));

  const mainNode = result.nodes.find((n) => n.id === 'alpha');
  assert.equal(mainNode.type, 'main');
  assert.equal(mainNode.frequency, 10);

  const betaNode = result.nodes.find((n) => n.id === 'beta');
  assert.equal(betaNode.type, 'related');
  assert.equal(betaNode.frequency, 5);

  // Links should be star links from main
  assert.ok(result.links.every((l) => l.source === 'alpha'));
  const betaLink = result.links.find((l) => l.target === 'beta');
  assert.equal(betaLink.weight, 4);
  const gammaLink = result.links.find((l) => l.target === 'gamma');
  assert.equal(gammaLink.weight, 2);
});

test('normalizeGraphData with integer node IDs in links', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  // nodes: index 0 = 'alpha', index 1 = 'beta'
  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
    ],
    links: [{ source: 0, target: 1, weight: 3 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].source, 'alpha');
  assert.equal(result.links[0].target, 'beta');
  assert.equal(result.links[0].weight, 3);
});

test('normalizeGraphData with object node IDs in links', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 8 },
      { id: 'beta', frequency: 4 },
    ],
    links: [{ source: { id: 'alpha' }, target: { id: 'beta' }, weight: 2 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].source, 'alpha');
  assert.equal(result.links[0].target, 'beta');
});

test('normalizeGraphData resolves object IDs with .tag property', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 8 },
      { id: 'beta', frequency: 4 },
    ],
    links: [{ source: { tag: 'alpha' }, target: { tag: 'beta' }, weight: 1 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].source, 'alpha');
  assert.equal(result.links[0].target, 'beta');
});

test('normalizeGraphData resolves object IDs with .name property', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 8 },
      { id: 'beta', frequency: 4 },
    ],
    links: [{ source: { name: 'alpha' }, target: { name: 'beta' }, weight: 1 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].source, 'alpha');
  assert.equal(result.links[0].target, 'beta');
});

test('normalizeGraphData falls back to this.tag when meta.main_tag mismatches', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'beta', es);
  // meta says main_tag is 'alpha' but links use 'beta' as the hub
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'beta', frequency: 5 },
      { id: 'gamma', frequency: 3 },
    ],
    links: [{ source: 'beta', target: 'gamma', weight: 2 }],
  };

  const result = graph.normalizeGraphData(rawData);

  // Should fall back to 'beta' since no links connect to 'alpha'
  assert.equal(result.mainId, 'beta');
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].source, 'beta');
  assert.equal(result.links[0].target, 'gamma');
});

test('normalizeGraphData handles empty data', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const result = graph.normalizeGraphData(null);
  assert.equal(result.mainId, 'alpha');
  assert.equal(result.nodes.length, 1);
  assert.equal(result.links.length, 0);

  const result2 = graph.normalizeGraphData({});
  assert.equal(result2.mainId, 'alpha');
  assert.equal(result2.nodes.length, 1);
  assert.equal(result2.links.length, 0);

  const result3 = graph.normalizeGraphData({ nodes: [], links: [] });
  assert.equal(result3.mainId, 'alpha');
  assert.equal(result3.nodes.length, 1);
  assert.equal(result3.links.length, 0);
});

test('normalizeGraphData handles single node', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'solo', es);
  graph.meta = { main_tag: 'solo' };

  const rawData = {
    nodes: [{ id: 'solo', frequency: 42 }],
    links: [],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'solo');
  assert.equal(result.nodes.length, 1);
  assert.equal(result.nodes[0].id, 'solo');
  assert.equal(result.nodes[0].frequency, 42);
  assert.equal(result.nodes[0].type, 'main');
  assert.equal(result.links.length, 0);
});

test('normalizeGraphData handles circular links (self-loops dropped)', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
    ],
    links: [
      { source: 'alpha', target: 'alpha', weight: 3 },
      { source: 'alpha', target: 'beta', weight: 4 },
    ],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  // Self-loop to main should be dropped (both source and target are mainId)
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].target, 'beta');
});

test('normalizeGraphData handles links with both directions to main', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
    ],
    links: [
      { source: 'alpha', target: 'beta', weight: 3 },
      { source: 'beta', target: 'alpha', weight: 2 },
    ],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  // Should only have one link to beta
  const betaLink = result.links.find((l) => l.target === 'beta');
  assert.ok(betaLink !== undefined);
  assert.equal(result.links.length, 1);
});

test('normalizeGraphData aggregates link weights', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
    ],
    links: [
      { source: 'alpha', target: 'beta', weight: 3 },
      { source: 'alpha', target: 'beta', weight: 7 },
    ],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  // Weights should be aggregated: 3 + 7 = 10
  assert.equal(result.links[0].weight, 10);
});

test('normalizeGraphData maps frequency from node data', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 20 },
      { id: 'beta', freq: 8 },
      { id: 'gamma', count: 3 },
    ],
    links: [
      { source: 'alpha', target: 'beta', weight: 2 },
      { source: 'alpha', target: 'gamma', weight: 1 },
    ],
  };

  const result = graph.normalizeGraphData(rawData);

  const alphaNode = result.nodes.find((n) => n.id === 'alpha');
  assert.equal(alphaNode.frequency, 20);

  const betaNode = result.nodes.find((n) => n.id === 'beta');
  assert.equal(betaNode.frequency, 8);

  const gammaNode = result.nodes.find((n) => n.id === 'gamma');
  assert.equal(gammaNode.frequency, 3);
});

test('normalizeGraphData uses bigram_frequency on related nodes', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 20 },
      { id: 'beta', frequency: 5, bigram_frequency: 3 },
    ],
    links: [{ source: 'alpha', target: 'beta', weight: 3 }],
  };

  const result = graph.normalizeGraphData(rawData);

  const betaNode = result.nodes.find((n) => n.id === 'beta');
  assert.equal(betaNode.bigram_frequency, 3);
});

test('normalizeGraphData handles nodes as plain strings', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: ['alpha', 'beta', 'gamma'],
    links: [{ source: 'alpha', target: 'beta', weight: 2 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].source, 'alpha');
  assert.equal(result.links[0].target, 'beta');
});

test('normalizeGraphData handles links with alternative property names', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
    ],
    links: [{ from: 'alpha', to: 'beta', posts_count: 4 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].weight, 4);
});

test('normalizeGraphData handles links with src/dst property names', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
    ],
    links: [{ src: 'alpha', dst: 'beta', value: 6 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].weight, 6);
});

test('normalizeGraphData uses edges as fallback for links', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
    ],
    edges: [{ source: 'alpha', target: 'beta', weight: 2 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].source, 'alpha');
  assert.equal(result.links[0].target, 'beta');
});

test('normalizeGraphData ensures main node exists even without explicit node entry', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha', main_tag_frequency: 15 };

  const rawData = {
    nodes: [{ id: 'beta', frequency: 5 }],
    links: [{ source: 'alpha', target: 'beta', weight: 3 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  const mainNode = result.nodes.find((n) => n.id === 'alpha');
  assert.ok(mainNode !== undefined);
  assert.equal(mainNode.type, 'main');
  // Frequency from meta.main_tag_frequency
  assert.equal(mainNode.frequency, 15);
});

test('normalizeGraphData defaults main node frequency to 1 when no meta frequency', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [{ id: 'beta', frequency: 5 }],
    links: [{ source: 'alpha', target: 'beta', weight: 3 }],
  };

  const result = graph.normalizeGraphData(rawData);

  const mainNode = result.nodes.find((n) => n.id === 'alpha');
  assert.equal(mainNode.frequency, 1);
});

test('normalizeGraphData drops links with zero or negative weight', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
      { id: 'gamma', frequency: 3 },
    ],
    links: [
      { source: 'alpha', target: 'beta', weight: 0 },
      { source: 'alpha', target: 'gamma', weight: -1 },
      { source: 'alpha', target: 'beta', weight: 2 },
    ],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.links.length, 1);
  assert.equal(result.links[0].target, 'beta');
  assert.equal(result.links[0].weight, 2);
});

test('normalizeGraphData handles null/undefined link entries', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { id: 'beta', frequency: 5 },
    ],
    links: [null, undefined, { source: 'alpha', target: 'beta', weight: 1 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.links.length, 1);
});

test('normalizeGraphData handles unresolved node index gracefully', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  // Link references index 99 which does not exist
  const rawData = {
    nodes: [{ id: 'alpha', frequency: 10 }],
    links: [{ source: 99, target: 'alpha', weight: 2 }],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  // Index 99 resolves to null, so link should be dropped
  assert.equal(result.links.length, 0);
});

test('normalizeGraphData handles node object without id (skipped in nodeDataById)', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  const rawData = {
    nodes: [
      { id: 'alpha', frequency: 10 },
      { frequency: 5 }, // no id - should be skipped
      { id: '', frequency: 3 }, // empty id - should be skipped
    ],
    links: [],
  };

  const result = graph.normalizeGraphData(rawData);

  assert.equal(result.mainId, 'alpha');
  assert.equal(result.nodes.length, 1); // only alpha
});

// ============================================================
// getNodeRadius tests
// ============================================================

test('getNodeRadius uses nodeRadiusScale when available', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  // Mock a scale function
  graph.nodeRadiusScale = (freq) => Math.sqrt(freq) * 5 + 10;

  const radius = graph.getNodeRadius({ frequency: 16 });
  assert.equal(radius, Math.sqrt(16) * 5 + 10); // sqrt(16)*5+10 = 30
});

test('getNodeRadius uses fallback calculation without scale', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);

  const radius1 = graph.getNodeRadius({ frequency: 1 });
  assert.ok(radius1 >= 8 && radius1 <= 60);

  const radius2 = graph.getNodeRadius({ frequency: 100 });
  assert.ok(radius2 > radius1, 'higher frequency should yield larger radius');

  const radius3 = graph.getNodeRadius({ frequency: 1000 });
  assert.ok(radius3 > radius2, 'even higher frequency should yield even larger radius');
});

test('getNodeRadius returns default for missing frequency', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);

  assert.equal(graph.getNodeRadius({}), 12);
  assert.equal(graph.getNodeRadius(null), 12);
  assert.equal(graph.getNodeRadius(undefined), 12);
});

test('getNodeRadius respects min/max bounds in fallback', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);

  // Very small frequency should clamp to minSize (8)
  const minR = graph.getNodeRadius({ frequency: 0 });
  assert.ok(minR >= 8, `min radius ${minR} should be >= 8`);

  // Very large frequency should clamp to maxSize (60)
  const maxR = graph.getNodeRadius({ frequency: 1e9 });
  assert.ok(maxR <= 60, `max radius ${maxR} should be <= 60`);
});

// ============================================================
// fetchData tests
// ============================================================

test('fetchData calls fetch and processes response with data', async () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);

  const mockResponse = {
    data: {
      nodes: [{ id: 'alpha', frequency: 10 }],
      links: [],
    },
    meta: { main_tag: 'alpha' },
  };

  // Stub globalThis.fetch
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => mockResponse,
  });

  // Stub renderGraph and renderError to avoid D3
  let renderGraphCalled = false;
  graph.renderGraph = () => {
    renderGraphCalled = true;
  };
  graph.renderError = () => {
    throw new Error('renderError called unexpectedly');
  };
  graph.showLoading = () => {};

  graph.fetchData();
  // fetchData uses promises, so wait a tick
  await new Promise((r) => setTimeout(r, 10));

  assert.equal(renderGraphCalled, true);
  assert.deepEqual(graph.data, mockResponse.data);
  assert.deepEqual(graph.meta, mockResponse.meta);

  globalThis.fetch = originalFetch;
});

test('fetchData handles response without data', async () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({}),
  });

  let renderErrorCalled = false;
  let renderGraphCalled = false;
  graph.renderGraph = () => {
    renderGraphCalled = true;
  };
  graph.renderError = (msg) => {
    renderErrorCalled = true;
  };
  graph.showLoading = () => {};

  graph.fetchData();
  await new Promise((r) => setTimeout(r, 10));

  assert.equal(renderGraphCalled, false);
  assert.equal(renderErrorCalled, true);

  globalThis.fetch = originalFetch;
});

test('fetchData handles fetch error', async () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new Error('Network error');
  };

  let renderErrorCalled = false;
  graph.renderError = (msg) => {
    renderErrorCalled = true;
  };
  graph.showLoading = () => {};

  graph.fetchData();
  await new Promise((r) => setTimeout(r, 10));

  assert.equal(renderErrorCalled, true);

  globalThis.fetch = originalFetch;
});

test('fetchData encodes tag in URL', async () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'my tag/with specials', es);

  let fetchUrl = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    fetchUrl = url;
    return { ok: true, json: async () => ({ data: { nodes: [], links: [] } }) };
  };

  graph.renderGraph = () => {};
  graph.renderError = () => {};
  graph.showLoading = () => {};

  graph.fetchData();
  await new Promise((r) => setTimeout(r, 10));

  assert.ok(fetchUrl !== null);
  assert.ok(fetchUrl.includes('my%20tag'));
  assert.ok(fetchUrl.includes('specials'));

  globalThis.fetch = originalFetch;
});

// ============================================================
// handleNodeClick tests
// ============================================================

test('handleNodeClick opens entity page for main tag', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  let openedUrl = null;
  globalThis.window.open = (url) => {
    openedUrl = url;
  };

  graph.handleNodeClick('alpha');
  assert.ok(openedUrl.includes('/entity/'));
  assert.ok(openedUrl.includes('alpha'));
});

test('handleNodeClick opens bi-gram page for related tag', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);
  graph.meta = { main_tag: 'alpha' };

  let openedUrl = null;
  globalThis.window.open = (url) => {
    openedUrl = url;
  };

  graph.handleNodeClick('beta');
  assert.ok(openedUrl.includes('/bi-gram/'));
  assert.ok(openedUrl.includes('alpha'));
  assert.ok(openedUrl.includes('beta'));
});

test('handleNodeClick uses this.tag as main when meta.main_tag is absent', () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'mytag', es);
  graph.meta = null;

  let openedUrl = null;
  globalThis.window.open = (url) => {
    openedUrl = url;
  };

  graph.handleNodeClick('other');
  assert.ok(openedUrl.includes('mytag'));
  assert.ok(openedUrl.includes('other'));
});

// ============================================================
// start method tests
// ============================================================

test('start calls fetchData', async () => {
  const es = createMockEventSystem();
  const graph = new BiGramsGraph('#c', 'alpha', es);

  let fetchDataCalled = false;
  graph.fetchData = () => {
    fetchDataCalled = true;
  };

  graph.start();
  assert.equal(fetchDataCalled, true);
});
