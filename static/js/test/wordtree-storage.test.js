import test from 'node:test';
import assert from 'node:assert/strict';

import WordTreeStorage from '../storages/wordtree-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, flushPromises } from './helpers.js';

function createWordTreeEventSystem() {
  return Object.assign(createEventSystem(), {
    WORDTREE_TEXTS_UPDATED: 'wordtree_texts_updated',
    CHANGE_TAGS_LOAD_BUTTON_STATE: 'change_tags_load_button_state',
    TAGS_ERROR_MESSAGE: 'tags_error_message',
  });
}

test('constructor sets default state snapshot', () => {
  const storage = new WordTreeStorage('tag-x', createWordTreeEventSystem());

  assert.deepEqual(storage.getState(), {
    tag: 'tag-x',
    texts: [],
  });
});

test('constructor sets correct URL for get_wordtree_texts', () => {
  const es = createWordTreeEventSystem();
  const storage = new WordTreeStorage('tag-x', es);

  assert.equal(storage.urls.get_wordtree_texts, '/wordtree-texts');
});

test('start() binds CHANGE_TAGS_LOAD_BUTTON_STATE', () => {
  const es = createWordTreeEventSystem();
  const storage = new WordTreeStorage('tag-x', es);

  storage.start();

  assert.equal(es.bindings.has(es.CHANGE_TAGS_LOAD_BUTTON_STATE), true);
});

test('changeState with hide_list clears texts', () => {
  const es = createWordTreeEventSystem();
  const storage = new WordTreeStorage('tag-x', es);

  // Pre-populate
  storage.setState({ tag: 'tag-x', texts: ['a', 'b'] });
  es.calls = [];

  storage.changeState({ tag: 'tag-x', hide_list: true });

  assert.deepEqual(storage.getState().texts, []);
});

test('changeState without hide_list fetches texts for the tag', async (t) => {
  const es = createWordTreeEventSystem();
  const storage = new WordTreeStorage('tag-x', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async (url) => {
    assert.ok(url.includes('my-tag'));
    return { data: ['new-text'] };
  };
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.changeState({ tag: 'my-tag', hide_list: false });
  await flushPromises();

  assert.deepEqual(storage.getState().texts, ['new-text']);
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

test('fetchWordTreeTexts() with no data in response triggers errorMessage', async (t) => {
  const es = createWordTreeEventSystem();
  const storage = new WordTreeStorage('tag-x', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  let errorMessage = null;
  storage.errorMessage = (msg) => {
    errorMessage = msg;
  };

  rsstag_utils.fetchJSON = async () => ({ error: 'bad' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchWordTreeTexts('tag-x');
  await flushPromises();

  assert.equal(errorMessage, 'Error. Try later');
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
