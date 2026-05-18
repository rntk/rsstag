import assert from 'node:assert/strict';
import test from 'node:test';

// Static import so c8 instruments the module for coverage tracking.
import '../topics-list.js';

async function importTopicsListModule() {
  const originalWindow = globalThis.window;
  globalThis.window = { innerWidth: 1280 };

  try {
    return await import(`../topics-list.js?case=${Date.now()}-${Math.random()}`);
  } finally {
    globalThis.window = originalWindow;
  }
}

// ============================================================
// triggerAnthology tests
// ============================================================

test('triggerAnthology returns early when seedValue is empty', async () => {
  const { triggerAnthology } = await importTopicsListModule();

  let confirmCalled = false;
  globalThis.confirm = () => {
    confirmCalled = true;
    return true;
  };

  await triggerAnthology('', ['1', '2']);
  assert.equal(confirmCalled, false);

  await triggerAnthology(null, ['1']);
  assert.equal(confirmCalled, false);
});

test('triggerAnthology proceeds when user confirms and navigates on success', async () => {
  const originalWindow = globalThis.window;
  globalThis.window = { innerWidth: 1280, location: {} };

  const { triggerAnthology } = await importTopicsListModule();

  let confirmCalled = false;
  let confirmMessage = '';
  globalThis.confirm = (msg) => {
    confirmCalled = true;
    confirmMessage = msg;
    return true;
  };

  let alertCalled = false;
  let alertMessage = '';
  globalThis.alert = (msg) => {
    alertCalled = true;
    alertMessage = msg;
  };

  let fetchUrl = '';
  let fetchOptions = {};
  globalThis.fetch = async (url, options) => {
    fetchUrl = url;
    fetchOptions = options;
    return {
      ok: true,
      json: async () => ({ data: { anthology_id: 'abc-123' } }),
    };
  };

  let redirectedUrl = '';
  globalThis.window.location = {
    set href(url) {
      redirectedUrl = url;
    },
  };

  try {
    await triggerAnthology('machine learning', ['10', '20', '30']);

    assert.equal(confirmCalled, true);
    assert.equal(confirmMessage, 'Start anthology for "machine learning"?');
    assert.equal(fetchUrl, '/api/anthologies');
    assert.equal(fetchOptions.method, 'POST');
    assert.equal(fetchOptions.headers['Content-Type'], 'application/json');

    const body = JSON.parse(fetchOptions.body);
    assert.equal(body.seed_type, 'tag');
    assert.equal(body.seed_value, 'machine learning');
    assert.deepEqual(body.scope.mode, 'posts');
    assert.deepEqual(body.scope.post_ids, ['10', '20', '30']);

    assert.equal(redirectedUrl, '/anthologies/abc-123');
    assert.equal(alertCalled, false);
  } finally {
    globalThis.window = originalWindow;
  }
});

test('triggerAnthology navigates to /anthologies when no anthology_id returned', async () => {
  const originalWindow = globalThis.window;
  globalThis.window = { innerWidth: 1280, location: {} };

  const { triggerAnthology } = await importTopicsListModule();

  globalThis.confirm = () => true;
  globalThis.alert = () => {};
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ data: {} }),
  });

  let redirectedUrl = '';
  globalThis.window.location = {
    set href(url) {
      redirectedUrl = url;
    },
  };

  try {
    await triggerAnthology('test-topic', ['5']);
    assert.equal(redirectedUrl, '/anthologies');
  } finally {
    globalThis.window = originalWindow;
  }
});

test('triggerAnthology shows alert when user cancels confirm', async () => {
  const { triggerAnthology } = await importTopicsListModule();

  globalThis.confirm = () => false;

  let fetchCalled = false;
  globalThis.fetch = async () => {
    fetchCalled = true;
    return { ok: true, json: async () => ({}) };
  };

  await triggerAnthology('some-topic', ['1']);
  assert.equal(fetchCalled, false);
});

test('triggerAnthology shows alert when fetch fails with error response', async () => {
  const originalWindow = globalThis.window;
  globalThis.window = { innerWidth: 1280, location: {} };

  const { triggerAnthology } = await importTopicsListModule();

  globalThis.confirm = () => true;

  let alertMessage = '';
  globalThis.alert = (msg) => {
    alertMessage = msg;
  };

  globalThis.fetch = async () => ({
    ok: false,
    statusText: 'Bad Request',
    json: async () => ({ error: 'Invalid seed' }),
  });

  globalThis.window.location = { set href(_url) {} };

  try {
    await triggerAnthology('bad-topic', ['1']);
    assert.match(alertMessage, /Error starting anthology/);
  } finally {
    globalThis.window = originalWindow;
  }
});

test('triggerAnthology shows alert when fetch throws', async () => {
  const originalWindow = globalThis.window;
  globalThis.window = { innerWidth: 1280, location: {} };

  const { triggerAnthology } = await importTopicsListModule();

  globalThis.confirm = () => true;

  let alertMessage = '';
  globalThis.alert = (msg) => {
    alertMessage = msg;
  };

  globalThis.fetch = async () => {
    throw new Error('Network error');
  };

  globalThis.window.location = { set href(_url) {} };

  try {
    await triggerAnthology('topic', ['1']);
    assert.match(alertMessage, /Failed to start anthology/);
  } finally {
    globalThis.window = originalWindow;
  }
});

test('triggerAnthology passes single postIds as array when given a scalar', async () => {
  const originalWindow = globalThis.window;
  globalThis.window = { innerWidth: 1280, location: {} };

  const { triggerAnthology } = await importTopicsListModule();

  globalThis.confirm = () => true;
  globalThis.alert = () => {};

  let fetchBody = '';
  globalThis.fetch = async (_url, options) => {
    fetchBody = options.body;
    return {
      ok: true,
      json: async () => ({ data: { anthology_id: 'x' } }),
    };
  };

  globalThis.window.location = { set href(_url) {} };

  try {
    await triggerAnthology('topic', 'single-id');
    const body = JSON.parse(fetchBody);
    assert.deepEqual(body.scope.post_ids, ['single-id']);
  } finally {
    globalThis.window = originalWindow;
  }
});

test('buildTopicsSunburstGroups returns a single all-topics group when nothing is large enough', async () => {
  const { buildTopicsSunburstGroups } = await importTopicsListModule();
  const data = {
    name: 'root',
    children: [
      { name: 'Topic A', children: [{ name: 'Child 1' }] },
      { name: 'Topic B', children: [] },
    ],
  };

  const groups = buildTopicsSunburstGroups(data);

  assert.equal(groups.length, 1);
  assert.equal(groups[0].title, 'All Topics');
  assert.equal(groups[0].data, data);
});

test('buildTopicsSunburstGroups splits large topics and collects the tail group', async () => {
  const { buildTopicsSunburstGroups } = await importTopicsListModule();
  const data = {
    name: 'root',
    children: [
      {
        name: 'Big Topic',
        children: Array.from({ length: 8 }, (_, index) => ({ name: `Child ${index}` })),
      },
      {
        name: 'Small Topic',
        children: [{ name: 'Leaf' }],
      },
    ],
  };

  const groups = buildTopicsSunburstGroups(data);

  assert.deepEqual(
    groups.map((group) => group.title),
    ['Big Topic', 'Tail Topics']
  );
  assert.equal(groups[1].data.children.length, 1);
  assert.equal(groups[1].data.children[0].name, 'Small Topic');
});
