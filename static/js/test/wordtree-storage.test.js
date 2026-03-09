import test from 'node:test';
import assert from 'node:assert/strict';

import WordTreeStorage from '../storages/wordtree-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, flushPromises } from './helpers.js';

function createWordTreeEventSystem() {
  return Object.assign(createEventSystem(), {
    WORDTREE_TEXTS_UPDATED: 'wordtree_texts_updated',
    CHANGE_TAGS_LOAD_BUTTON_STATE: 'change_tags_load_button_state',
  });
}

test('constructor sets default state snapshot', () => {
  const storage = new WordTreeStorage('tag-x', createWordTreeEventSystem());

  assert.deepEqual(storage.getState(), {
    tag: 'tag-x',
    texts: [],
  });
});

test('start() binds CHANGE_TAGS_LOAD_BUTTON_STATE', () => {
  const es = createWordTreeEventSystem();
  const storage = new WordTreeStorage('tag-x', es);

  storage.start();

  assert.equal(es.bindings.has(es.CHANGE_TAGS_LOAD_BUTTON_STATE), true);
});

test('fetchWordTreeTexts() success updates state and emits payload shape', async (t) => {
  const es = createWordTreeEventSystem();
  const storage = new WordTreeStorage('tag-x', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async () => ({ data: ['t1', 't2'] });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchWordTreeTexts('tag-x');
  await flushPromises();

  assert.deepEqual(es.calls.at(-1), {
    event: es.WORDTREE_TEXTS_UPDATED,
    payload: { tag: 'tag-x', texts: ['t1', 't2'] },
  });
});

test('fetchWordTreeTexts() failure path triggers errorMessage', async (t) => {
  const storage = new WordTreeStorage('tag-x', createWordTreeEventSystem());
  const originalFetchJSON = rsstag_utils.fetchJSON;

  let errorText = null;
  storage.errorMessage = (msg) => {
    errorText = msg;
  };

  rsstag_utils.fetchJSON = async () => {
    throw new Error('network');
  };
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchWordTreeTexts('tag-x');
  await flushPromises();

  assert.equal(errorText, 'Error. Try later');
});
