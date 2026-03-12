import test from 'node:test';
import assert from 'node:assert/strict';

import PathStorage from '../storages/path-storage.js';
import { createEventSystem } from './helpers.js';

test('getPathRecommendations() returns payload data on success', async () => {
  const storage = new PathStorage(createEventSystem());
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
  const storage = new PathStorage(createEventSystem());
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
