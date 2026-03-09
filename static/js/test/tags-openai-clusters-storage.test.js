import test from 'node:test';
import assert from 'node:assert/strict';

import TagsOpenAIClustersStorage from '../storages/tags-openai-clusters-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, flushPromises } from './helpers.js';

function createTagsOpenAIClustersEventSystem() {
  return Object.assign(createEventSystem(), {
    TAGS_CLUSTERS_UPDATED: 'tags_clusters_updated',
    CHANGE_TAGS_LOAD_BUTTON_STATE: 'change_tags_load_button_state',
  });
}

test('constructor sets default state snapshot', () => {
  global.document = { location: { hash: '' } };
  const storage = new TagsOpenAIClustersStorage(createTagsOpenAIClustersEventSystem());

  assert.deepEqual(storage.getState(), { clusters: {} });
});

test('start() binds CHANGE_TAGS_LOAD_BUTTON_STATE', () => {
  global.document = { location: { hash: '' } };
  const es = createTagsOpenAIClustersEventSystem();
  const storage = new TagsOpenAIClustersStorage(es);

  storage.start();

  assert.equal(es.bindings.has(es.CHANGE_TAGS_LOAD_BUTTON_STATE), true);
});

test('fetchTagClusters() success updates state and emits payload shape', async (t) => {
  global.document = { location: { hash: '' } };
  const es = createTagsOpenAIClustersEventSystem();
  const storage = new TagsOpenAIClustersStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async () => ({ data: { c1: ['x', 'y'] } });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagClusters('root');
  await flushPromises();

  assert.deepEqual(es.calls.at(-1), {
    event: es.TAGS_CLUSTERS_UPDATED,
    payload: { clusters: { c1: ['x', 'y'] } },
  });
});

test('fetchTagClusters() failure path triggers errorMessage', async (t) => {
  global.document = { location: { hash: '' } };
  const storage = new TagsOpenAIClustersStorage(createTagsOpenAIClustersEventSystem());
  const originalFetchJSON = rsstag_utils.fetchJSON;

  let errorText = null;
  storage.errorMessage = (msg) => {
    errorText = msg;
  };

  rsstag_utils.fetchJSON = async () => ({ error: 'nope' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagClusters('root');
  await flushPromises();

  assert.equal(errorText, 'Error: No data. Try later');
});
