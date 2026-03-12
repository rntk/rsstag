import assert from 'node:assert/strict';
import test from 'node:test';

import TagTopicsRadar from '../components/tag-topics-radar.js';

function createElement(tagName) {
  return {
    tagName,
    children: [],
    className: '',
    textContent: '',
    title: '',
    href: '',
    style: {
      cssText: '',
    },
    _listeners: new Map(),
    appendChild(child) {
      this.children.push(child);
      return child;
    },
    addEventListener(eventName, handler) {
      this._listeners.set(eventName, handler);
    },
    dispatch(eventName, event = {}) {
      const handler = this._listeners.get(eventName);
      if (handler) {
        handler(event);
      }
    },
    getContext() {
      return {};
    },
    set innerHTML(value) {
      this._innerHTML = value;
      this.children = [];
    },
    get innerHTML() {
      return this._innerHTML || '';
    },
  };
}

test('renders topic links and creates a sentences path for tag + topic clicks', async () => {
  const originalDocument = globalThis.document;
  const originalChart = globalThis.Chart;
  const originalWindow = globalThis.window;

  const container = createElement('div');
  const chartConfigs = [];
  const pathCalls = [];

  globalThis.document = {
    querySelector(selector) {
      assert.equal(selector, '#radar');
      return container;
    },
    createElement(tagName) {
      return createElement(tagName);
    },
  };

  globalThis.Chart = class ChartStub {
    constructor(_ctx, config) {
      chartConfigs.push(config);
    }

    destroy() {}
  };

  globalThis.window = {
    initial_tag: { tag: 'python' },
    pathManager: {
      async createAndNavigate(contentType, filterset) {
        pathCalls.push({ contentType, filterset });
        return { path_id: 'abc123' };
      },
    },
    location: {
      href: '',
    },
  };

  try {
    const radar = new TagTopicsRadar('#radar', { bind() {} });
    radar.renderChart(2, ['AI > NLP'], [4], [200], [
      {
        label: 'AI > NLP',
        count: 4,
        totalLength: 200,
        postIds: ['1'],
        level: 2,
        snippetsUrl: '/fallback',
        compareUrl: '/compare',
        filter: 'AI > NLP',
      },
    ]);

    assert.equal(container.children.length, 3);
    const linksList = container.children[2];
    assert.equal(linksList.className, 'tag-topics-radar-links');
    assert.equal(linksList.children.length, 1);

    const linkItem = linksList.children[0];
    const link = linkItem.children[0];
    const meta = linkItem.children[1];

    assert.equal(link.textContent, 'AI > NLP');
    assert.equal(link.href, '/fallback');
    assert.equal(meta.textContent, '4 posts · 200 chars · 1 articles');

    let prevented = false;
    link.dispatch('click', {
      preventDefault() {
        prevented = true;
      },
    });

    await Promise.resolve();

    assert.equal(prevented, true);
    assert.deepEqual(pathCalls, [
      {
        contentType: 'sentences',
        filterset: {
          tags: { values: ['python'], logic: 'and' },
          topics: { values: ['AI > NLP'], logic: 'and' },
        },
      },
    ]);

    assert.equal(typeof chartConfigs[0].options.onClick, 'function');
  } finally {
    globalThis.document = originalDocument;
    globalThis.Chart = originalChart;
    globalThis.window = originalWindow;
  }
});
