import test from 'node:test';
import assert from 'node:assert/strict';

import PathManager from '../components/path-manager.js';

function createElement(tagName) {
  return {
    tagName,
    children: [],
    className: '',
    textContent: '',
    disabled: false,
    type: '',
    _listeners: new Map(),
    appendChild(child) {
      this.children.push(child);
      return child;
    },
    addEventListener(eventName, handler) {
      this._listeners.set(eventName, handler);
    },
    dispatch(eventName) {
      const handler = this._listeners.get(eventName);
      if (handler) {
        handler();
      }
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

test('loadRecommendations() renders recommendation groups and click navigates via createPath', async () => {
  const originalDocument = globalThis.document;
  const originalWindow = globalThis.window;

  const container = createElement('aside');
  const createCalls = [];
  const storage = {
    async getPathRecommendations(pathId) {
      assert.equal(pathId, 'path-1');
      return {
        path_id: 'path-1',
        groups: [
          {
            id: 'tags_replace',
            title: 'Replace Tag',
            items: [
              {
                title: 'google + Google > Gemma',
                content_type: 'sentences',
                filterset: {
                  tags: { values: ['googl'], logic: 'and' },
                  topics: { values: ['Google > Gemma'], logic: 'and' },
                },
                exclude: {},
                source_value: 'google',
                suggested_value: 'googl',
                posts_count: 3,
                sentences_count: 7,
                score: 0.81,
              },
            ],
          },
        ],
      };
    },
    async createPath(contentType, filterset, exclude) {
      createCalls.push({ contentType, filterset, exclude });
      return { path_id: 'new-path' };
    },
  };

  globalThis.document = {
    createElement,
  };
  globalThis.window = {
    location: {
      href: '',
    },
  };

  try {
    const manager = new PathManager(storage);
    await manager.loadRecommendations('path-1', container);

    assert.equal(container.children.length, 2);
    const groupSection = container.children[1];
    const list = groupSection.children[1];
    const itemButton = list.children[0];

    assert.equal(itemButton.children[0].textContent, 'google + Google > Gemma');
    assert.equal(itemButton.children[1].textContent, '7 sentences · 3 posts · google -> googl · score 0.81');

    itemButton.dispatch('click');
    await Promise.resolve();

    assert.deepEqual(createCalls, [
      {
        contentType: 'sentences',
        filterset: {
          tags: { values: ['googl'], logic: 'and' },
          topics: { values: ['Google > Gemma'], logic: 'and' },
        },
        exclude: {},
      },
    ]);
    assert.equal(globalThis.window.location.href, '/paths/sentences/new-path');
  } finally {
    globalThis.document = originalDocument;
    globalThis.window = originalWindow;
  }
});

test('loadRecommendations() renders empty state when api returns no groups', async () => {
  const originalDocument = globalThis.document;
  const container = createElement('aside');
  globalThis.document = { createElement };

  try {
    const manager = new PathManager({
      async getPathRecommendations() {
        return { path_id: 'path-2', groups: [] };
      },
    });

    await manager.loadRecommendations('path-2', container);

    assert.equal(container.children[1].textContent, 'No suggestions for this path yet.');
  } finally {
    globalThis.document = originalDocument;
  }
});
