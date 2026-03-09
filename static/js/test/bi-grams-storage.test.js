import test from 'node:test';
import assert from 'node:assert/strict';

import BiGramsStorage from '../storages/bi-grams-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { flushPromises } from './helpers.js';

function createEventSystem() {
  return {
    calls: [],
    TAGS_UPDATED: 'tags_updated',
    CHANGE_TAGS_LOAD_BUTTON_STATE: 'change_tags_load_button_state',
    TAGS_ERROR_MESSAGE: 'tags_error_message',
    trigger(event, payload) {
      this.calls.push({ event, payload });
    },
    bind() {},
  };
}

function withDocumentHash(hash = '') {
  const previousDocument = globalThis.document;
  globalThis.document = {
    location: {
      hash,
    },
  };
  return () => {
    globalThis.document = previousDocument;
  };
}

test('normalizedTags marks roots and returns map keyed by tag', () => {
  const restoreDocument = withDocumentHash('');
  const storage = new BiGramsStorage(createEventSystem());
  const tags = [{ tag: 'alpha' }, { tag: 'beta' }];

  try {
    const normalized = storage.normalizedTags(tags);

    assert.ok(normalized instanceof Map);
    assert.equal(normalized.get('alpha').root, true);
    assert.equal(normalized.get('beta').root, true);
    assert.deepEqual(Array.from(normalized.keys()), ['alpha', 'beta']);
  } finally {
    restoreDocument();
  }
});

test('fetchTags initializes tags map from window.initial_tags_list', () => {
  const restoreDocument = withDocumentHash('#selected');
  const previousWindow = globalThis.window;
  const es = createEventSystem();
  const storage = new BiGramsStorage(es);

  globalThis.window = {
    initial_tags_list: [{ tag: 'alpha' }, { tag: 'beta' }],
  };

  try {
    storage.fetchTags();

    const state = storage.getState();
    assert.equal(state.tag_hash, 'selected');
    assert.ok(state.tags instanceof Map);
    assert.equal(state.tags.get('alpha').root, true);
    assert.equal(state.tags.get('beta').root, true);
    assert.deepEqual(es.calls.at(-1), {
      event: es.TAGS_UPDATED,
      payload: state,
    });
  } finally {
    globalThis.window = previousWindow;
    restoreDocument();
  }
});

test('changeTagBigramsState with hide_list clears tags and emits update', () => {
  const restoreDocument = withDocumentHash('');
  const es = createEventSystem();
  const storage = new BiGramsStorage(es);

  try {
    storage.setState({
      tags: new Map([['alpha', { tag: 'alpha', root: true }]]),
      tag_hash: '',
    });
    es.calls.length = 0;

    storage.changeTagBigramsState({ hide_list: true });

    assert.equal(storage.getState().tags.size, 0);
    assert.equal(es.calls.at(-1).event, es.TAGS_UPDATED);
  } finally {
    restoreDocument();
  }
});

test('changeTagBigramsState with tag fetches only when tag exists', () => {
  const restoreDocument = withDocumentHash('');
  const storage = new BiGramsStorage(createEventSystem());
  const calls = [];

  try {
    storage.setState({
      tags: new Map([['alpha', { tag: 'alpha', root: true }]]),
      tag_hash: '',
    });

    storage.fetchTagBigrams = (tag) => {
      calls.push(tag);
    };

    storage.changeTagBigramsState({ tag: 'alpha' });
    storage.changeTagBigramsState({ tag: 'missing' });

    assert.deepEqual(calls, ['alpha']);
  } finally {
    restoreDocument();
  }
});

test('fetchTagBigrams fetches encoded URL, sorts siblings, links parent, and updates state', async (t) => {
  const restoreDocument = withDocumentHash('');
  const originalFetchJSON = rsstag_utils.fetchJSON;
  const es = createEventSystem();
  const storage = new BiGramsStorage(es);
  const requests = [];

  storage.setState({
    tags: new Map([['tag with space', { tag: 'tag with space', root: true }]]),
    tag_hash: '',
  });
  es.calls.length = 0;

  rsstag_utils.fetchJSON = async (url, options) => {
    requests.push({ url, options });
    return {
      data: [
        { tag: 'second', count: 3 },
        { tag: 'first', count: 7 },
      ],
    };
  };

  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
    restoreDocument();
  });

  storage.fetchTagBigrams('tag with space');
  await flushPromises();

  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, '/bi-grams-siblings/tag%20with%20space');
  assert.equal(requests[0].options.method, 'GET');

  const state = storage.getState();
  const rootTag = state.tags.get('tag with space');
  assert.deepEqual(rootTag.siblings, ['first', 'second']);
  assert.deepEqual(state.tags.get('first').parent, 'tag with space');
  assert.equal(state.tags.get('first').root, true);
  assert.deepEqual(state.tags.get('second').parent, 'tag with space');
  assert.equal(es.calls.at(-1).event, es.TAGS_UPDATED);
});

test('fetchTagBigrams handles API error response and rejected request', async (t) => {
  const restoreDocument = withDocumentHash('');
  const originalFetchJSON = rsstag_utils.fetchJSON;
  const es = createEventSystem();
  const storage = new BiGramsStorage(es);
  const errors = [];

  storage.setState({
    tags: new Map([['alpha', { tag: 'alpha', root: true }]]),
    tag_hash: '',
  });
  es.calls.length = 0;
  storage.TAGS_ERROR_MESSAGE = es.TAGS_ERROR_MESSAGE;

  rsstag_utils.fetchJSON = async () => ({ error: 'bad response' });
  storage.fetchTagBigrams('alpha');
  await flushPromises();

  rsstag_utils.fetchJSON = async () => {
    throw new Error('network');
  };
  storage.fetchTagBigrams('alpha');
  await flushPromises();

  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
    restoreDocument();
  });

  for (const call of es.calls) {
    if (call.event === es.TAGS_ERROR_MESSAGE) {
      errors.push(call.payload);
    }
  }

  assert.deepEqual(errors, ['Error. Try later', 'Error. Try later']);
});
