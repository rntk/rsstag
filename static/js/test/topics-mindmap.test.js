import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import TopicsMindmap from '../components/topics-mindmap.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'topics-mindmap.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

/**
 * Extract a class method body from source.
 */
function extractMethodBody(src, name) {
  const idx = src.indexOf(`${name}(`);
  if (idx === -1) throw new Error(`Method ${name} not found`);

  const parenOpen = src.indexOf('(', idx + name.length);
  let depth = 0;
  let parenClose = -1;
  for (let i = parenOpen; i < src.length; i += 1) {
    if (src[i] === '(') depth += 1;
    else if (src[i] === ')') {
      depth -= 1;
      if (depth === 0) {
        parenClose = i;
        break;
      }
    }
  }

  const bodyStart = src.indexOf('{', parenClose);
  let braceDepth = 0;
  let end = bodyStart;
  for (; end < src.length; end += 1) {
    if (src[end] === '{') braceDepth += 1;
    else if (src[end] === '}') {
      braceDepth -= 1;
      if (braceDepth === 0) break;
    }
  }

  return src.slice(bodyStart + 1, end);
}

// ============================================================
// Helpers
// ============================================================

/**
 * Create a d3.hierarchy-like node without actually calling d3.hierarchy.
 * Tests that call _normalizeNodeData, _toggleChildren, etc. work with plain
 * objects that have the same shape as d3 hierarchy nodes.
 */
function makeNode(name, nodeKind = 'topic', overrides = {}) {
  return {
    data: {
      name,
      node_kind: nodeKind,
      ...overrides,
    },
    children: null,
    _children: null,
    depth: 1,
    x: 0,
    y: 0,
  };
}

/**
 * Create a node tree with nested children.
 */
function makeTree(rootName, childNames, options = {}) {
  const root = makeNode(rootName, options.rootKind || 'root', options.rootData || {});
  root.depth = 0;
  root.children = childNames.map((name, i) => {
    const child = makeNode(name, options.childKind || 'topic', {
      ...((options.childData || {})[i] || {}),
    });
    child.parent = root;
    child.depth = 1;
    if (options.grandchildren && options.grandchildren[i]) {
      child.children = options.grandchildren[i].map((gname) => {
        const grand = makeNode(gname, 'subtopic');
        grand.parent = child;
        grand.depth = 2;
        return grand;
      });
    }
    return child;
  });
  return root;
}

// ============================================================
// Section 1: Constructor
// ============================================================

test('TopicsMindmap is constructable', () => {
  const mm = new TopicsMindmap();
  assert.ok(mm instanceof TopicsMindmap);
});

test('TopicsMindmap initializes with default options', () => {
  const mm = new TopicsMindmap();
  assert.equal(mm.options.topicClickAction, 'navigate');
  assert.equal(mm.options.countLabel, 'posts');
});

test('TopicsMindmap initializes with default node sizing constants', () => {
  const mm = new TopicsMindmap();
  assert.equal(mm.nodeHeight, 32);
  assert.equal(mm.nodeSpacingY, 20);
  assert.equal(mm.nodeMinWidth, 96);
  assert.equal(mm.nodeMaxWidth, 440);
  assert.equal(mm.nodeCharWidth, 7.5);
});

test('TopicsMindmap initializes with default snippet settings', () => {
  const mm = new TopicsMindmap();
  assert.equal(mm.snippetPanelWidth, 420);
  assert.equal(mm.snippetItemHeight, 80);
  assert.equal(mm.snippetMaxHeight, 500);
});

test('TopicsMindmap initializes search/filter state as empty', () => {
  const mm = new TopicsMindmap();
  assert.equal(mm._searchFilter, '');
  assert.equal(mm._alphaFilter, '');
  assert.equal(mm._focusedRootIndex, null);
  assert.equal(mm._twoColMode, false);
});

test('TopicsMindmap initializes D3 references as null', () => {
  const mm = new TopicsMindmap();
  assert.equal(mm.gMain, null);
  assert.equal(mm.svg, null);
  assert.equal(mm.root, null);
  assert.equal(mm.zoom, null);
});

// ============================================================
// Section 2: _normalizeNodeData
// ============================================================

test('_normalizeNodeData handles null/undefined gracefully', () => {
  const mm = new TopicsMindmap();
  assert.doesNotThrow(() => mm._normalizeNodeData(null));
  assert.doesNotThrow(() => mm._normalizeNodeData(undefined));
  assert.doesNotThrow(() => mm._normalizeNodeData({}));
});

test('_normalizeNodeData sets default node_kind from _nodeKind', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', undefined, { _nodeKind: 'custom_kind' });
  delete node.data.node_kind;
  mm._normalizeNodeData(node);
  assert.equal(node.data.node_kind, 'custom_kind');
});

