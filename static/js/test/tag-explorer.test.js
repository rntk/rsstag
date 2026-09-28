import { beforeEach, describe, expect, it, vi } from 'vitest';
import source from '../tag-explorer.js?raw';

function pageMarkup() {
  const ids = [
    'tag-explorer-root', 'tag-explorer-filter-tabs', 'tag-explorer-tree',
    'tag-explorer-status', 'tag-explorer-sentences', 'tag-explorer-posts',
    'tag-explorer-sentences-tab', 'tag-explorer-posts-tab', 'tag-explorer-previous',
    'tag-explorer-next', 'tag-explorer-page', 'tag-explorer-read-page', 'tag-explorer-unread-page',
    'tag-explorer-read-all', 'tag-explorer-unread-all',
    'tag-explorer-selection-label', 'tag-explorer-selection', 'tag-explorer-read-filter',
  ];
  return `${ids.map((id) => `<div id="${id}"></div>`).join('')}
    <button id="tag-explorer-clear-filter" hidden>Clear branch filter</button>
    <script id="tag-explorer-data" type="application/json">${JSON.stringify({
      name: 'codex',
      count: 10,
      context: [{
        name: 'cli', count: 5, occurrences: 5,
        children: [{
          name: 'tool', count: 3, occurrences: 3,
          children: [{ name: 'extra', count: 2, occurrences: 2, children: [] }],
        }],
      }],
    })}</script>`;
}

