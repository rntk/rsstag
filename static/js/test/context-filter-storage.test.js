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

test('fetchFilter network error is caught without throwing', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  const originalConsoleError = console.error;

  globalThis.fetch = async () => {
    throw new Error('network down');
  };
  console.error = () => {};

  try {
    await storage.fetchFilter();
    // Should not throw
  } finally {
    globalThis.fetch = previousFetch;
    console.error = originalConsoleError;
  }
});

test('fetchFilter with response missing data key does not mutate state', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;

  globalThis.fetch = async () => ({
    async json() {
      return { error: 'no filter' };
    },
  });

  try {
    const beforeState = storage.getState();
    await storage.fetchFilter();
    const afterState = storage.getState();

    // State unchanged (normalizeState produces default for no data)
    assert.deepEqual(beforeState, afterState);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('addFilter with missing type is a no-op', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  let fetchCalled = false;

  globalThis.fetch = async () => {
    fetchCalled = true;
    return { async json() { return { data: 'ok' }; } };
  };

  try {
    await storage.addFilter({ value: 'some-value' });
    assert.equal(fetchCalled, false);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('addFilter with missing value is a no-op', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  let fetchCalled = false;

  globalThis.fetch = async () => {
    fetchCalled = true;
    return { async json() { return { data: 'ok' }; } };
  };

  try {
    await storage.addFilter({ type: 'tags' });
    assert.equal(fetchCalled, false);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('addFilter with null argument is a no-op', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  let fetchCalled = false;

  globalThis.fetch = async () => {
    fetchCalled = true;
    return { async json() { return { data: 'ok' }; } };
  };

  try {
    await storage.addFilter(null);
    assert.equal(fetchCalled, false);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('addFilter API error response does not update state or reload', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  const previousWindow = globalThis.window;
  const windowStub = createWindowStub();

  globalThis.window = windowStub.stub;
  globalThis.fetch = async () => ({
    async json() {
      return { error: 'duplicate filter' };
    },
  });

  try {
    await storage.addFilter({ type: 'tags', value: 'duplicate' });
    assert.equal(windowStub.getReloadCount(), 0);
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.window = previousWindow;
  }
});

test('addFilter network error is caught without throwing', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  const previousWindow = globalThis.window;
  const originalConsoleError = console.error;

  globalThis.window = { location: { reload() {} } };
  globalThis.fetch = async () => {
    throw new Error('timeout');
  };
  console.error = () => {};

  try {
    await storage.addFilter({ type: 'tags', value: 'beta' });
    // Should not throw
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.window = previousWindow;
    console.error = originalConsoleError;
  }
});

test('removeFilter success updates state and reloads', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  const previousWindow = globalThis.window;
  const windowStub = createWindowStub();

  globalThis.window = windowStub.stub;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/context-filter/item');
    assert.equal(options.method, 'DELETE');
    assert.equal(options.body, JSON.stringify({ type: 'tag', value: 'beta' }));

    return {
      async json() {
        return { data: 'ok', state: { active: false, filters: { tags: ['alpha'] } } };
      },
    };
  };

  try {
    await storage.removeFilter({ type: 'tags', value: 'beta' });

    assert.deepEqual(storage.getState(), {
      active: false,
      filters: {
        tags: ['alpha'],
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

test('removeFilter with missing type is a no-op', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  let fetchCalled = false;

  globalThis.fetch = async () => {
    fetchCalled = true;
    return { async json() { return { data: 'ok' }; } };
  };

  try {
    await storage.removeFilter({ value: 'some-value' });
    assert.equal(fetchCalled, false);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('removeFilter API error returns without updating state', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  const previousWindow = globalThis.window;
  const windowStub = createWindowStub();
  const originalConsoleError = console.error;

  globalThis.window = windowStub.stub;
  globalThis.fetch = async () => ({
    async json() {
      return { error: 'not found' };
    },
  });
  console.error = () => {};

  try {
    await storage.removeFilter({ type: 'tags', value: 'nonexistent' });
    assert.equal(windowStub.getReloadCount(), 0);
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.window = previousWindow;
    console.error = originalConsoleError;
  }
});

test('removeFilter network error is caught without throwing', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  const previousWindow = globalThis.window;
  const originalConsoleError = console.error;

  globalThis.window = { location: { reload() {} } };
  globalThis.fetch = async () => {
    throw new Error('connection reset');
  };
  console.error = () => {};

  try {
    await storage.removeFilter({ type: 'tags', value: 'alpha' });
    // Should not throw
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.window = previousWindow;
    console.error = originalConsoleError;
  }
});

test('clearFilter success reloads the page', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  const previousWindow = globalThis.window;
  const windowStub = createWindowStub();

  globalThis.window = windowStub.stub;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/context-filter/clear');
    assert.equal(options.method, 'POST');

    return {
      async json() {
        return { data: 'ok', active: false, filters: { tags: [], feeds: [] } };
      },
    };
  };

  try {
    await storage.clearFilter();
    assert.equal(windowStub.getReloadCount(), 1);
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.window = previousWindow;
  }
});

test('clearFilter network error is caught without throwing', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);
  const previousFetch = globalThis.fetch;
  const originalConsoleError = console.error;

  globalThis.fetch = async () => {
    throw new Error('server error');
  };
  console.error = () => {};

  try {
    await storage.clearFilter();
    // Should not throw
  } finally {
    globalThis.fetch = previousFetch;
    console.error = originalConsoleError;
  }
});

test('setState normalizes filters - strips non-string and empty values', () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);

  storage.setState({
    active: true,
    filters: {
      tags: ['alpha', 42, '', '  ', 'beta'],
      feeds: [null, undefined, 'feed-1'],
      categories: [],
    },
  });

  const state = storage.getState();
  assert.deepEqual(state.filters.tags, ['alpha', 'beta']);
  assert.deepEqual(state.filters.feeds, ['feed-1']);
  assert.deepEqual(state.filters.categories, []);
  assert.deepEqual(state.filters.topics, []);
  assert.deepEqual(state.filters.subtopics, []);
});

test('bindEvents wires add/remove/clear to the storage methods', async () => {
  const eventSystem = new FakeEventSystem();
  const storage = new ContextFilterStorage(eventSystem);

  let addArg = null;
  let removeArg = null;
  let clearCalls = 0;

  storage.addFilter = async (f) => { addArg = f; };
  storage.removeFilter = async (f) => { removeArg = f; };
  storage.clearFilter = async () => { clearCalls += 1; };

  storage.bindEvents();

  eventSystem.boundHandlers.get('context_filter_add')({ type: 'tags', value: 'x' });
  eventSystem.boundHandlers.get('context_filter_remove')({ type: 'feeds', value: 'y' });
  eventSystem.boundHandlers.get('context_filter_clear')();

  assert.deepEqual(addArg, { type: 'tags', value: 'x' });
  assert.deepEqual(removeArg, { type: 'feeds', value: 'y' });
  assert.equal(clearCalls, 1);
});