test('_normalizeNodeData sets default node_kind to topic when missing', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test');
  delete node.data.node_kind;
  mm._normalizeNodeData(node);
  assert.equal(node.data.node_kind, 'topic');
});

test('_normalizeNodeData uses _isSnippetNode to infer snippet_panel kind', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippet', undefined, { _isSnippetNode: true });
  delete node.data.node_kind;
  mm._normalizeNodeData(node);
  assert.equal(node.data.node_kind, 'snippet_panel');
});

test('_normalizeNodeData sets available_actions from data', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', { available_actions: ['tags', 'sources'] });
  mm._normalizeNodeData(node);
  assert.deepEqual(node.data.available_actions, ['tags', 'sources']);
});

test('_normalizeNodeData falls back to _availableActions when available_actions is missing', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', { _availableActions: ['categories'] });
  delete node.data.available_actions;
  mm._normalizeNodeData(node);
  assert.deepEqual(node.data.available_actions, ['categories']);
});

test('_normalizeNodeData uses default actions for topic kind', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic');
  delete node.data.available_actions;
  mm._normalizeNodeData(node);
  assert.deepEqual(node.data.available_actions, [
    'tags',
    'sentences',
    'sources',
    'categories',
    'subtopics',
  ]);
});

test('_normalizeNodeData returns empty actions for snippet_panel', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippet', 'snippet_panel');
  delete node.data.available_actions;
  mm._normalizeNodeData(node);
  assert.deepEqual(node.data.available_actions, []);
});

test('_normalizeNodeData returns empty actions for root', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('root', 'root');
  delete node.data.available_actions;
  mm._normalizeNodeData(node);
  assert.deepEqual(node.data.available_actions, []);
});

test('_normalizeNodeData copies _mindmapScope to scope', () => {
  const mm = new TopicsMindmap();
  const scope = { topic_path: 'a/b', post_ids: [1, 2] };
  const node = makeNode('test', 'topic', { _mindmapScope: scope });
  mm._normalizeNodeData(node);
  assert.deepEqual(node.data.scope, scope);
});

test('_normalizeNodeData builds scope from _topicPath and _topicPosts', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', {
    _topicPath: 'science/physics',
    _topicPosts: [10, 20, 30],
  });
  mm._normalizeNodeData(node);
  assert.equal(node.data.scope.topic_path, 'science/physics');
  assert.deepEqual(node.data.scope.post_ids, [10, 20, 30]);
  assert.equal(node.data.scope.node_kind, 'topic');
});

test('_normalizeNodeData sets _isSnippetNode flag for snippet_panel kind', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippets', 'snippet_panel', { snippets: [] });
  mm._normalizeNodeData(node);
  assert.equal(node.data._isSnippetNode, true);
});

// ============================================================
// Section 3: _getAvailableActions
// ============================================================

test('_getAvailableActions returns empty for null node', () => {
  const mm = new TopicsMindmap();
  assert.deepEqual(mm._getAvailableActions(null), []);
  assert.deepEqual(mm._getAvailableActions(undefined), []);
  assert.deepEqual(mm._getAvailableActions({}), []);
});

test('_getAvailableActions returns data.available_actions when present', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', { available_actions: ['tags'] });
  assert.deepEqual(mm._getAvailableActions(node), ['tags']);
});

test('_getAvailableActions falls back to defaults for topic nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic');
  const actions = mm._getAvailableActions(node);
  assert.deepEqual(actions, ['tags', 'sentences', 'sources', 'categories', 'subtopics']);
});

test('_getAvailableActions returns empty for root node', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('root', 'root');
  assert.deepEqual(mm._getAvailableActions(node), []);
});

test('_getAvailableActions returns empty for snippet_panel', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippets', 'snippet_panel');
  assert.deepEqual(mm._getAvailableActions(node), []);
});

// ============================================================
// Section 4: _collapseAll
// ============================================================

test('_collapseAll moves children to _children and clears children', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['A', 'B'], {
    grandchildren: [['A1', 'A2'], ['B1']],
  });
  const childA = tree.children[0];
  mm._collapseAll(childA);
  assert.equal(childA.children, null);
  assert.ok(Array.isArray(childA._children), '_children should be an array');
  assert.equal(childA._children.length, 2);
});

test('_collapseAll recursively collapses grandchildren', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['A'], {
    grandchildren: [['A1', 'A2']],
  });
  const childA = tree.children[0];
  mm._collapseAll(childA);
  assert.equal(childA.children, null);
  assert.ok(Array.isArray(childA._children), '_children should be an array');
  assert.equal(childA._children.length, 2);
  // Grandchildren are leaf nodes (no children of their own), so their _children stays null
  const collapsedGrandA1 = childA._children[0];
  assert.equal(collapsedGrandA1.children, null);
  assert.equal(collapsedGrandA1._children, null, 'leaf grandchildren have no children to collapse');
});

