import test from 'node:test';
import assert from 'node:assert/strict';

import PostsStorage from '../storages/posts-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem, createPost, flushPromises } from './helpers.js';

test('normalizePosts marks the first post as current', () => {
  const storage = new PostsStorage(createEventSystem());
  const posts = [createPost(1), createPost(2)];

  const normalized = storage.normalizePosts(posts);

  assert.equal(normalized.get('1').current, true);
  assert.equal(normalized.get('2').current, false);
});

test('fetchPosts reads page state from window globals', () => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
  const originalWindow = globalThis.window;

  globalThis.window = {
    posts_list: [createPost(1), createPost(2)],
    group: 'tag',
    group_title: 'alpha',
    words: ['alpha'],
    rss_settings: {
      posts_on_page: 25,
    },
  };

  try {
    storage.fetchPosts();
  } finally {
    globalThis.window = originalWindow;
  }

  const state = storage.getState();
  assert.equal(state.group, 'tag');
  assert.equal(state.group_title, 'alpha');
  assert.deepEqual(state.words, ['alpha']);
  assert.equal(state.posts_per_page, 25);
  assert.equal(state.posts.get('1').current, true);
  assert.deepEqual(es.calls.at(-1), {
    event: es.POSTS_UPDATED,
    payload: state,
  });
});

test('setCurrentPost swaps the current marker to the requested post', () => {
  const storage = new PostsStorage(createEventSystem());
  const normalized = storage.normalizePosts([createPost(1), createPost(2)]);

  storage.setState({
    words: [],
    group: '',
    group_title: '',
    posts: normalized,
    readed: false,
    showed: false,
    posts_per_page: 10,
    current_page: 1,
  });

  storage.setCurrentPost('2');

  assert.equal(storage.getState().posts.get('1').current, false);
  assert.equal(storage.getState().posts.get('2').current, true);
});

test('loadMorePosts increments the current page and emits an update', () => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);

  storage.setState({
    words: [],
    group: '',
    group_title: '',
    posts: new Map(),
    readed: false,
    showed: false,
    posts_per_page: 10,
    current_page: 1,
  });
  es.calls.length = 0;

  storage.loadMorePosts();

  assert.equal(storage.getState().current_page, 2);
  assert.equal(es.calls.at(-1).event, es.POSTS_UPDATED);
});

test('changePostsStatus persists the new read state after a successful request', async (t) => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  storage.setState({
    words: [],
    group: '',
    group_title: '',
    posts: new Map([['1', createPost(1)]]),
    readed: false,
    showed: false,
    posts_per_page: 10,
    current_page: 1,
  });

  rsstag_utils.fetchJSON = async () => ({ data: true });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.changePostsStatus({ ids: ['1'], readed: true });
  await flushPromises();

  assert.equal(storage.getState().posts.get('1').post.read, true);
  assert.equal(es.calls.at(-1).event, es.POSTS_UPDATED);
});
