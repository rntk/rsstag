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

test('changeLoadButtonState with hide_list clears tags map', async (t) => {
  const es = createTagContextsEventSystem();
  const storage = new TagContextsClassificationStorage(es);

  // Pre-populate tags
  storage.setState({ tags: new Map([['existing', { tag: 'existing' }]]) });
  es.calls = [];

  storage.changeLoadButtonState({ tag: 'existing', hide_list: true });

  assert.equal(storage.getState().tags.size, 0);
});

test('changeLoadButtonState without hide_list fetches contexts for the tag', async (t) => {
  const es = createTagContextsEventSystem();
  const storage = new TagContextsClassificationStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async (url) => {
    assert.ok(url.includes('my-tag'));
    return [{ tag: 'fetched', score: 0.9 }];
  };
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.changeLoadButtonState({ tag: 'my-tag', hide_list: false });
  await flushPromises();

  assert.ok(storage.getState().tags.has('fetched'));
});

test('fetchContexts with empty/falsy tag is a no-op', () => {
  const es = createTagContextsEventSystem();
  const storage = new TagContextsClassificationStorage(es);

  storage.fetchContexts('');
  storage.fetchContexts(null);
  storage.fetchContexts(undefined);

  assert.equal(storage.getState().tags.size, 0);
  assert.equal(es.calls.length, 0);
});

test('fetchContexts error response does not update state', async (t) => {
  const es = createTagContextsEventSystem();
  const storage = new TagContextsClassificationStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;
  const originalError = console.error;
  console.error = () => {};

  rsstag_utils.fetchJSON = async () => null;
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
    console.error = originalError;
  });

  storage.fetchContexts('tag');
  await flushPromises();

  assert.equal(storage.getState().tags.size, 0);
});

test('constructor sets correct URL for get_contexts', () => {
  const es = createTagContextsEventSystem();
  const storage = new TagContextsClassificationStorage(es);

  assert.equal(storage.urls.get_contexts, '/tag-contexts-classification');
});