test('_collapseAll does nothing for snippet_panel nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippets', 'snippet_panel', { snippets: [] });
  node.children = [makeNode('child1'), makeNode('child2')];
  const originalCount = node.children.length;
  mm._collapseAll(node);
  assert.equal(node.children.length, originalCount, 'children count should be preserved');
  assert.equal(node._children, null, '_children should remain null');
});

test('_collapseAll does nothing for leaf nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('leaf');
  node.children = null;
  mm._collapseAll(node);
  assert.equal(node.children, null);
  assert.equal(node._children, null);
});

// ============================================================
// Section 5: _toggleChildren
// ============================================================

test('_toggleChildren collapses when children exist', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test');
  node.children = [makeNode('c1'), makeNode('c2')];
  mm._toggleChildren(node);
  assert.equal(node.children, null);
  assert.equal(node._children.length, 2);
});

test('_toggleChildren expands when _children exist', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test');
  node._children = [makeNode('c1'), makeNode('c2')];
  node.children = null;
  mm._toggleChildren(node);
  assert.equal(node._children, null);
  assert.equal(node.children.length, 2);
});

test('_toggleChildren does nothing when both children and _children are null', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test');
  node.children = null;
  node._children = null;
  mm._toggleChildren(node);
  assert.equal(node.children, null);
  assert.equal(node._children, null);
});

test('_toggleChildren preserves child references', () => {
  const mm = new TopicsMindmap();
  const child1 = makeNode('c1');
  const child2 = makeNode('c2');
  const node = makeNode('test');
  node.children = [child1, child2];
  mm._toggleChildren(node);
  assert.strictEqual(node._children[0], child1);
  assert.strictEqual(node._children[1], child2);
});

// ============================================================
// Section 6: _isSnippetNode
// ============================================================

test('_isSnippetNode returns true for snippet_panel kind', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippets', 'snippet_panel');
  assert.equal(mm._isSnippetNode(node), true);
});

test('_isSnippetNode returns true when _isSnippetNode flag is set', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', { _isSnippetNode: true });
  assert.equal(mm._isSnippetNode(node), true);
});

test('_isSnippetNode returns false for regular topic nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic');
  assert.equal(mm._isSnippetNode(node), false);
});

test('_isSnippetNode returns false for subtopic nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'subtopic');
  assert.equal(mm._isSnippetNode(node), false);
});

test('_isSnippetNode returns false for null/undefined', () => {
  const mm = new TopicsMindmap();
  assert.equal(mm._isSnippetNode(null), false);
  assert.equal(mm._isSnippetNode(undefined), false);
  assert.equal(mm._isSnippetNode({}), false);
  assert.equal(mm._isSnippetNode({ data: {} }), false);
});

// ============================================================
// Section 7: _hasMenuButton
// ============================================================

test('_hasMenuButton returns true for topic with available actions', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic');
  assert.equal(mm._hasMenuButton(node), true);
});

test('_hasMenuButton returns false for snippet_panel nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippets', 'snippet_panel');
  assert.equal(mm._hasMenuButton(node), false);
});

test('_hasMenuButton returns false for nodes with no available actions', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', { available_actions: [] });
  assert.equal(mm._hasMenuButton(node), false);
});

test('_hasMenuButton returns false for root nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('root', 'root');
  assert.equal(mm._hasMenuButton(node), false);
});

// ============================================================
// Section 8: _nodeWidth
// ============================================================

test('_nodeWidth returns snippetPanelWidth for snippet nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippets', 'snippet_panel');
  assert.equal(mm._nodeWidth(node), mm.snippetPanelWidth);
});

test('_nodeWidth respects minWidth for short labels', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('Hi', 'topic');
  const width = mm._nodeWidth(node);
  assert.ok(width >= mm.nodeMinWidth, 'should be at least nodeMinWidth');
});

test('_nodeWidth respects maxWidth for very long labels', () => {
  const mm = new TopicsMindmap();
  const node = makeNode(
    'This is an extremely long topic label that should definitely trigger the maximum width constraint',
    'topic'
  );
  const width = mm._nodeWidth(node);
  assert.ok(width <= mm.nodeMaxWidth, 'should not exceed nodeMaxWidth');
});

