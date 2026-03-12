import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

function extractExportedFunction(source, name) {
  const start = source.indexOf(`export function ${name}`);
  if (start === -1) {
    throw new Error(`Unable to find function ${name}`);
  }

  const bodyStart = source.indexOf('{', start);
  let depth = 0;
  let end = bodyStart;

  for (; end < source.length; end += 1) {
    const char = source[end];
    if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        break;
      }
    }
  }

  return source.slice(start, end + 1).replace('export function', 'function');
}

function loadAppFunctions(contextOverrides = {}) {
  const source = fs.readFileSync(new URL('../apps/app.js', import.meta.url), 'utf8');
  const functionNames = ['resolvePageType', 'initSnippetHoverCards', 'initSentenceClusterPage'];
  const scriptSource = [
    ...functionNames.map((name) => extractExportedFunction(source, name)),
    'module.exports = { resolvePageType, initSnippetHoverCards, initSentenceClusterPage };',
  ].join('\n\n');

  const context = {
    module: { exports: {} },
    exports: {},
    window: {},
    document: {},
    TopicsMindmap: class TopicsMindmap {},
    ...contextOverrides,
  };

  vm.runInNewContext(scriptSource, context);
  return context.module.exports;
}

function createClassList(initial = []) {
  const classes = new Set(initial);
  return {
    add(name) {
      classes.add(name);
    },
    contains(name) {
      return classes.has(name);
    },
    toggle(name, force) {
      if (force === undefined) {
        if (classes.has(name)) {
          classes.delete(name);
          return false;
        }
        classes.add(name);
        return true;
      }

      if (force) {
        classes.add(name);
      } else {
        classes.delete(name);
      }
      return force;
    },
  };
}

function createElement({ attrs = {}, classes = [] } = {}) {
  const listeners = new Map();
  const attrMap = new Map(Object.entries(attrs));

  return {
    classList: createClassList(classes),
    addEventListener(eventName, callback) {
      listeners.set(eventName, callback);
    },
    trigger(eventName) {
      const handler = listeners.get(eventName);
      if (handler) {
        handler();
      }
    },
    getAttribute(name) {
      return attrMap.has(name) ? attrMap.get(name) : null;
    },
    setAttribute(name, value) {
      attrMap.set(name, value);
    },
    hasAttribute(name) {
      return attrMap.has(name);
    },
  };
}

test('resolvePageType handles expected routes and fallback', () => {
  const { resolvePageType } = loadAppFunctions();
  const cases = [
    ['/', 'root'],
    ['/post-compare/demo', 'post-compare'],
    ['/post-grouped/demo', 'post-grouped'],
    ['/s-tree/demo', 's-tree'],
    ['/sunburst/demo', 'sunburst'],
    ['/tree/demo', 'tree'],
    ['/prefixes/prefix/demo', 'tree'],
    ['/group/category', 'group-category'],
    ['/group/tag/demo', 'tags-group'],
    ['/group/bi-grams/demo', 'bigrams-group'],
    ['/feed', 'posts-list'],
    ['/category/news', 'posts-list'],
    ['/posts/demo', 'posts-list'],
    ['/tag-info/demo', 'tag-info'],
    ['/map', 'map'],
    ['/tag-net', 'tag-net'],
    ['/topics-mindmap', 'topics-mindmap'],
    ['/sentence-clusters', 'sentence-clusters'],
    ['/sentence-clusters/123', 'sentence-cluster'],
    ['/topics-list', 'topics-list'],
    ['/topics-list/123', 'topics-list'],
    ['/paths/sentences/demo', 'path-sentences'],
    ['/paths/posts/demo', 'path-posts'],
    ['/unknown/path', 'unknown'],
  ];

  for (const [path, expected] of cases) {
    assert.equal(resolvePageType(path), expected, `Unexpected page type for ${path}`);
  }
});

test('initSnippetHoverCards sets tabindex when missing, preserves existing tabindex, and adds class', () => {
  const firstCard = createElement();
  const secondCard = createElement({ attrs: { tabindex: '4' } });

  const documentStub = {
    querySelectorAll(selector) {
      assert.equal(selector, '.snippet-item');
      return [firstCard, secondCard];
    },
  };

  const { initSnippetHoverCards } = loadAppFunctions({ document: documentStub });
  initSnippetHoverCards();

  assert.equal(firstCard.getAttribute('tabindex'), '0');
  assert.equal(secondCard.getAttribute('tabindex'), '4');
  assert.equal(firstCard.classList.contains('snippet-hover-card'), true);
  assert.equal(secondCard.classList.contains('snippet-hover-card'), true);
});

test('initSentenceClusterPage toggles active tabs and lazily renders mindmap on demand', () => {
  const snippetsTab = createElement({ attrs: { 'data-tab': 'snippets' } });
  const groupsTab = createElement({ attrs: { 'data-tab': 'groups-mind-map' } });
  const snippetsPane = createElement();
  const groupsPane = createElement();
  const tabsContainer = {
    querySelectorAll(selector) {
      assert.equal(selector, '.sentence-cluster-tab-btn');
      return [snippetsTab, groupsTab];
    },
  };

  const chartContainer = createElement();
  const renderCalls = [];
  class TopicsMindmapStub {
    render(...args) {
      renderCalls.push(args);
    }
  }

  const documentStub = {
    getElementById(id) {
      const elements = {
        sentence_cluster_tabs: tabsContainer,
        sentence_cluster_tab_snippets: snippetsPane,
        sentence_cluster_tab_groups_mind_map: groupsPane,
        sentence_cluster_mindmap_chart: chartContainer,
      };
      return elements[id] || null;
    },
  };

  const windowStub = {
    sentence_cluster_mindmap_data: { name: 'root' },
    sentence_cluster_id: 123,
  };

  const { initSentenceClusterPage } = loadAppFunctions({
    document: documentStub,
    window: windowStub,
    TopicsMindmap: TopicsMindmapStub,
  });

  initSentenceClusterPage();
  assert.equal(renderCalls.length, 0);

  snippetsTab.trigger('click');
  assert.equal(snippetsTab.classList.contains('active'), true);
  assert.equal(groupsTab.classList.contains('active'), false);
  assert.equal(snippetsPane.classList.contains('active'), true);
  assert.equal(groupsPane.classList.contains('active'), false);
  assert.equal(renderCalls.length, 0);

  groupsTab.trigger('click');
  assert.equal(snippetsTab.classList.contains('active'), false);
  assert.equal(groupsTab.classList.contains('active'), true);
  assert.equal(snippetsPane.classList.contains('active'), false);
  assert.equal(groupsPane.classList.contains('active'), true);
  assert.equal(renderCalls.length, 1);
  assert.equal(renderCalls[0][0], '#sentence_cluster_mindmap_chart');
  assert.deepEqual(renderCalls[0][1], { name: 'root' });

  groupsTab.trigger('click');
  assert.equal(renderCalls.length, 1);
});

test('initSentenceClusterPage is a no-op when tabs container is missing', () => {
  const { initSentenceClusterPage } = loadAppFunctions({
    document: {
      getElementById() {
        return null;
      },
    },
  });

  assert.doesNotThrow(() => {
    initSentenceClusterPage();
  });
});
