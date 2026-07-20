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

test('fetchPostsContent updates showed flag and content on success', async (t) => {
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

  rsstag_utils.fetchJSON = async () => ({
    data: [{ pos: '1', content: '<p>new content</p>' }],
  });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchPostsContent(['1']);
  await flushPromises();

  const post = storage.getState().posts.get('1');
  assert.equal(post.showed, true);
  assert.equal(post.post.content.content, '<p>new content</p>');
  assert.equal(es.calls.at(-1).event, es.POSTS_UPDATED);
});

test('fetchPostsContent logs error on non-JSON response', async (t) => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;
  let errorMessage = null;
  storage.errorMessage = (msg) => {
    errorMessage = msg;
  };

  rsstag_utils.fetchJSON = async () => ({ error: 'not found' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchPostsContent(['1']);
  await flushPromises();

  assert.equal(errorMessage, 'Can\x60t fetch posts content');
});

test('fetchPostsContent catches network errors', async (t) => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;
  let errorMsg = null;
  let errorDetail = null;
  storage.errorMessage = (msg, err) => {
    errorMsg = msg;
    errorDetail = err;
  };

  rsstag_utils.fetchJSON = async () => {
    throw new Error('network unavailable');
  };
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchPostsContent(['1']);
  await flushPromises();

  assert.equal(errorMsg, 'Can\x60t fetch posts content.');
  assert.ok(errorDetail instanceof Error);
});

test('fetchPostLinks attaches sorted tags to post', async (t) => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;

  storage.setState({
    words: [],
    group: '',
    group_title: '',
    posts: new Map([['5', createPost(5)]]),
    readed: false,
    showed: false,
    posts_per_page: 10,
    current_page: 1,
  });

  rsstag_utils.fetchJSON = async () => ({
    data: {
      tags: [
        { tag: 'zebra', count: 1 },
        { tag: 'alpha', count: 3 },
        { tag: 'beta', count: 2 },
      ],
    },
  });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  await storage.fetchPostLinks('5');

  const post = storage.getState().posts.get('5');
  assert.deepEqual(
    post.links.tags.map((t) => t.tag),
    ['alpha', 'beta', 'zebra']
  );
});

test('fetchPostLinks handles missing data gracefully', async (t) => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;
  let errorMessage = null;
  storage.errorMessage = (msg) => {
    errorMessage = msg;
  };

  rsstag_utils.fetchJSON = async () => ({});
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  await storage.fetchPostLinks('1');

  assert.equal(errorMessage, undefined);
});

test('fetchPostLinks catches network errors', async (t) => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;
  let errorMsg = null;
  let errorDetail = null;
  storage.errorMessage = (msg, err) => {
    errorMsg = msg;
    errorDetail = err;
  };

  rsstag_utils.fetchJSON = async () => {
    throw new Error('dns failure');
  };
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.fetchPostLinks('1');
  await flushPromises();

  assert.equal(errorMsg, 'Can\x60t fetch posts links');
  assert.ok(errorDetail instanceof Error);
});

test('changePostsStatus handles network errors', async (t) => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;
  let errorMsg = null;
  let errorDetail = null;
  storage.errorMessage = (msg, err) => {
    errorMsg = msg;
    errorDetail = err;
  };

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

  rsstag_utils.fetchJSON = async () => {
    throw new Error('timeout');
  };
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.changePostsStatus({ ids: ['1'], readed: true });
  await flushPromises();

  assert.equal(errorMsg, 'Can\x60t change posts status.');
  assert.ok(errorDetail instanceof Error);
});

test('changePostsStatus handles response with no data', async (t) => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
  const originalFetchJSON = rsstag_utils.fetchJSON;
  let errorMessage = null;
  storage.errorMessage = (msg) => {
    errorMessage = msg;
  };

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

  rsstag_utils.fetchJSON = async () => ({ error: 'bad request' });
  t.after(() => {
    rsstag_utils.fetchJSON = originalFetchJSON;
  });

  storage.changePostsStatus({ ids: ['1'], readed: true });
  await flushPromises();

  assert.equal(errorMessage, 'Can\x60t change posts status');
});

test('changePostsStatus ignores invalid post IDs silently', async (t) => {
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

  const beforeCalls = es.calls.length;
  storage.changePostsStatus({ ids: ['999', '888'], readed: true });
  await flushPromises();

  // No state change, no POSTS_UPDATED triggered
  assert.equal(es.calls.length, beforeCalls);
});

test('setCurrentPost does nothing for a non-existent post ID', () => {
  const es = createEventSystem();
  const storage = new PostsStorage(es);
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

  const beforeCalls = es.calls.length;
  storage.setCurrentPost('999');

  assert.equal(es.calls.length, beforeCalls);
  assert.equal(storage.getState().posts.get('1').current, true);
  assert.equal(storage.getState().posts.get('2').current, false);
});

test('normalizePosts handles empty array', () => {
  const storage = new PostsStorage(createEventSystem());

  const normalized = storage.normalizePosts([]);

  assert.equal(normalized.size, 0);
});

test('loadMorePosts increments without boundary checks', () => {
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

  storage.loadMorePosts();
  storage.loadMorePosts();
  storage.loadMorePosts();

  assert.equal(storage.getState().current_page, 4);
});