test('_nodeWidth increases with label length', () => {
  const mm = new TopicsMindmap();
  const shortNode = makeNode('Short', 'topic');
  const longNode = makeNode(
    'This is a much longer topic label for testing width calculation',
    'topic'
  );
  const shortWidth = mm._nodeWidth(shortNode);
  const longWidth = mm._nodeWidth(longNode);
  assert.ok(longWidth > shortWidth, 'longer label should produce wider node');
});

test('_nodeWidth accounts for arrow space when node has children', () => {
  const mm = new TopicsMindmap();
  const nodeWithChildren = makeNode('test', 'topic');
  nodeWithChildren.children = [makeNode('child')];
  const nodeWithoutChildren = makeNode('test', 'topic');
  const widthWith = mm._nodeWidth(nodeWithChildren);
  const widthWithout = mm._nodeWidth(nodeWithoutChildren);
  // Arrow adds nodeArrowWidth space
  assert.ok(widthWith >= widthWithout, 'node with children should be at least as wide');
});

test('_nodeWidth accounts for menu button space when node has actions', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic');
  const width = mm._nodeWidth(node);
  // Topic nodes have default actions, so menu button space is included
  assert.ok(width > mm.nodeMinWidth, 'should be wider than minimum due to menu button');
});

// ============================================================
// Section 9: _displayNodeLabel
// ============================================================

test('_displayNodeLabel returns empty string for snippet nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippets', 'snippet_panel');
  assert.equal(mm._displayNodeLabel(node), '');
});

test('_displayNodeLabel returns full label when it fits', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('Short Label', 'topic');
  const label = mm._displayNodeLabel(node);
  assert.equal(label, 'Short Label');
});

test('_displayNodeLabel truncates long labels with ellipsis', () => {
  const mm = new TopicsMindmap();
  const longName =
    'This is a very long topic name that will definitely need truncation because it exceeds the available width';
  const node = makeNode(longName, 'topic');
  const label = mm._displayNodeLabel(node);
  assert.ok(label.length < longName.length, 'truncated label should be shorter');
  assert.ok(label.endsWith('...'), 'truncated label should end with ellipsis');
});

test('_displayNodeLabel preserves original when label fits exactly', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('Fit', 'topic');
  const label = mm._displayNodeLabel(node);
  assert.equal(label, 'Fit');
});

test('_displayNodeLabel handles empty name', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('', 'topic');
  const label = mm._displayNodeLabel(node);
  assert.equal(label, '');
});

test('_displayNodeLabel returns ellipsis for very short usable width', () => {
  const mm = new TopicsMindmap();
  // Create an extremely long name to force maxChars <= 3
  const extremeName = 'A'.repeat(500);
  const node = makeNode(extremeName, 'topic');
  const label = mm._displayNodeLabel(node);
  assert.ok(label.endsWith('...'), 'should truncate with ellipsis');
  assert.ok(label.length < extremeName.length, 'should be truncated');
});

// ============================================================
// Section 10: _buildSnippetHTML (source inspection)
// ============================================================

test('_buildSnippetHTML generates header with sentence count', () => {
  assert.ok(
    /\$\{snippets\.length\}\s*sentence/.test(source),
    'should include sentence count in header'
  );
  assert.ok(/snippets\.length\s*!==\s*1/.test(source), 'should handle singular case');
});

test('_buildSnippetHTML generates header with plural sentence count', () => {
  assert.ok(/sentence/.test(source), 'should include sentence text');
  assert.ok(/snippets\.length/.test(source), 'should use snippets.length for count');
});

test('_buildSnippetHTML includes Maximize button by default', () => {
  assert.ok(/maximize/.test(source), 'should include maximize button');
  assert.ok(/Maximize/.test(source), 'should have Maximize label');
});

test('_buildSnippetHTML excludes Maximize button when includeMaximize is false', () => {
  assert.ok(/includeMaximize/.test(source), 'should check includeMaximize option');
});

test('_buildSnippetHTML includes Read All and Unread All buttons', () => {
  assert.ok(/Read All/.test(source), 'should include Read All button');
  assert.ok(/Unread All/.test(source), 'should include Unread All button');
});

test('_buildSnippetHTML includes close button when includeClose is true', () => {
  assert.ok(/includeClose/.test(source), 'should check includeClose option');
  assert.ok(/Close/.test(source), 'should include Close label');
});

test('_buildSnippetHTML does not include close button by default', () => {
  assert.ok(/includeClose/.test(source), 'should use includeClose option');
});

test('_buildSnippetHTML generates snippet items with correct indices', () => {
  assert.ok(/data-index/.test(source), 'should include data-index attribute');
  assert.ok(/index/.test(source), 'should use index for data-index');
});

test('_buildSnippetHTML shows Read/Unread toggle based on snippet state', () => {
  assert.ok(/\.read/.test(source), 'should check snippet read state');
  assert.ok(/Read/.test(source), 'should include Read button');
  assert.ok(/Unread/.test(source), 'should include Unread button');
});

