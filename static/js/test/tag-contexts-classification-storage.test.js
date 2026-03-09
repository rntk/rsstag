import test from 'node:test';
import assert from 'node:assert/strict';

import TagContextsClassificationStorage from '../storages/tag-contexts-classification-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, flushPromises } from './helpers.js';

function createTagContextsEventSystem() {
  return Object.assign(createEventSystem(), {
    TAGS_UPDATED: 'tags_updated',
    CHANGE_TAGS_LOAD_BUTTON_STATE: 'change_tags_load_button_state',
    START_TASK: 'start_task',
    END_TASK: 'end_task',
  });
}

test('constructor sets default state snapshot', () => {
  const storage = new TagContextsClassificationStorage(createTagContextsEventSystem());

  assert.deepEqual(storage.getState(), { tags: new Map() });
});

test('start() binds CHANGE_TAGS_LOAD_BUTTON_STATE', () => {
  const es = createTagContextsEventSystem();
  const storage = new TagContextsClassificationStorage(es);

  storage.start();

  assert.equal(es.bindings.has(es.CHANGE_TAGS_LOAD_BUTTON_STATE), true);
});

test('fetchContexts() success updates tags and emits payload shape', async (t) => {
  const es = createTagContextsEventSystem();
  const storage = new TagContextsClassificationStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async () => [{ tag: 'root', count: 2 }];
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchContexts('root');
  await flushPromises();

  const lastCall = es.calls.at(-1);
  assert.equal(lastCall.event, es.TAGS_UPDATED);
  assert.equal(lastCall.payload.tags.get('root').count, 2);
  assert.equal(es.calls.some((c) => c.event === es.START_TASK), true);
  assert.equal(es.calls.some((c) => c.event === es.END_TASK), true);
});

test('fetchContexts() failure path emits END_TASK after error', async (t) => {
  const es = createTagContextsEventSystem();
  const storage = new TagContextsClassificationStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;
  const originalConsoleError = console.error;

  rsstag_utils.fetchJSON = async () => {
    throw new Error('network');
  };
  console.error = () => {};

  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
    console.error = originalConsoleError;
  });

  storage.fetchContexts('root');
  await flushPromises();

  assert.equal(es.calls.at(-1).event, es.END_TASK);
});
