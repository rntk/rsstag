import test from 'node:test';
import assert from 'node:assert/strict';

import {
  boundsOf,
  buildDisplayTree,
  clampCardSize,
  columnOffsets,
  currentLevel,
  expandBranch,
  expandToLevel,
  fitTransform,
  topicMaxWidth,
  findPostLeaf,
  initialExpanded,
  labelSize,
  progressLabel,
  revealNode,
  sourceNumbers,
  toggleNode,
  treeDepth,
  visibleTree,
} from '../libs/summary-tree-model.js';

const result = {
  root_id: 'root',
  nodes: {
    root: {
      id: 'root',
      title: 'apple',
      virtual: true,
      post_ids: ['1', '2', '3'],
      children: ['n1', 'n2'],
      statements: [],
    },
    n1: {
      id: 'n1',
      title: 'Prices',
      post_ids: ['1', '2'],
      children: [],
      statements: [{ text: 'Up', sources: ['2'] }],
    },
    n2: { id: 'n2', title: 'Harvest', post_ids: ['3'], children: [], statements: [] },
  },
  posts: { 1: { pid: '1', title: 'One' }, 2: { pid: '2', summary_title: 'Two' }, 3: { pid: '3' } },
};

test('builds topics with post leaves', () => {
  const tree = buildDisplayTree(result);
  assert.equal(tree.kind, 'root');
  assert.deepEqual(
    tree.children.map((c) => c.title),
    ['Prices', 'Harvest']
  );
  assert.deepEqual(
    tree.children[0].children.map((c) => c.title),
    ['One', 'Two']
  );
});

test('initially shows at most five second-level items and no deeper branches', () => {
  const tree = buildDisplayTree(result);
  assert.deepEqual([...initialExpanded(tree)], ['root']);
  const child = tree.children[0];
  tree.children = Array.from({ length: 5 }, (_, i) => ({ ...child, key: String(i) }));
  assert.deepEqual([...initialExpanded(tree)], ['root']);
  tree.children.push({ ...child, key: 'six' });
  assert.deepEqual([...initialExpanded(tree)], []);
  assert.deepEqual([...initialExpanded(null)], []);
});

test('exclusive toggle walks one branch', () => {
  const tree = buildDisplayTree(result);
  let expanded = initialExpanded(tree);
  expanded = toggleNode(tree, expanded, 'n1', true);
  expanded = toggleNode(tree, expanded, 'n2', true);
  assert.equal(expanded.has('n1'), false);
  assert.equal(expanded.has('n2'), true);
  const visible = visibleTree(tree, expanded);
  assert.equal(visible.children[0].hiddenCount, 2);
});

test('reveals a cited post', () => {
  const tree = buildDisplayTree(result);
  const leaf = findPostLeaf(tree, '2', 'n1');
  assert.equal(leaf, 'n1:2');
  assert.equal(revealNode(tree, new Set(['root']), leaf).has('n1'), true);
});

test('source numbers start with cited posts', () => {
  assert.deepEqual(
    [...sourceNumbers(result.nodes.n1).entries()],
    [
      ['2', 1],
      ['1', 2],
    ]
  );
});

test('labels and progress', () => {
  const tree = buildDisplayTree(result);
  assert.ok(labelSize(tree, 3) > labelSize(tree.children[1], 3));
  assert.equal(
    progressLabel({ status: 'processing', stage: 'summaries', progress: { done: 2, total: 5 } }),
    'summaries 2/5'
  );
});

test('claim occurrences keep independent paths and exact passage ranges', () => {
  const cited = {
    schema_version: 2,
    root_id: 'r',
    posts: { p: { pid: 'p', title: 'Original', evidence: ['One', 'Two'] } },
    nodes: {
      r: {
        id: 'r',
        kind: 'root',
        title: 'Focus',
        post_ids: ['p'],
        children: ['p'],
        segments: [
          { text: 'First theme', sources: [{ kind: 'claim', child: 'p', segment: 0 }] },
          { text: 'Second theme', sources: [{ kind: 'claim', child: 'p', segment: 1 }] },
        ],
      },
      p: {
        id: 'p',
        kind: 'post',
        title: 'Original',
        post_ids: ['p'],
        children: [],
        segments: [
          { text: 'First detail', sources: [{ kind: 'rows', first: 1, last: 1 }] },
          { text: 'Second detail', sources: [{ kind: 'rows', first: 2, last: 2 }] },
        ],
      },
    },
  };
  const tree = buildDisplayTree(cited);
  assert.equal(tree.children.length, 2);
  const first = tree.children[0].children[0];
  const second = tree.children[1].children[0];
  assert.equal(first.kind, 'post');
  assert.notEqual(first.key, second.key);
  assert.deepEqual(first.rows, [[1, 1]]);
  assert.deepEqual(second.rows, [[2, 2]]);
  assert.equal(first.title, 'First detail');
  assert.ok(findPostLeaf(tree, 'p', tree.children[1].key).includes('/s1/'));
});

test('uncited children remain reachable during generation', () => {
  const tree = buildDisplayTree({
    schema_version: 2,
    root_id: 'r',
    posts: { p: { pid: 'p' } },
    nodes: {
      r: { id: 'r', kind: 'root', title: 'Focus', children: ['p'], segments: null },
      p: { id: 'p', kind: 'post', title: 'Pending', post_ids: ['p'], children: [], segments: null },
    },
  });
  assert.equal(tree.kind, 'post');
  assert.equal(tree.post.pid, 'p');
});

test('columnOffsets stacks columns by the widest node of each depth', () => {
  assert.deepEqual(columnOffsets([100, 300, 50], 20), [0, 120, 440]);
});