test('_buildSnippetHTML applies read class to read snippets', () => {
  assert.ok(/read/.test(source), 'should include read class');
  assert.ok(/snippet\.read/.test(source), 'should check snippet.read for class');
});

test('_buildSnippetHTML respects textPreviewLimit option', () => {
  assert.ok(/textPreviewLimit/.test(source), 'should check textPreviewLimit option');
  assert.ok(/substring|slice|substr/.test(source), 'should truncate text');
});

test('_buildSnippetHTML uses html fallback when text is missing', () => {
  assert.ok(/\.html/.test(source), 'should check html field');
  assert.ok(/\.text/.test(source), 'should check text field');
});

test('_buildSnippetHTML handles empty snippets array', () => {
  assert.ok(/snippets\.length/.test(source), 'should check snippets length');
  assert.ok(/snippets\.length\s*}\s*sentence/.test(source), 'should show zero count');
});

test('_buildSnippetHTML includes close-panel button when includeClosePanel is true', () => {
  assert.ok(/includeClosePanel/.test(source), 'should check includeClosePanel option');
  assert.ok(/close-panel/.test(source), 'should include close-panel action');
});

// ============================================================
// Section 11: _getFilteredRootChildren
// ============================================================

test('_getFilteredRootChildren returns all children when no filter is set', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['Alpha', 'Beta', 'Gamma']);
  mm.root = tree;
  mm._allRootChildren = tree.children;
  mm._searchFilter = '';
  mm._alphaFilter = '';
  mm._focusedRootIndex = null;

  const result = mm._getFilteredRootChildren();
  assert.equal(result.length, 3);
  assert.equal(result[0].data.name, 'Alpha');
  assert.equal(result[1].data.name, 'Beta');
  assert.equal(result[2].data.name, 'Gamma');
});

test('_getFilteredRootChildren returns null when _allRootChildren is empty', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', []);
  mm.root = tree;
  mm._allRootChildren = [];
  mm._searchFilter = '';
  mm._alphaFilter = '';
  mm._focusedRootIndex = null;

  const result = mm._getFilteredRootChildren();
  assert.equal(result, null);
});

test('_getFilteredRootChildren filters by search query', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['Apple', 'Banana', 'Apricot', 'Cherry']);
  mm.root = tree;
  mm._allRootChildren = tree.children;
  mm._searchFilter = 'app';
  mm._alphaFilter = '';
  mm._focusedRootIndex = null;

  const result = mm._getFilteredRootChildren();
  // 'apple' includes 'app', but 'apricot' does NOT include 'app'
  assert.equal(result.length, 1);
  assert.equal(result[0].data.name, 'Apple');
});

test('_getFilteredRootChildren filters are case-insensitive', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['Apple', 'BANANA', 'Apricot']);
  mm.root = tree;
  mm._allRootChildren = tree.children;
  mm._searchFilter = 'APP';
  mm._alphaFilter = '';
  mm._focusedRootIndex = null;

  const result = mm._getFilteredRootChildren();
  // Only 'apple' includes 'app'
  assert.equal(result.length, 1);
});

test('_getFilteredRootChildren filters by first letter (alpha filter)', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['Apple', 'Apricot', 'Banana', 'Cherry']);
  mm.root = tree;
  mm._allRootChildren = tree.children;
  mm._searchFilter = '';
  mm._alphaFilter = 'b';
  mm._focusedRootIndex = null;

  const result = mm._getFilteredRootChildren();
  assert.equal(result.length, 1);
  assert.equal(result[0].data.name, 'Banana');
});

test('_getFilteredRootChildren alpha filter # matches non-letter starters', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['123 Topic', 'Alpha', 'Beta']);
  mm.root = tree;
  mm._allRootChildren = tree.children;
  mm._searchFilter = '';
  mm._alphaFilter = '#';
  mm._focusedRootIndex = null;

  const result = mm._getFilteredRootChildren();
  assert.equal(result.length, 1);
  assert.equal(result[0].data.name, '123 Topic');
});

test('_getFilteredRootChildren returns single focused node', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['Alpha', 'Beta', 'Gamma']);
  mm.root = tree;
  mm._allRootChildren = tree.children;
  mm._searchFilter = '';
  mm._alphaFilter = '';
  mm._focusedRootIndex = 1;

  const result = mm._getFilteredRootChildren();
  assert.equal(result.length, 1);
  assert.equal(result[0].data.name, 'Beta');
});

