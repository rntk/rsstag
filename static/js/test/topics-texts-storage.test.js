import test from 'node:test';
import assert from 'node:assert/strict';

import TopicsTextsStorage from '../storages/topics-texts-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, flushPromises } from './helpers.js';

function createTopicsTextsEventSystem() {
  return Object.assign(createEventSystem(), {
    TOPICS_TEXTS_UPDATED: 'topics_texts_updated',
    TAGS_ERROR_MESSAGE: 'tags_error_message',
  });
}

test('constructor sets default state snapshot', () => {
  const storage = new TopicsTextsStorage('tag-x', createTopicsTextsEventSystem());

  assert.deepEqual(storage.getState(), {
    tag: 'tag-x',
    texts: [],
    topics: [],
  });
});

test('constructor sets correct URL for get_wordtree_texts', () => {
  const es = createTopicsTextsEventSystem();
  const storage = new TopicsTextsStorage('tag-x', es);

  assert.equal(storage.urls.get_wordtree_texts, '/topics-texts');
});

test('start() calls fetchWordTreeTexts with current tag', () => {
  const storage = new TopicsTextsStorage('tag-x', createTopicsTextsEventSystem());

  let passedTag = null;
  storage.fetchWordTreeTexts = (tag) => {
    passedTag = tag;
  };

  storage.start();

  assert.equal(passedTag, 'tag-x');
});

test('fetchWordTreeTexts() success updates state and emits payload shape', async (t) => {
  const es = createTopicsTextsEventSystem();
  const storage = new TopicsTextsStorage('tag-x', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async () => ({
    data: {
      texts: ['text1'],
      topics: ['topic1'],
    },
  });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchWordTreeTexts('tag-x');
  await flushPromises();

  assert.deepEqual(es.calls.at(-1), {
    event: es.TOPICS_TEXTS_UPDATED,
    payload: {
      tag: 'tag-x',
      texts: ['text1'],
      topics: ['topic1'],
    },
  });
});

test('fetchWordTreeTexts() with no data triggers errorMessage', async (t) => {
  const es = createTopicsTextsEventSystem();
  const storage = new TopicsTextsStorage('tag-x', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  let errorMessage = null;
  storage.errorMessage = (msg) => {
    errorMessage = msg;
  };

  rsstag_utils.fetchJSON = async () => ({ error: 'no data' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchWordTreeTexts('tag-x');
  await flushPromises();

  assert.equal(errorMessage, 'Error. Try later');
});

test('fetchWordTreeTexts() network failure triggers errorMessage', async (t) => {
  const es = createTopicsTextsEventSystem();
  const storage = new TopicsTextsStorage('tag-x', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  let errorMessage = null;
  storage.errorMessage = (msg) => {
    errorMessage = msg;
  };

  rsstag_utils.fetchJSON = async () => {
    throw new Error('offline');
  };
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchWordTreeTexts('tag-x');
  await flushPromises();

  assert.equal(errorMessage, 'Error. Try later');
});
