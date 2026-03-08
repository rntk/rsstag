import assert from 'node:assert/strict';
import test from 'node:test';

import ContextFilterStorage from '../storages/context-filter-storage.js';

class FakeEventSystem {
  constructor() {
    this.CONTEXT_FILTER_UPDATED = 'context_filter_updated';
    this.CONTEXT_FILTER_ADD = 'context_filter_add';
    this.CONTEXT_FILTER_REMOVE = 'context_filter_remove';
    this.CONTEXT_FILTER_CLEAR = 'context_filter_clear';
    this.boundHandlers = new Map();
    this.triggered = [];
  }

  bind(eventName, handler) {
    this.boundHandlers.set(eventName, handler);
  }

  trigger(eventName, payload) {
    this.triggered.push([eventName, payload]);
  }
}

function createWindowStub() {
  let reloadCount = 0;

  return {
    stub: {
      location: {
        reload() {
          reloadCount += 1;
        },
      },
    },
    getReloadCount() {
      return reloadCount;
    },
  };
}

test('fetchFilter stores API state and emits update', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/context-filter');
    assert.deepEqual(options, { credentials: 'include' });

    return {
      async json() {
        return { data: { active: true, filters: { tags: ['alpha', 'beta'], feeds: [] } } };
      },
    };
  };

  try {
    await storage.fetchFilter();

    assert.deepEqual(storage.getState(), {
      active: true,
      filters: {
        tags: ['alpha', 'beta'],
        feeds: [],
        categories: [],
        topics: [],
        subtopics: [],
      },
    });
    assert.deepEqual(eventSystem.triggered, [
      [
        'context_filter_updated',
        {
          active: true,
          filters: {
            tags: ['alpha', 'beta'],
            feeds: [],
            categories: [],
            topics: [],
            subtopics: [],
          },
        },
      ],
    ]);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('addFilter posts JSON, updates state, and reloads the page', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  const previousWindow = globalThis.window;
  const windowStub = createWindowStub();

  globalThis.window = windowStub.stub;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/context-filter/tag');
    assert.equal(options.method, 'POST');
    assert.equal(options.credentials, 'include');
    assert.equal(options.headers['Content-Type'], 'application/json');
    assert.equal(options.body, JSON.stringify({ tag: 'beta' }));

    return {
      async json() {
        return { data: 'ok', filters: { tags: ['alpha', 'beta'] } };
      },
    };
  };

  try {
    await storage.addFilter({ type: 'tags', value: 'beta' });

    assert.deepEqual(storage.getState(), {
      active: true,
      filters: {
        tags: ['alpha', 'beta'],
        feeds: [],
        categories: [],
        topics: [],
        subtopics: [],
      },
    });
    assert.equal(windowStub.getReloadCount(), 1);
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.window = previousWindow;
  }
});

test('start binds event handlers and kicks off the initial fetch', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const originalFetchFilter = storage.fetchFilter;
  let fetchFilterCalls = 0;

  storage.fetchFilter = async () => {
    fetchFilterCalls += 1;
  };

  try {
    storage.start();

    assert.equal(typeof eventSystem.boundHandlers.get('context_filter_add'), 'function');
    assert.equal(typeof eventSystem.boundHandlers.get('context_filter_remove'), 'function');
    assert.equal(typeof eventSystem.boundHandlers.get('context_filter_clear'), 'function');
    assert.equal(fetchFilterCalls, 1);
  } finally {
    storage.fetchFilter = originalFetchFilter;
  }
});
