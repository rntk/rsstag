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

test('fetchTagSiblings() network catch path triggers errorMessage', async (t) => {
  global.document = { location: { hash: '' } };
  const es = createTagsEventSystem();
  const storage = new TagsStorage(es, '/siblings');
  const originalFetchJSON = rsstag_utils.fetchJSON;
  let errorText = null;
  storage.errorMessage = (msg) => {
    errorText = msg;
  };

  rsstag_utils.fetchJSON = async () => {
    throw new Error('service unavailable');
  };
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagSiblings('root');
  await flushPromises();

  assert.equal(errorText, 'Error. Try later');
});

test('changeTagSiblingsState with hide_list: true clears tags', async (t) => {
  global.document = { location: { hash: '' } };
  const es = createTagsEventSystem();
  const storage = new TagsStorage(es, '/siblings');
  const originalFetchJSON = rsstag_utils.fetchJSON;

  // Pre-populate tags
  storage.setState({
    tags: new Map([
      ['alpha', { tag: 'alpha', count: 3 }],
      ['beta', { tag: 'beta', count: 1 }],
    ]),
    tag_hash: '',
  });
  es.calls.length = 0;

  // Stub fetchJSON so it is not called during hide
  rsstag_utils.fetchJSON = async () => ({ data: [] });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.changeTagSiblingsState({ hide_list: true });

  assert.deepEqual([...storage.getState().tags.keys()], []);
  assert.equal(es.calls.at(-1).event, es.TAGS_UPDATED);
});

test('fetchTagSiblings with empty tag string does nothing', async (t) => {
  global.document = { location: { hash: '' } };
  const es = createTagsEventSystem();
  const storage = new TagsStorage(es, '/siblings');
  const originalFetchJSON = rsstag_utils.fetchJSON;
  let fetchCalls = 0;

  rsstag_utils.fetchJSON = async () => {
    fetchCalls += 1;
    return { data: [] };
  };
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagSiblings('');
  await flushPromises();

  assert.equal(fetchCalls, 0);
});

test('fetchTagSiblings with empty data array clears existing tags', async (t) => {
  global.document = { location: { hash: '' } };
  const es = createTagsEventSystem();
  const storage = new TagsStorage(es, '/siblings');
  const originalFetchJSON = rsstag_utils.fetchJSON;

  storage.setState({
    tags: new Map([['old', { tag: 'old', count: 1 }]]),
    tag_hash: '',
  });

  rsstag_utils.fetchJSON = async () => ({ data: [] });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagSiblings('root');
  await flushPromises();

  assert.equal(storage.getState().tags.size, 0);
});

test('normalizedTags marks all tags as root', () => {
  global.document = { location: { hash: '' } };
  const storage = new TagsStorage(createTagsEventSystem(), '/siblings');

  const normalized = storage.normalizedTags([
    { tag: 'alpha', count: 1 },
    { tag: 'beta', count: 2 },
  ]);

  assert.equal(normalized.get('alpha').root, true);
  assert.equal(normalized.get('beta').root, true);
});

test('fetchTags initializes tags from window.initial_tags_list', () => {
  global.document = { location: { hash: '' } };
  global.window = {
    initial_tags_list: [
      { tag: 'root', count: 5 },
      { tag: 'child', count: 2 },
    ],
  };
  const es = createTagsEventSystem();
  const storage = new TagsStorage(es, '/siblings');

  storage.fetchTags();

  assert.deepEqual([...storage.getState().tags.keys()], ['root', 'child']);
});

test('fetchTags does nothing when window.initial_tags_list is undefined', () => {
  global.document = { location: { hash: '' } };
  global.window = {};
  const es = createTagsEventSystem();
  const storage = new TagsStorage(es, '/siblings');

  storage.fetchTags();

  assert.equal(storage.getState().tags.size, 0);
});

test('fetchTagSiblings sorts tags by count descending', async (t) => {
  global.document = { location: { hash: '' } };
  const es = createTagsEventSystem();
  const storage = new TagsStorage(es, '/siblings');
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async () => ({
    data: [
      { tag: 'low', count: 1 },
      { tag: 'high', count: 10 },
      { tag: 'mid', count: 5 },
    ],
  });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagSiblings('root');
  await flushPromises();

  assert.deepEqual([...storage.getState().tags.keys()], ['high', 'mid', 'low']);
});
