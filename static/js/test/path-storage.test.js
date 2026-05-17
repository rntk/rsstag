import test from 'node:test';
import assert from 'node:assert/strict';

import PathStorage from '../storages/path-storage.js';
import { createEventSystem } from './helpers.js';

function createPathEventSystem() {
  const es = createEventSystem();
  es.PATH_CREATED = 'path_created';
  es.PATH_DELETED = 'path_deleted';
  es.PATHS_UPDATED = 'paths_updated';
  return es;
}

test('createPath() posts payload and returns doc on success', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const docs = [];

  global.fetch = async (url, options) => {
    assert.equal(url, '/api/paths');
    assert.equal(options.method, 'POST');
    return {
      async json() {
        return { data: { id: 'new-path', content_type: 'posts' } };
      },
    };
  };

  es.bind(es.PATH_CREATED, (doc) => docs.push(doc));

  try {
    const result = await storage.createPath('posts', { tag: 'test' });
    assert.deepEqual(result, { id: 'new-path', content_type: 'posts' });
    assert.equal(docs.length, 1);
  } finally {
    global.fetch = originalFetch;
  }
});

test('createPath() returns null and logs error when API returns error', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const originalError = console.error;
  console.error = () => {};

  global.fetch = async () => ({
    async json() {
      return { error: 'validation failed' };
    },
  });

  try {
    const result = await storage.createPath('posts', {});
    assert.equal(result, null);
  } finally {
    global.fetch = originalFetch;
    console.error = originalError;
  }
});

test('createPath() returns null on network error', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const originalError = console.error;
  console.error = () => {};

  global.fetch = async () => {
    throw new TypeError('network error');
  };

  try {
    const result = await storage.createPath('posts', {}, { reason: 'test' });
    assert.equal(result, null);
  } finally {
    global.fetch = originalFetch;
    console.error = originalError;
  }
});

test('listPaths() returns array and emits PATHS_UPDATED', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const updates = [];

  global.fetch = async (url) => {
    assert.equal(url, '/api/paths');
    return {
      async json() {
        return { data: [{ id: 'p1' }, { id: 'p2' }] };
      },
    };
  };

  es.bind(es.PATHS_UPDATED, (paths) => updates.push(paths));

  try {
    const result = await storage.listPaths();
    assert.equal(result.length, 2);
    assert.equal(updates.length, 1);
  } finally {
    global.fetch = originalFetch;
  }
});

test('listPaths() returns empty array on network error', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const originalError = console.error;
  console.error = () => {};

  global.fetch = async () => {
    throw new Error('offline');
  };

  try {
    const result = await storage.listPaths();
    assert.deepEqual(result, []);
  } finally {
    global.fetch = originalFetch;
    console.error = originalError;
  }
});

test('deletePath() sends DELETE and returns true on success', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const deleted = [];

  global.fetch = async (url, options) => {
    assert.equal(url, '/api/paths/path-42');
    assert.equal(options.method, 'DELETE');
    return {
      async json() {
        return { data: true };
      },
    };
  };

  es.bind(es.PATH_DELETED, (id) => deleted.push(id));

  try {
    const result = await storage.deletePath('path-42');
    assert.equal(result, true);
    assert.deepEqual(deleted, ['path-42']);
  } finally {
    global.fetch = originalFetch;
  }
});

test('deletePath() returns false when API returns error', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const originalError = console.error;
  console.error = () => {};

  global.fetch = async () => ({
    async json() {
      return { error: 'not found' };
    },
  });

  try {
    const result = await storage.deletePath('missing');
    assert.equal(result, false);
  } finally {
    global.fetch = originalFetch;
    console.error = originalError;
  }
});

test('deletePath() returns false on network error', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const originalError = console.error;
  console.error = () => {};

  global.fetch = async () => {
    throw new Error('network');
  };

  try {
    const result = await storage.deletePath('any');
    assert.equal(result, false);
  } finally {
    global.fetch = originalFetch;
    console.error = originalError;
  }
});

test('getPathRecommendations() returns payload data on success', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;

  global.fetch = async (url) => {
    assert.equal(url, '/api/paths/path-1/recommendations');
    return {
      ok: true,
      async json() {
        return {
          data: {
            path_id: 'path-1',
            groups: [{ id: 'tags_replace', items: [] }],
          },
        };
      },
    };
  };

  try {
    const payload = await storage.getPathRecommendations('path-1');
    assert.deepEqual(payload, {
      path_id: 'path-1',
      groups: [{ id: 'tags_replace', items: [] }],
    });
  } finally {
    global.fetch = originalFetch;
  }
});

test('getPathRecommendations() returns null on api error', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;

  global.fetch = async () => ({
    ok: false,
    statusText: 'bad',
    async json() {
      return { error: 'boom' };
    },
  });

  try {
    const payload = await storage.getPathRecommendations('path-2');
    assert.equal(payload, null);
  } finally {
    global.fetch = originalFetch;
  }
});

test('getPathClusterRecommendations() returns payload data on success', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;

  global.fetch = async (url) => {
    assert.equal(url, '/api/paths/path-1/cluster-recommendations');
    return {
      ok: true,
      async json() {
        return {
          data: {
            path_id: 'path-1',
            clusters: [{ id: 'c1', tags: ['a', 'b'] }],
          },
        };
      },
    };
  };

  try {
    const payload = await storage.getPathClusterRecommendations('path-1');
    assert.deepEqual(payload, {
      path_id: 'path-1',
      clusters: [{ id: 'c1', tags: ['a', 'b'] }],
    });
  } finally {
    global.fetch = originalFetch;
  }
});

test('getPathClusterRecommendations() returns null on api error', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;

  global.fetch = async () => ({
    ok: false,
    statusText: 'bad',
    async json() {
      return { error: 'boom' };
    },
  });

  try {
    const payload = await storage.getPathClusterRecommendations('path-2');
    assert.equal(payload, null);
  } finally {
    global.fetch = originalFetch;
  }
});

test('getPathClusterRecommendations() returns null on network error', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const originalError = console.error;
  console.error = () => {};

  global.fetch = async () => {
    throw new Error('offline');
  };

  try {
    const payload = await storage.getPathClusterRecommendations('path-3');
    assert.equal(payload, null);
  } finally {
    global.fetch = originalFetch;
    console.error = originalError;
  }
});

test('getPathRecommendations() returns null on network error', async () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);
  const originalFetch = global.fetch;
  const originalError = console.error;
  console.error = () => {};

  global.fetch = async () => {
    throw new Error('offline');
  };

  try {
    const payload = await storage.getPathRecommendations('path-3');
    assert.equal(payload, null);
  } finally {
    global.fetch = originalFetch;
    console.error = originalError;
  }
});

test('start() is a no-op', () => {
  const es = createPathEventSystem();
  const storage = new PathStorage(es);

  storage.start();
});
