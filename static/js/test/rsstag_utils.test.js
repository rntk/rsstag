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

test('fetchJSON rejects and emits END_TASK when response.json() fails', async (t) => {
  const es = createEventSystem();
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;

  globalThis.window = { EVSYS: es };
  globalThis.fetch = async () => ({
    json: async () => {
      throw new SyntaxError('Unexpected token');
    },
  });

  t.after(() => {
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  });

  await assert.rejects(async () => {
    await rsstag_utils.fetchJSON('/api/bad-json', { method: 'GET' });
  }, SyntaxError);

  assert.deepEqual(es.calls, [
    { event: es.START_TASK, payload: 'ajax' },
    { event: es.END_TASK, payload: 'ajax' },
  ]);
});

test('fetchJSON rejects and emits END_TASK when fetch network fails', async (t) => {
  const es = createEventSystem();
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;

  globalThis.window = { EVSYS: es };
  globalThis.fetch = async () => {
    throw new TypeError('NetworkError');
  };

  t.after(() => {
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  });

  await assert.rejects(async () => {
    await rsstag_utils.fetchJSON('/api/offline', { method: 'GET' });
  }, TypeError);

  assert.deepEqual(es.calls, [
    { event: es.START_TASK, payload: 'ajax' },
    { event: es.END_TASK, payload: 'ajax' },
  ]);
});

test('randInt returns a number between min and max', () => {
  const result = rsstag_utils.randInt(10, 20);
  assert.equal(typeof result, 'number');
  assert.ok(result >= 10 && result < 20);
});
