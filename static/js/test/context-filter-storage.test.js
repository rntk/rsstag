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
    assert.equal(url, '/api/context-filter/item');
    assert.equal(options.method, 'POST');
    assert.equal(options.credentials, 'include');
    assert.equal(options.headers['Content-Type'], 'application/json');
    assert.equal(options.body, JSON.stringify({ type: 'tag', value: 'beta' }));

    return {
      async json() {
        return { data: 'ok', state: { active: true, filters: { tags: ['alpha', 'beta'] } } };
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


test('addFilter maps feed/category/topic/subtopic item types', async () => {
  const previousFetch = globalThis.fetch;
  const previousWindow = globalThis.window;
  const calls = [];
  const windowStub = createWindowStub();
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);

  globalThis.window = windowStub.stub;
  globalThis.fetch = async (_url, options) => {
    calls.push(JSON.parse(options.body));
    return {
      async json() {
        return { data: 'ok', state: { active: true, filters: {} } };
      },
    };
  };

  try {
    await storage.addFilter({ type: 'feeds', value: 'feed-1' });
    await storage.addFilter({ type: 'categories', value: 'cat-1' });
    await storage.addFilter({ type: 'topics', value: 'Technology > AI' });
    await storage.addFilter({ type: 'subtopics', value: 'Technology > AI > Agents' });

    assert.deepEqual(calls, [
      { type: 'feed', value: 'feed-1' },
      { type: 'category', value: 'cat-1' },
      { type: 'topic', value: 'Technology > AI' },
      { type: 'subtopic', value: 'Technology > AI > Agents' },
    ]);
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.window = previousWindow;
  }
});
