import test from 'node:test';
import assert from 'node:assert/strict';

import TagsNetStorage from '../storages/tags-net-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { flushPromises } from './helpers.js';

function createEventSystem() {
  const calls = [];

  return {
    calls,
    TAGS_NET_UPDATED: 'tags_net_updated',
    TAGS_ERROR_MESSAGE: 'tags_error_message',
    LOAD_TAG_NET: 'load_tag_net',
    NET_TAG_SELECTED: 'net_tag_selected',
    NET_TAG_CHANGE: 'net_tag_change',
    trigger(event, payload) {
      calls.push({ event, payload });
    },
    bind() {},
    unbind() {},
  };
}

function createStorageWithTags(tags) {
  const storage = new TagsNetStorage(createEventSystem(), 'root');
  storage.setState({
    tags: new Map(tags.map((tag) => [tag.tag, tag])),
    main_tag: 'root',
    selected_tag: '',
  });
  storage.ES.calls.length = 0;
  return storage;
}

test('mergeTags creates new tags and merges repeated tags edges while preserving root group', () => {
  const storage = new TagsNetStorage(createEventSystem(), 'root');
  const state = {
    tags: new Map([
      [
        'root',
        {
          tag: 'root',
          group: 'old-group',
          hidden: false,
          edges: new Set(['alpha']),
        },
      ],
      [
        'alpha',
        {
          tag: 'alpha',
          group: 'old-group',
          hidden: false,
          edges: new Set(['root']),
        },
      ],
    ]),
    main_tag: 'root',
    selected_tag: '',
  };

  const merged = storage.mergeTags(
    state,
    [
      { tag: 'root', edges: ['alpha', 'beta'], count: 5 },
      { tag: 'beta', edges: ['root'], count: 1 },
    ],
    'root'
  );

  assert.equal(merged.tags.get('beta').group, 'root');
  assert.equal(merged.tags.get('beta').hidden, false);
  assert.ok(merged.tags.get('beta').edges instanceof Set);
  assert.deepEqual([...merged.tags.get('root').edges].sort(), ['alpha', 'beta']);
  assert.equal(merged.tags.get('root').group, 'root');
});

test('needHideEdge is false if any non-root edge is visible and true when all are hidden', () => {
  const storage = createStorageWithTags([
    { tag: 'root', hidden: false, edges: new Set(['alpha', 'beta']) },
    { tag: 'alpha', hidden: true, edges: new Set(['root']) },
    { tag: 'beta', hidden: false, edges: new Set(['root']) },
  ]);

  assert.equal(storage.needHideEdge(new Set(['root', 'alpha', 'beta']), 'root'), false);

  const state = storage.getState();
  state.tags.get('beta').hidden = true;
  storage.setState(state);
  storage.ES.calls.length = 0;

  assert.equal(storage.needHideEdge(new Set(['root', 'alpha', 'beta']), 'root'), true);
});

test('changeTagSettings toggles selected tag visibility and propagates hide/unhide', () => {
  const storage = createStorageWithTags([
    { tag: 'root', hidden: false, edges: new Set(['alpha', 'beta']) },
    { tag: 'alpha', hidden: false, edges: new Set(['root']) },
    { tag: 'beta', hidden: false, edges: new Set(['root', 'gamma']) },
    { tag: 'gamma', hidden: false, edges: new Set(['beta']) },
  ]);

  const hideBeta = {
    ...storage.getState().tags.get('beta'),
    hidden: true,
  };
  storage.changeTagSettings(hideBeta);

  assert.equal(storage.getState().tags.get('beta').hidden, true);
  assert.equal(storage.getState().tags.get('gamma').hidden, true);

  const hideRoot = {
    ...storage.getState().tags.get('root'),
    hidden: true,
  };
  storage.changeTagSettings(hideRoot);

  assert.equal(storage.getState().tags.get('alpha').hidden, true);
  assert.equal(storage.getState().tags.get('beta').hidden, true);

  const showRoot = {
    ...storage.getState().tags.get('root'),
    hidden: false,
  };
  storage.changeTagSettings(showRoot);

  assert.equal(storage.getState().tags.get('alpha').hidden, false);
  assert.equal(storage.getState().tags.get('beta').hidden, false);
  assert.equal(storage.ES.calls.at(-1).event, storage.ES.TAGS_NET_UPDATED);
});

test('selectTag updates only when the tag exists', () => {
  const storage = createStorageWithTags([
    { tag: 'root', hidden: false, edges: new Set() },
    { tag: 'alpha', hidden: false, edges: new Set(['root']) },
  ]);

  storage.selectTag('missing');
  assert.equal(storage.getState().selected_tag, '');
  assert.equal(storage.ES.calls.length, 0);

  storage.selectTag('alpha');
  assert.equal(storage.getState().selected_tag, 'alpha');
  assert.equal(storage.ES.calls.at(-1).event, storage.ES.TAGS_NET_UPDATED);
});

test('fetchTagsNet merges response data and emits error event for empty/error responses', async (t) => {
  const es = createEventSystem();
  const storage = new TagsNetStorage(es, 'root');
  const originalFetchJSON = rsstag_utils.fetchJSON;

  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  rsstag_utils.fetchJSON = async (url, options) => {
    assert.equal(url, '/api/tag-net/root');
    assert.equal(options.method, 'GET');
    return {
      data: [
        { tag: 'root', edges: ['alpha'] },
        { tag: 'alpha', edges: ['root'] },
      ],
    };
  };

  storage.fetchTagsNet('root');
  await flushPromises();

  assert.equal(storage.getState().tags.has('alpha'), true);
  assert.equal(es.calls.at(-1).event, es.TAGS_NET_UPDATED);

  es.calls.length = 0;
  rsstag_utils.fetchJSON = async () => ({ data: null });

  storage.fetchTagsNet('root');
  await flushPromises();

  assert.equal(es.calls.at(-1).event, es.TAGS_ERROR_MESSAGE);

  es.calls.length = 0;
  rsstag_utils.fetchJSON = async () => {
    throw new Error('network');
  };

  storage.fetchTagsNet('root');
  await flushPromises();

  assert.equal(es.calls.at(-1).event, es.TAGS_ERROR_MESSAGE);
});