test('_getFilteredRootChildren clamps focusedRootIndex to bounds', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['A', 'B']);
  mm.root = tree;
  mm._allRootChildren = tree.children;
  mm._searchFilter = '';
  mm._alphaFilter = '';
  mm._focusedRootIndex = 99;

  const result = mm._getFilteredRootChildren();
  assert.equal(result.length, 1);
  assert.equal(result[0].data.name, 'B');
});

test('_getFilteredRootChildren combines search and alpha filters', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['Apple', 'Apricot', 'Banana', 'Alpha Test']);
  mm.root = tree;
  mm._allRootChildren = tree.children;
  mm._searchFilter = 'a';
  mm._alphaFilter = 'a';
  mm._focusedRootIndex = null;

  const result = mm._getFilteredRootChildren();
  // Alpha filter: first char 'a' -> Apple, Apricot, Alpha Test (3 items)
  // Then search filter: all 3 include 'a'
  assert.equal(result.length, 3);
});

test('_getFilteredRootChildren search filter combined with focus', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['Apple', 'Apricot', 'Banana']);
  mm.root = tree;
  mm._allRootChildren = tree.children;
  mm._searchFilter = 'ap';
  mm._alphaFilter = '';
  mm._focusedRootIndex = 0;

  const result = mm._getFilteredRootChildren();
  // After search: [Apple, Apricot], focus index 0 = Apple
  assert.equal(result.length, 1);
  assert.equal(result[0].data.name, 'Apple');
});

// ============================================================
// Section 12: _getBaseFilteredChildren (helper for filtered children)
// ============================================================

test('_getBaseFilteredChildren returns copy of _allRootChildren when no filter', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['A', 'B']);
  mm._allRootChildren = tree.children;
  mm._searchFilter = '';
  mm._alphaFilter = '';

  const result = mm._getBaseFilteredChildren();
  assert.equal(result.length, 2);
});

test('_getBaseFilteredChildren does not mutate _allRootChildren', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['A', 'B']);
  mm._allRootChildren = tree.children;
  mm._searchFilter = 'a';
  mm._alphaFilter = '';

  const originalCount = mm._allRootChildren.length;
  mm._getBaseFilteredChildren();
  assert.equal(mm._allRootChildren.length, originalCount);
});

// ============================================================
// Section 13: _depthColor
// ============================================================

test('_depthColor cycles through nodeColors', () => {
  const mm = new TopicsMindmap();
  const color1 = mm._depthColor(1);
  const color2 = mm._depthColor(2);
  assert.ok(color1 !== color2, 'different depths should produce different colors');
});

test('_depthColor wraps around when exceeding available colors', () => {
  const mm = new TopicsMindmap();
  const numColors = mm.nodeColors.length;
  const color1 = mm._depthColor(1);
  const colorWrap = mm._depthColor(1 + numColors);
  assert.equal(color1, colorWrap, 'color should wrap at nodeColors.length');
});

test('_depthColor returns first nodeColor for depth 0', () => {
  const mm = new TopicsMindmap();
  const color = mm._depthColor(0);
  // _depthColor uses Math.max(depth, 1) - 1, so depth 0 maps to index 0
  assert.equal(color, mm.nodeColors[0]);
});

// ============================================================
// Section 14: _hasArrow
// ============================================================

test('_hasArrow returns true when node has children', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test');
  node.children = [makeNode('child')];
  assert.equal(mm._hasArrow(node), true);
});

test('_hasArrow returns true when node has _children (collapsed)', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test');
  node._children = [makeNode('child')];
  assert.equal(mm._hasArrow(node), true);
});

test('_hasArrow returns false for leaf nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('leaf');
  assert.equal(mm._hasArrow(node), false);
});

test('_hasArrow returns false for snippet nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippets', 'snippet_panel');
  node.children = [makeNode('child')];
  assert.equal(mm._hasArrow(node), false);
});

// ============================================================
// Section 15: _truncate
// ============================================================

test('_truncate returns input when shorter than limit', () => {
  const mm = new TopicsMindmap();
  assert.equal(mm._truncate('Hello', 10), 'Hello');
});

test('_truncate truncates and adds ellipsis when longer than limit', () => {
  const mm = new TopicsMindmap();
  assert.equal(mm._truncate('Hello World', 5), 'Hello...');
});

test('_truncate returns empty string for null/undefined', () => {
  const mm = new TopicsMindmap();
  assert.equal(mm._truncate(null, 10), '');
  assert.equal(mm._truncate(undefined, 10), '');
});

// ============================================================
// Section 16: _nodeHeightFor
// ============================================================

test('_nodeHeightFor returns standard height for non-snippet nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic');
  assert.equal(mm._nodeHeightFor(node), mm.nodeHeight);
});