function resultFor(selection) {
  const total = selection.kind === 'root' ? 10 : selection.chain.length === 1 ? 5 : selection.chain.length === 2 ? 3 : 2;
  return {
    total,
    posts: Array.from({ length: total }, (_, index) => ({
      pid: index + 1, title: `Post ${index + 1}`, url: `/post/${index + 1}`,
      excerpt: 'codex cli tool', read: false,
    })),
    sentences: [],
    page_size: 40,
    has_more: false,
  };
}

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('tag explorer context tree', () => {
  beforeEach(() => {
    document.body.innerHTML = pageMarkup();
    window.history.replaceState({}, '', '/tag-explorer/codex');
    vi.restoreAllMocks();
  });

  it('renders one lazy context tree and filters posts by each selected chain prefix', async () => {
    const requests = [];
    vi.stubGlobal('fetch', vi.fn(async (input) => {
      const url = new URL(String(input), window.location.origin);
      const selection = JSON.parse(url.searchParams.get('selection'));
      requests.push(selection);
      return { ok: true, json: async () => resultFor(selection) };
    }));

    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();

    const filterTabs = document.getElementById('tag-explorer-filter-tabs');
    expect(filterTabs.querySelectorAll('[role="tab"]')).toHaveLength(2);
    expect(filterTabs.textContent).toContain('Context chain');
    expect(document.querySelectorAll('.tag-explorer__section-body')).toHaveLength(2);
    expect(document.querySelectorAll('.tag-explorer__node-label')).toHaveLength(2);
    expect([...document.querySelectorAll('.tag-explorer__node-label')].map((button) => button.textContent))
      .toEqual(['codex', 'cli']);
    expect(document.getElementById('tag-explorer-selection').textContent).toBe('All branches');
    expect(document.getElementById('tag-explorer-read-filter').textContent).toBe('Read and unread');
    expect(document.getElementById('tag-explorer-clear-filter').hidden).toBe(true);

    const cliBranch = document.querySelector('.tag-explorer__toggle[aria-label="Expand cli"]');
    expect(cliBranch).not.toBeNull();
    cliBranch.click();
    const cliButton = [...document.querySelectorAll('.tag-explorer__node-label')]
      .find((button) => button.textContent === 'cli');
    expect(cliButton).toBeDefined();
    cliButton.click();
    await settle();
    expect(requests.at(-1)).toEqual({ kind: 'context', chain: ['cli'] });
    const cliRow = cliButton.closest('.tag-explorer__node');
    const cliProgress = cliRow.querySelector('progress');
    expect(cliProgress.value).toBe(5);
    expect(cliProgress.max).toBe(10);
    expect(cliProgress.getAttribute('aria-label')).toBe('5 of 10 parent posts');

    cliButton.closest('.tag-explorer__node').querySelector('.tag-explorer__toggle').click();
    const toolButton = [...document.querySelectorAll('.tag-explorer__node-label')]
      .find((button) => button.textContent === 'tool');
    expect(toolButton).toBeDefined();
    toolButton.click();
    await settle();
    expect(requests.at(-1)).toEqual({ kind: 'context', chain: ['cli', 'tool'] });

    toolButton.closest('.tag-explorer__node').querySelector('.tag-explorer__toggle').click();
    const extraButton = [...document.querySelectorAll('.tag-explorer__node-label')]
      .find((button) => button.textContent === 'extra');
    expect(extraButton).toBeDefined();
    extraButton.click();
    await settle();
    expect(requests.at(-1)).toEqual({ kind: 'context', chain: ['cli', 'tool', 'extra'] });
    expect(document.getElementById('tag-explorer-selection-label').textContent).toBe('Context chain');
    expect(document.getElementById('tag-explorer-selection').textContent)
      .toBe('codex → cli → tool → extra (either side of the tag)');
    cliBranch.click();
    document.getElementById('tag-explorer-posts-tab').click();
    expect(document.getElementById('tag-explorer-selection').textContent)
      .toBe('codex → cli → tool → extra (either side of the tag)');

    document.getElementById('tag-explorer-clear-filter').click();
    await settle();
    expect(requests.at(-1)).toEqual({ kind: 'root' });
    expect(document.getElementById('tag-explorer-selection').textContent).toBe('All branches');
    expect(document.getElementById('tag-explorer-clear-filter').hidden).toBe(true);
    expect(document.querySelectorAll('.tag-explorer__node-label.is-active')).toHaveLength(1);
    expect(document.activeElement).toBe(document.querySelector('#tag-explorer-root .tag-explorer__node-label'));
    vi.unstubAllGlobals();
  });
  it('switches topic tabs and selects parent and nested topic filters', async () => {
    const data = document.getElementById('tag-explorer-data');
    const tree = JSON.parse(data.textContent);
    tree.topics = [{ name: 'Tech', count: 5, children: [{ name: 'AI', count: 3, children: [] }] }];
    data.textContent = JSON.stringify(tree);
    const requests = [];
    vi.stubGlobal('fetch', vi.fn(async input => {
      const selection = JSON.parse(new URL(String(input), window.location.origin).searchParams.get('selection'));
      requests.push(selection);
      return { ok: true, json: async () => resultFor(selection) };
    }));
    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();
    const contextPanel = document.getElementById('tag-explorer-filter-context');
    const topicsPanel = document.getElementById('tag-explorer-filter-topics');
    expect(topicsPanel.hidden).toBe(true);
    const topicsTab = document.getElementById('tag-explorer-filter-topics-tab');
    topicsTab.click();
    expect(contextPanel.hidden).toBe(true);
    expect(topicsPanel.hidden).toBe(false);
    expect(topicsTab.getAttribute('aria-selected')).toBe('true');
    topicsPanel.querySelector('.tag-explorer__node-label').click();
    await settle();
    expect(requests.at(-1)).toEqual({ kind: 'topic', chain: ['Tech'] });
    topicsPanel.querySelector('.tag-explorer__toggle').click();
    [...topicsPanel.querySelectorAll('.tag-explorer__node-label')].find(button => button.textContent === 'AI').click();
    await settle();
    expect(requests.at(-1)).toEqual({ kind: 'topic', chain: ['Tech', 'AI'] });
    expect(document.getElementById('tag-explorer-selection-label').textContent).toBe('Topic');
    expect(document.getElementById('tag-explorer-selection').textContent).toBe('Tech → AI (including subtopics)');
    topicsTab.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
    expect(contextPanel.hidden).toBe(false);
    expect(topicsPanel.hidden).toBe(true);
    expect(document.getElementById('tag-explorer-selection').textContent).toBe('Tech → AI (including subtopics)');
    contextPanel.querySelector('.tag-explorer__node-label').click();
    await settle();
    expect(document.getElementById('tag-explorer-selection-label').textContent).toBe('Context chain');
    expect(document.getElementById('tag-explorer-selection').textContent).toBe('codex → cli (either side of the tag)');
    vi.unstubAllGlobals();
  });

  it('shows an empty state when no grouped topics are available', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => resultFor({ kind: 'root' }) })));
    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();
    document.getElementById('tag-explorer-filter-topics-tab').click();
    expect(document.getElementById('tag-explorer-filter-topics').textContent).toContain('No grouped topics available');
    vi.unstubAllGlobals();
  });
  it('marks only the current page with page buttons and every page with all buttons', async () => {
    const marked = [];
    const pagePosts = [{ pid: 1, title: 'Post 1', url: '/post/1', excerpt: 'codex', read: false }];
    vi.stubGlobal('fetch', vi.fn(async (input, options) => {
      if (options && options.method === 'POST') {
        marked.push({ url: String(input), body: JSON.parse(options.body) });
        return { ok: true, json: async () => ({ data: 'ok' }) };
      }
      const url = new URL(String(input), window.location.origin);
      if (url.searchParams.get('scope') === 'all') {
        return { ok: true, json: async () => ({
          total: 3, sentences: [],
          posts: [{ pid: 1, read: false }, { pid: 2, read: true }, { pid: 41, read: false }],
        }) };
      }
      return { ok: true, json: async () => ({
        total: 3, posts: pagePosts, sentences: [], page_size: 40, has_more: false, only_unread: false,
      }) };
    }));

    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();
    document.getElementById('tag-explorer-posts-tab').click();

    document.getElementById('tag-explorer-read-page').click();
    await settle();
    expect(marked.at(-1)).toEqual({ url: '/read/posts', body: { ids: [1], readed: true } });

    document.getElementById('tag-explorer-read-all').click();
    await settle();
    await settle();
    expect(marked.at(-1)).toEqual({ url: '/read/posts', body: { ids: [1, 41], readed: true } });

    document.getElementById('tag-explorer-unread-all').click();
    await settle();
    await settle();
    expect(marked.at(-1)).toEqual({ url: '/read/posts', body: { ids: [2], readed: false } });
    vi.unstubAllGlobals();
  });

  it('disables unread all when only unread posts are shown', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({
      total: 1, posts: [{ pid: 1, title: 'P', url: '/post/1', excerpt: 'x', read: false }],
      sentences: [], page_size: 40, has_more: false, only_unread: true,
    }) })));

    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();

    expect(document.getElementById('tag-explorer-read-all').disabled).toBe(false);
    expect(document.getElementById('tag-explorer-unread-all').disabled).toBe(true);
    expect(document.getElementById('tag-explorer-read-filter').textContent).toBe('Unread only');
    vi.unstubAllGlobals();
  });

  it('keeps the selected filters visible while loading and after a failed request', async () => {
    document.getElementById('tag-explorer-read-filter').dataset.onlyUnread = 'true';
    const data = document.getElementById('tag-explorer-data');
    const tree = JSON.parse(data.textContent);
    tree.context[0].name = '<b>cli</b>';
    data.textContent = JSON.stringify(tree);
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('Could not load results.'); }));
    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();

    document.querySelector('#tag-explorer-filter-context .tag-explorer__node-label').click();
    const summary = document.getElementById('tag-explorer-selection');
    expect(summary.textContent).toBe('codex → <b>cli</b> (either side of the tag)');
    expect(summary.querySelector('b')).toBeNull();
    expect(document.getElementById('tag-explorer-read-filter').textContent).toBe('Unread only');
    await settle();
    expect(document.getElementById('tag-explorer-status').textContent).toBe('Could not load results.');
    expect(summary.textContent).toBe('codex → <b>cli</b> (either side of the tag)');
    vi.unstubAllGlobals();
  });
});
