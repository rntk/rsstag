import test from 'node:test';
import assert from 'node:assert/strict';

import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem } from './helpers.js';

test('fetchJSON resolves JSON and emits task lifecycle events', async (t) => {
  const es = createEventSystem();
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;

  globalThis.window = { EVSYS: es };
  globalThis.fetch = async () => ({
    json: async () => ({ data: 'ok' }),
  });

  t.after(() => {
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  });

  const data = await rsstag_utils.fetchJSON('/api/example', { method: 'GET' });

  assert.deepEqual(data, { data: 'ok' });
  assert.deepEqual(es.calls, [
    { event: es.START_TASK, payload: 'ajax' },
    { event: es.END_TASK, payload: 'ajax' },
  ]);
});

test('waitFor resolves once the predicate becomes true', async () => {
  let ready = false;

  setTimeout(() => {
    ready = true;
  }, 10);

  await rsstag_utils.waitFor(() => ready, 200, 5);
  assert.equal(ready, true);
});

test('waitFor rejects after the timeout elapses', async () => {
  await assert.rejects(async () => {
    await rsstag_utils.waitFor(() => false, 30, 5);
  });
});