test('topicMaxWidth widens with font size within bounds', () => {
  assert.equal(topicMaxWidth(12), 480);
  assert.equal(topicMaxWidth(30), 660);
  assert.equal(topicMaxWidth(80), 760);
});

test('clampCardSize enforces the minimum card size', () => {
  assert.deepEqual(clampCardSize(10, 10), { w: 240, h: 120 });
  assert.deepEqual(clampCardSize(500.4, 300.6), { w: 500, h: 301 });
});

test('fitTransform shrinks oversized bounds and centres small ones', () => {
  const big = fitTransform(
    { minX: 0, minY: -500, width: 2000, height: 1000 },
    { width: 1048, height: 548 }
  );
  assert.equal(big.k, 0.5);
  assert.equal(big.x, 24);
  assert.equal(big.y, 274);
  const small = fitTransform(boundsOf([{ left: 0, top: -10, w: 100, h: 20 }]), {
    width: 400,
    height: 200,
  });
  assert.equal(small.k, 1);
  assert.equal(small.x, 150);
  assert.equal(small.y, 100);
  assert.equal(boundsOf([]), null);
});

const deep = () => ({
  key: 'r',
  kind: 'root',
  postIds: ['1'],
  children: [
    {
      key: 'a',
      kind: 'topic',
      postIds: ['1'],
      children: [
        {
          key: 'b',
          kind: 'topic',
          postIds: ['1'],
          children: [{ key: 'p', kind: 'post', postIds: ['1'], children: [] }],
        },
      ],
    },
    { key: 'c', kind: 'topic', postIds: ['2'], children: [{ key: 'q', kind: 'post', postIds: ['2'], children: [] }] },
  ],
});

test('treeDepth counts levels including post leaves', () => {
  assert.equal(treeDepth(null), 0);
  assert.equal(treeDepth({ key: 'x', kind: 'topic', children: [] }), 1);
  assert.equal(treeDepth(deep()), 4);
});

test('expandToLevel unfolds every branch down to the chosen level only', () => {
  const tree = deep();
  assert.deepEqual([...expandToLevel(tree, 1)], []);
  assert.deepEqual([...expandToLevel(tree, 2)].sort(), ['r']);
  assert.deepEqual([...expandToLevel(tree, 3)].sort(), ['a', 'c', 'r']);
  assert.deepEqual([...expandToLevel(tree, 4)].sort(), ['a', 'b', 'c', 'r']);
});

test('currentLevel recognises level states and reports custom ones as null', () => {
  const tree = deep();
  assert.equal(currentLevel(tree, expandToLevel(tree, 3)), 3);
  assert.equal(currentLevel(tree, new Set(['r', 'a'])), null);
});

test('expandBranch opens one branch fully and leaves the others alone', () => {
  const tree = deep();
  const next = expandBranch(tree, new Set(['r']), 'a');
  assert.deepEqual([...next].sort(), ['a', 'b', 'r']);
  assert.ok(!next.has('c'));
  assert.deepEqual([...expandBranch(tree, new Set(), 'b')].sort(), ['a', 'b', 'r']);
});

test('schema 3 follows the topic hierarchy down to cited post passages', () => {
  const claim = (child) => ({ kind: 'claim', child, segment: 0 });
  const tree = buildDisplayTree({
    schema_version: 3,
    root_id: 'r',
    nodes: {
      r: { id: 'r', kind: 'root', title: 'apple', children: ['t1', 't2'], post_ids: ['1', '2', '3'],
        segments: [{ text: 'Phones and Macs.', sources: [claim('t1')] }] },
      t1: { id: 't1', kind: 'topic', title: 'iPhone', children: ['p1', 'p2'], post_ids: ['1', '2'],
        segments: [{ text: 'Battery.', sources: [claim('p1')] }] },
      t2: { id: 't2', kind: 'topic', title: 'Mac', children: ['p3'], post_ids: ['3'], segments: [] },
      p1: { id: 'p1', kind: 'post', title: 'One', children: ['c1'], post_ids: ['1'],
        segments: [{ text: 'x', sources: [claim('c1')] }] },
      c1: { id: 'c1', kind: 'chunk', children: [], post_ids: ['1'],
        segments: [{ text: 'x', sources: [{ kind: 'rows', first: 2, last: 3 }] }] },
      p2: { id: 'p2', kind: 'post', title: 'Two', children: [], post_ids: ['2'], segments: [] },
      p3: { id: 'p3', kind: 'post', title: 'Three', children: [], post_ids: ['3'],
        segments: [{ text: 'y', sources: [{ kind: 'rows', first: 1, last: 1 }] }] },
    },
    posts: { 1: { pid: '1', title: 'One' }, 3: { pid: '3', title: 'Three' } },
  });
  assert.equal(tree.kind, 'root');
  assert.equal(tree.summary, 'Phones and Macs.');
  assert.deepEqual(tree.children.map((c) => [c.title, c.postIds]), [['iPhone', ['1']], ['Mac', ['3']]]);
  const post = tree.children[0].children[0];
  assert.equal(post.kind, 'post');
  assert.deepEqual(post.rows, [[2, 3]]);
  assert.deepEqual(post.parts, [{ node: 't1', segment: 0 }]);
  assert.deepEqual([...initialExpanded(tree)], ['r']);
});

test('schema 3 shows summarized posts while topics are still pending', () => {
  const tree = buildDisplayTree({
    schema_version: 3,
    root_id: null,
    nodes: { p1: { id: 'p1', kind: 'post', children: [], post_ids: ['1'], segments: [{ text: 'a', sources: [] }] } },
    posts: { 1: { pid: '1', title: 'One' } },
  });
  assert.deepEqual(tree.children.map((c) => c.key), ['p1']);
});
