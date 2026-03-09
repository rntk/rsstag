import test from 'node:test';
import assert from 'node:assert/strict';

import BiGramsMetionsStorage from '../storages/bigrams-mentions-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, flushPromises } from './helpers.js';

function createBigramsMentionsEventSystem() {
  return Object.assign(createEventSystem(), {
    BIGRAMS_MENTIONS_UPDATED: 'bigrams_mentions_updated',
    CHANGE_TAGS_LOAD_BUTTON_STATE: 'change_tags_load_button_state',
  });
}

test('constructor sets default state snapshot', () => {
  const storage = new BiGramsMetionsStorage('tag-x', createBigramsMentionsEventSystem());

  assert.deepEqual(storage.getState(), {
    tag: 'tag-x',
    bigrams: {},
  });
});

test('start() binds CHANGE_TAGS_LOAD_BUTTON_STATE', () => {
  const es = createBigramsMentionsEventSystem();
  const storage = new BiGramsMetionsStorage('tag-x', es);

  storage.start();

  assert.equal(es.bindings.has(es.CHANGE_TAGS_LOAD_BUTTON_STATE), true);
});

test('fetchDates() success updates state and emits payload shape', async (t) => {
  const es = createBigramsMentionsEventSystem();
  const storage = new BiGramsMetionsStorage('tag-x', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async () => ({ data: { one_two: [1, 2] } });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchDates('tag-x');
  await flushPromises();

  assert.deepEqual(es.calls.at(-1), {
    event: es.BIGRAMS_MENTIONS_UPDATED,
    payload: { tag: 'tag-x', bigrams: { one_two: [1, 2] } },
  });
});

test('fetchDates() failure path triggers errorMessage', async (t) => {
  const storage = new BiGramsMetionsStorage('tag-x', createBigramsMentionsEventSystem());
  const originalFetchJSON = rsstag_utils.fetchJSON;

  let errorText = null;
  storage.errorMessage = (msg) => {
    errorText = msg;
  };

  rsstag_utils.fetchJSON = async () => ({ error: 'bad' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchDates('tag-x');
  await flushPromises();

  assert.equal(errorText, 'Error. Try later');
});
