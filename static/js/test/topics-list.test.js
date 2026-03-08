import assert from 'node:assert/strict';
import test from 'node:test';

async function importTopicsListModule() {
  const originalWindow = globalThis.window;
  globalThis.window = { innerWidth: 1280 };

  try {
    return await import(`../topics-list.js?case=${Date.now()}-${Math.random()}`);
  } finally {
    globalThis.window = originalWindow;
  }
}

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
