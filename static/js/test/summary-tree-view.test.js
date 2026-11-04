import test from 'node:test';
import assert from 'node:assert/strict';
import { SummaryTreeView } from '../summary-tree.js';
import { findPostLeaf } from '../libs/summary-tree-model.js';

function payload() {
  return {
    focus: 'Subject',
    result: {
      schema_version: 2,
      root_id: 'r',
      nodes: {
        r: {
          id: 'r',
          kind: 'root',
          title: 'Subject',
          post_ids: ['p'],
          children: ['p'],
          segments: [{ text: 'Overview', sources: [{ kind: 'claim', child: 'p', segment: 0 }] }],
        },
        p: {
          id: 'p',
          kind: 'post',
          title: 'Original',
          post_ids: ['p'],
          children: [],
          segments: [{ text: 'Detail', sources: [{ kind: 'rows', first: 2, last: 2 }] }],
        },
      },
      posts: {
        p: {
          pid: 'p',
          title: 'Original',
          summary: 'Detail',
          evidence: ['Title', '<script>evidence</script>'],
        },
      },
    },
  };
}

test('post panel highlights exact source passage and includes full route summaries', () => {
  const data = payload();
  const view = new SummaryTreeView({}, data, null);
  view.selectedKey = findPostLeaf(view.tree, 'p');
  const html = view.postPanel(data.result.posts.p, [[2, 2]]);
  assert.ok(html.includes('<li class="is-cited">&lt;script&gt;evidence&lt;/script&gt;</li>'));
  assert.ok(html.includes('<li>Title</li>'));
  assert.ok(html.includes('<mark>Overview</mark>'));
  assert.ok(html.includes('<mark>Detail</mark>'));
  assert.ok(!html.includes('<script>evidence</script>'));
});

test('poll payload updates fold the tree and select the root', () => {
  const view = new SummaryTreeView({}, payload(), null);
  const leafKey = findPostLeaf(view.tree, 'p');
  assert.equal(view.expanded.size, 0);
  view.selectedKey = leafKey;
  view.expanded.add(view.tree.key);
  view.expanded.add(leafKey);
  view.setPayload(payload());
  assert.equal(view.selectedKey, view.tree.key);
  assert.equal(view.expanded.size, 0);
  assert.equal(view.exclusive, false);
});

test('a provisional root displays the current entity while posts are being summarized', () => {
  const data = payload();
  data.result.schema_version = 3;
  data.result.root_id = null;
  const view = new SummaryTreeView({}, data, null);
  assert.equal(view.tree.title, 'Subject');
  assert.equal(view.expanded.size, 0);
});

test('polling preserves a fully folded tree and initializes a newly available tree', () => {
  const view = new SummaryTreeView({}, payload(), null);
  view.expanded.clear();
  view.setPayload(payload());
  assert.equal(view.expanded.size, 0);

  const pending = new SummaryTreeView({}, { result: null }, null);
  pending.setPayload(payload());
  assert.deepEqual([...pending.expanded], [...new SummaryTreeView({}, payload(), null).expanded]);
});

test('post leaves render as escaped, movable and resizable cards', () => {
  const data = payload();
  const view = new SummaryTreeView({}, data, null);
  const leaf = findPostLeaf(view.tree, 'p');
  const display = view.tree.children?.find((c) => c.key === leaf) || view.tree;
  const html = view.cardHtml({ ...display, key: leaf, post: data.result.posts.p, rows: [[2, 2]] });
  assert.ok(html.includes('class="stree-card__head"'));
  assert.ok(html.includes('class="stree-card__resize"'));
  assert.ok(html.includes('&lt;script&gt;evidence&lt;/script&gt;'));
  assert.ok(!html.includes('<script>'));
});

test('topic nodes show wrapped title and hidden-children count', () => {
  const view = new SummaryTreeView({}, payload(), null);
  const html = view.topicHtml({
    kind: 'topic',
    title: 'A <b>',
    postIds: ['p'],
    hiddenCount: 2,
    node: {},
  });
  assert.ok(html.includes('A &lt;b&gt;'));
  assert.ok(html.includes('+2 hidden'));
  assert.ok(html.includes('is-collapsed'));
});

test('post count is a button that unfolds the branch', () => {
  const view = new SummaryTreeView({}, payload(), null);
  const html = view.topicHtml({ kind: 'topic', title: 'T', postIds: ['p'], hiddenCount: 0, node: {} });
  assert.ok(html.includes('data-branch'));
  assert.ok(html.includes('>1 post</button>'));
});
