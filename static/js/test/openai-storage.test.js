import test from 'node:test';
import assert from 'node:assert/strict';

import OpenAIStorage from '../storages/openai-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, flushPromises } from './helpers.js';

function createOpenAIEventSystem() {
  return Object.assign(createEventSystem(), {
    OPENAI_GET_RESPONSE: 'openai_get_response',
    OPENAI_GOT_RESPONSE: 'openai_got_response',
  });
}

test('constructor sets default state snapshot', () => {
  const storage = new OpenAIStorage('python', createOpenAIEventSystem());

  assert.deepEqual(storage.getState(), {
    user: '',
    response: '',
    tag: 'python',
  });
});

test('start() binds OPENAI_GET_RESPONSE handler', () => {
  const es = createOpenAIEventSystem();
  const storage = new OpenAIStorage('python', es);

  storage.start();

  assert.equal(es.bindings.has(es.OPENAI_GET_RESPONSE), true);
});

test('getResponse() success updates state and emits payload shape', async (t) => {
  const es = createOpenAIEventSystem();
  const storage = new OpenAIStorage('python', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async () => ({ data: 'answer' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.getResponse({ user: 'alice' });
  await flushPromises();

  const lastCall = es.calls.at(-1);
  assert.equal(lastCall.event, es.OPENAI_GOT_RESPONSE);
  assert.deepEqual(lastCall.payload, {
    user: 'alice',
    response: 'answer',
    tag: 'python',
  });
});

test('getResponse() failure path calls errorMessage and stores error response', async (t) => {
  const es = createOpenAIEventSystem();
  const storage = new OpenAIStorage('python', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  let errorText = null;
  storage.errorMessage = (msg) => {
    errorText = msg;
  };

  rsstag_utils.fetchJSON = async () => ({ error: 'api down' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.getResponse({ user: 'alice' });
  await flushPromises();

  assert.equal(errorText, 'Error. Try later');
  assert.equal(storage.getState().response, 'api down');
});