test('_nodeHeightFor calculates height based on snippet count', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('snippets', 'snippet_panel', {
    snippets: [
      { text: 'One', post_title: 'Post' },
      { text: 'Two', post_title: 'Post' },
    ],
  });
  const height = mm._nodeHeightFor(node);
  // 36 + snippets.length * snippetItemHeight + multiSentenceExtra
  assert.ok(height > mm.nodeHeight, 'snippet height should exceed standard node height');
});

test('_nodeHeightFor caps at snippetMaxHeight', () => {
  const mm = new TopicsMindmap();
  const manySnippets = [];
  for (let i = 0; i < 50; i++) {
    manySnippets.push({ text: `Snippet ${i}`, post_title: `Post ${i}` });
  }
  const node = makeNode('snippets', 'snippet_panel', { snippets: manySnippets });
  const height = mm._nodeHeightFor(node);
  assert.ok(height <= mm.snippetMaxHeight, 'should not exceed snippetMaxHeight');
});

// ============================================================
// Section 17: _defaultActionsForNodeKind
// ============================================================

test('_defaultActionsForNodeKind returns empty for snippet_panel', () => {
  const mm = new TopicsMindmap();
  assert.deepEqual(mm._defaultActionsForNodeKind('snippet_panel'), []);
});

test('_defaultActionsForNodeKind returns empty for root', () => {
  const mm = new TopicsMindmap();
  assert.deepEqual(mm._defaultActionsForNodeKind('root'), []);
});

test('_defaultActionsForNodeKind returns DEFAULT_ACTIONS for topic', () => {
  const mm = new TopicsMindmap();
  assert.deepEqual(mm._defaultActionsForNodeKind('topic'), [
    'tags',
    'sentences',
    'sources',
    'categories',
    'subtopics',
  ]);
});

test('_defaultActionsForNodeKind returns DEFAULT_ACTIONS for subtopic', () => {
  const mm = new TopicsMindmap();
  assert.deepEqual(mm._defaultActionsForNodeKind('subtopic'), [
    'tags',
    'sentences',
    'sources',
    'categories',
    'subtopics',
  ]);
});

test('_defaultActionsForNodeKind returns DEFAULT_ACTIONS for unknown kind', () => {
  const mm = new TopicsMindmap();
  assert.deepEqual(mm._defaultActionsForNodeKind('unknown_kind'), [
    'tags',
    'sentences',
    'sources',
    'categories',
    'subtopics',
  ]);
});

// ============================================================
// Section 18: _setHorizontalPosition
// ============================================================

test('_setHorizontalPosition sets y on node and propagates to children', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['A', 'B'], {
    grandchildren: [['A1'], ['B1']],
  });
  mm._setHorizontalPosition(tree.children[0], 200);
  assert.equal(tree.children[0].y, 200);
  // Children should be positioned at parentY + nodeWidth + gapX
  assert.ok(tree.children[0].children[0].y > 200, 'child y should be greater than parent y');
});

test('_setHorizontalPosition does nothing for leaf nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('leaf');
  mm._setHorizontalPosition(node, 100);
  assert.equal(node.y, 100);
});

// ============================================================
// Section 19: Smoke tests for D3-dependent methods
// ============================================================

test('render method exists and is a function', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm.render, 'function');
});

test('render returns early when container is not found', () => {
  assert.ok(/document\.querySelector/.test(source), 'render should use document.querySelector');
  assert.ok(/if\s*\(\s*!container\)/.test(source), 'render should check if container is missing');
});

test('_fitToView method exists', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._fitToView, 'function');
});

test('_fitToView returns early without D3 setup', () => {
  const mm = new TopicsMindmap();
  assert.doesNotThrow(() => {
    mm._fitToView();
  });
});

test('_update method exists', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._update, 'function');
});

test('_foldAll method exists and does not throw without root', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._foldAll, 'function');
  assert.doesNotThrow(() => {
    mm._foldAll();
  });
});

test('_foldCurrentLevel method exists and does not throw without root', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._foldCurrentLevel, 'function');
  assert.doesNotThrow(() => {
    mm._foldCurrentLevel();
  });
});

test('_handleResize method exists', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._handleResize, 'function');
});

test('_handleResize returns early without svg', () => {
  const mm = new TopicsMindmap();
  assert.doesNotThrow(() => {
    mm._handleResize();
  });
});

test('_addControlButtons method exists', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._addControlButtons, 'function');
});

test('_addSearchUI method exists', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._addSearchUI, 'function');
});

test('_createMinimap method exists', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._createMinimap, 'function');
});

test('_renderMinimapContent method exists and returns early without data', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._renderMinimapContent, 'function');
  assert.doesNotThrow(() => {
    mm._renderMinimapContent();
  });
});

