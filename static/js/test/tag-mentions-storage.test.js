import test from 'node:test';
import assert from 'node:assert/strict';

import TagMetionsStorage from '../storages/tag-mentions-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, flushPromises } from './helpers.js';

function createTagMentionsEventSystem() {
  return Object.assign(createEventSystem(), {
    TAG_MENTIONS_UPDATED: 'tag_mentions_updated',
    CHANGE_TAGS_LOAD_BUTTON_STATE: 'change_tags_load_button_state',
  });
}

test('constructor sets default state snapshot', () => {
  const storage = new TagMetionsStorage('tag-x', createTagMentionsEventSystem());

  assert.deepEqual(storage.getState(), {
    tag: 'tag-x',
    dates: [],
  });
});

test('start() binds CHANGE_TAGS_LOAD_BUTTON_STATE', () => {
  const es = createTagMentionsEventSystem();
  const storage = new TagMetionsStorage('tag-x', es);

  storage.start();

  assert.equal(es.bindings.has(es.CHANGE_TAGS_LOAD_BUTTON_STATE), true);
});

test('fetchTagDates() success updates state and emits payload shape', async (t) => {
  const es = createTagMentionsEventSystem();
  const storage = new TagMetionsStorage('tag-x', es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  rsstag_utils.fetchJSON = async () => ({ data: ['2024-01-01'] });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagDates('tag-x');
  await flushPromises();

  assert.deepEqual(es.calls.at(-1), {
    event: es.TAG_MENTIONS_UPDATED,
    payload: { tag: 'tag-x', dates: ['2024-01-01'] },
  });
});

test('fetchTagDates() failure path triggers errorMessage', async (t) => {
  const storage = new TagMetionsStorage('tag-x', createTagMentionsEventSystem());
  const originalFetchJSON = rsstag_utils.fetchJSON;

  let errorText = null;
  storage.errorMessage = (msg) => {
    errorText = msg;
  };

  rsstag_utils.fetchJSON = async () => ({ error: 'bad' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchTagDates('tag-x');
  await flushPromises();

  assert.equal(errorText, 'Error. Try later');
});
