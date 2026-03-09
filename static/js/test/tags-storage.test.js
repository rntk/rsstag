import test from 'node:test';
import assert from 'node:assert/strict';

import TagsStorage from '../storages/tags-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, flushPromises } from './helpers.js';

function createTagsEventSystem() {
  return Object.assign(createEventSystem(), {
    TAGS_UPDATED: 'tags_updated',
    CHANGE_TAGS_LOAD_BUTTON_STATE: 'change_tags_load_button_state',
  });
}

test('constructor sets default state snapshot', () => {
  global.document = { location: { hash: '#root' } };
  const storage = new TagsStorage(createTagsEventSystem(), '/siblings');

  assert.deepEqual(storage.getState(), {
    tags: new Map(),
    tag_hash: 'root',
  });
});

test('start() binds CHANGE_TAGS_LOAD_BUTTON_STATE', () => {
  global.document = { location: { hash: '' } };
  global.window = {};
  const es = createTagsEventSystem();
  const storage = new TagsStorage(es, '/siblings');

  storage.start();

  assert.equal(es.bindings.has(es.CHANGE_TAGS_LOAD_BUTTON_STATE), true);
});

test('fetchTagSiblings() success updates tags and emits payload shape', async (t) => {
  global.document = { location: { hash: '' } };
  const es = createTagsEventSystem();
  const storage = new TagsStorage(es, '/siblings');
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async () => ({
    data: [
      { tag: 'b', count: 1 },
      { tag: 'a', count: 5 },
    ],
  });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagSiblings('root');
  await flushPromises();

  const payload = es.calls.at(-1).payload;
  assert.equal(es.calls.at(-1).event, es.TAGS_UPDATED);
  assert.deepEqual([...payload.tags.keys()], ['a', 'b']);
});

test('fetchTagSiblings() error response triggers errorMessage', async (t) => {
  global.document = { location: { hash: '' } };
  const storage = new TagsStorage(createTagsEventSystem(), '/siblings');
  const originalFetchJSON = rsstag_utils.fetchJSON;

  let errorText = null;
  storage.errorMessage = (msg) => {
    errorText = msg;
  };

  rsstag_utils.fetchJSON = async () => ({ error: 'no data' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagSiblings('root');
  await flushPromises();

  assert.equal(errorText, 'Error. Try later');
});