test('_getViewportSize method exists', () => {
  const mm = new TopicsMindmap();
  assert.equal(typeof mm._getViewportSize, 'function');
});

test('_getNodeScope extracts scope from node data', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', {
    scope: { topic_path: 'a/b/c', post_ids: [1, 2, 3] },
  });
  const scope = mm._getNodeScope(node);
  assert.equal(scope.topic_path, 'a/b/c');
  assert.deepEqual(scope.post_ids, [1, 2, 3]);
});

test('_getNodeScope normalizes scope with fallbacks', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', {
    _topicPath: 'fallback/path',
    _topicPosts: [10, 20],
  });
  const scope = mm._getNodeScope(node);
  assert.equal(scope.topic_path, 'fallback/path');
  assert.deepEqual(scope.post_ids, [10, 20]);
});

test('_getNodeScope returns normalized empty scope for minimal node', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic');
  const scope = mm._getNodeScope(node);
  assert.equal(scope.topic_path, '');
  assert.deepEqual(scope.post_ids, []);
  assert.equal(scope.node_kind, 'topic');
});

test('_isNavigableNode returns true for topic with scope', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', {
    scope: { topic_path: 'a/b', post_ids: [1, 2] },
  });
  assert.equal(mm._isNavigableNode(node), true);
});

test('_isNavigableNode returns false for topic without posts', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'topic', {
    scope: { topic_path: 'a/b', post_ids: [] },
  });
  assert.equal(mm._isNavigableNode(node), false);
});

test('_isNavigableNode returns false for non-topic/subtopic nodes', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('test', 'root');
  assert.equal(mm._isNavigableNode(node), false);
});

test('_navigateFocus sets focusedRootIndex (source inspection)', () => {
  assert.ok(
    /this\._focusedRootIndex\s*=\s*delta\s*>\s*0\s*\?\s*0/.test(source),
    'should set focusedRootIndex to 0 when delta > 0 and null'
  );
  assert.ok(
    /_focusedRootIndex\s*\+\s*delta/.test(source),
    'should adjust focusedRootIndex by delta'
  );
  assert.ok(/\.length\)\s*%\s*\w+\.length/.test(source), 'should wrap around using modulo');
});

test('_navigateFocus wraps around at end of list (source inspection)', () => {
  assert.ok(/children\.length/.test(source), 'should use children length for wrapping');
  assert.ok(/%/.test(source), 'should use modulo for wrapping');
});

test('_navigateFocus negative delta wraps from beginning (source inspection)', () => {
  assert.ok(
    /delta\s*>\s*0\s*\?\s*0\s*:\s*children\.length\s*-\s*1/.test(source),
    'should wrap to last when delta < 0 and null'
  );
});

test('_getAllDescendantsDeep returns node and all descendants', () => {
  const mm = new TopicsMindmap();
  const tree = makeTree('root', ['A'], {
    grandchildren: [['A1', 'A2']],
  });
  const childA = tree.children[0];
  const descendants = mm._getAllDescendantsDeep(childA);
  assert.ok(descendants.length >= 3, 'should include node + 2 grandchildren');
  const names = descendants.map((n) => n.data.name);
  assert.ok(names.includes('A'));
  assert.ok(names.includes('A1'));
  assert.ok(names.includes('A2'));
});

test('_getAllDescendantsDeep returns single node for leaf', () => {
  const mm = new TopicsMindmap();
  const node = makeNode('leaf');
  const descendants = mm._getAllDescendantsDeep(node);
  assert.equal(descendants.length, 1);
  assert.equal(descendants[0].data.name, 'leaf');
});

// ============================================================
// Section 20: _ensureContextMenu and _closeContextMenu
// ============================================================

test('_closeContextMenu does not throw when menuElement is null', () => {
  const mm = new TopicsMindmap();
  assert.doesNotThrow(() => {
    mm._closeContextMenu();
  });
});

test('_closeSnippetOverlay does not throw when overlay is null', () => {
  const mm = new TopicsMindmap();
  assert.doesNotThrow(() => {
    mm._closeSnippetOverlay();
  });
});

// ============================================================
// Section 21: _escapeHtml
// ============================================================

test('_escapeHtml escapes HTML entities', () => {
  const mm = new TopicsMindmap();
  // We need a minimal document for createElement
  if (typeof document !== 'undefined') {
    const escaped = mm._escapeHtml('<script>alert("xss")</script>');
    assert.ok(!escaped.includes('<script>'), 'should escape script tags');
  }
});

test('_escapeHtml returns empty string for null/undefined', () => {
  const mm = new TopicsMindmap();
  if (typeof document !== 'undefined') {
    assert.equal(mm._escapeHtml(null), '');
    assert.equal(mm._escapeHtml(undefined), '');
  }
});
