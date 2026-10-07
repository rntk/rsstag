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
  return `${ids.map((id) => `<div id="${id}"${id === 'tag-explorer-posts' ? ' hidden' : ''}></div>`).join('')}
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

  it('renders the full post body and sentence text in their respective tabs', async () => {
    const body = 'Opening paragraph. ' + 'Full post text. '.repeat(60) + 'Closing paragraph.';
    const sentence = 'Full post text.';
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({
      total: 1,
      posts: [{ pid: 1, title: 'Example', url: '/posts/1', excerpt: body, read: false }],
      sentences: [{ pid: 1, title: 'Example', url: '/posts/1', text: sentence, number: 1, read: false }],
      page_size: 30, has_more: false, only_unread: false,
    }) })));
    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();

    const sentencesPanel = document.getElementById('tag-explorer-sentences');
    const postsPanel = document.getElementById('tag-explorer-posts');
    expect(sentencesPanel.querySelector('p').textContent).toBe(sentence);
    expect(postsPanel.hidden).toBe(true);
    document.getElementById('tag-explorer-posts-tab').click();
    expect(postsPanel.hidden).toBe(false);
    expect(sentencesPanel.hidden).toBe(true);
    expect(postsPanel.querySelector('p').textContent).toBe(body);
    expect(postsPanel.querySelector('a').getAttribute('href')).toBe('/posts/1');
    expect(sentencesPanel.querySelector('a').getAttribute('href')).toBe('/posts/1');
    expect(fetch).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it('shows an empty state when no grouped topics are available', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => resultFor({ kind: 'root' }) })));
    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();
    document.getElementById('tag-explorer-filter-topics-tab').click();
    expect(document.getElementById('tag-explorer-filter-topics').textContent).toContain('No grouped topics contain sentences mentioning this tag.');
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

  it('shows metadata and lazily shares related links between a post and its sentences', async () => {
    const metadata = { source: '<b>Source</b>', source_url: '/feed/source', provider: 'rss', date: '2026-09-28' };
    const post = { pid: 1, title: 'Title', url: '/posts/1', excerpt: 'codex', read: false, metadata };
    const fetchMock = vi.fn(async input => {
      if (String(input) === '/post-links/1') return { ok: true, json: async () => ({ data: {
        f_title: 'Source', f_url: '/feed/source', c_title: 'News', c_url: '/category/news',
        p_url: 'https://example.com', ctx_url: '/posts/1/10', clst_url: '/cluster/1',
        tags: [{ tag: '<script>tag</script>', url: '/tag/tag' }, { tag: 'unsafe', url: 'javascript:alert(1)' }],
        topics: [{ topic: 'Tech > AI', name: 'AI', url: '/topic/ai', snippets_url: '/snippets/ai' }],
      } }) };
      return { ok: true, json: async () => ({ total: 1, posts: [post],
        sentences: [{ ...post, text: 'codex sentence', number: 2 }], page_size: 30, has_more: false }) };
    });
    vi.stubGlobal('fetch', fetchMock);
    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();
    const sentence = document.querySelector('#tag-explorer-sentences article');
    expect(sentence.querySelector('.tag-explorer__metadata').textContent).toContain('<b>Source</b>rss2026-09-28Unread#2');
    expect(sentence.querySelector('.tag-explorer__metadata b')).toBeNull();
    const details = sentence.querySelector('details');
    expect(details.open).toBe(false);
    expect(details.parentElement).toBe(sentence.querySelector('.tag-explorer__metadata'));
    expect(sentence.querySelector(':scope > .tag-explorer__item-tools')).toBeNull();
    expect(details.contains(sentence.querySelector('.tag-explorer__read-button'))).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    details.open = true;
    details.dispatchEvent(new Event('toggle'));
    await settle();
    expect(sentence.querySelector('.tag-explorer__related-links').textContent).toContain('With contextCluster');
    expect(sentence.querySelector('.tag-explorer__related-links').textContent).toContain('Tech > AI');
    expect(sentence.querySelector('.tag-explorer__related-links script')).toBeNull();
    expect(sentence.querySelector('a[href^="javascript:"]')).toBeNull();
    const postDetails = document.querySelector('#tag-explorer-posts details');
    expect(postDetails.parentElement.className).toBe('tag-explorer__metadata');
    postDetails.open = true;
    postDetails.dispatchEvent(new Event('toggle'));
    await settle();
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === '/post-links/1')).toHaveLength(1);
    vi.unstubAllGlobals();
  });

  it('offers retry when related links fail without losing the excerpt', async () => {
    let attempts = 0;
    vi.stubGlobal('fetch', vi.fn(async input => {
      if (String(input) === '/post-links/1') {
        attempts += 1;
        if (attempts === 1) throw new Error('Links unavailable');
        return { ok: true, json: async () => ({ data: { tags: [], topics: [] } }) };
      }
      return { ok: true, json: async () => ({ total: 1, posts: [], sentences: [
        { pid: 1, title: 'Title', url: '/posts/1', text: 'codex sentence', number: 2, read: false },
      ], page_size: 30, has_more: false }) };
    }));
    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();
    const card = document.querySelector('#tag-explorer-sentences article');
    const details = card.querySelector('details');
    details.open = true;
    details.dispatchEvent(new Event('toggle'));
    await settle();
    expect(card.querySelector('p').textContent).toBe('codex sentence');
    const links = card.querySelector('.tag-explorer__related-links');
    expect(links.textContent).toContain('Links unavailable');
    links.querySelector('button').click();
    await settle();
    expect(links.textContent).toContain('Open post');
    expect(attempts).toBe(2);
    vi.unstubAllGlobals();
  });

  it('animates disclosure collapse and safely reverses a quick toggle', async () => {
    vi.stubGlobal('fetch', vi.fn(async input => {
      if (String(input) === '/post-links/1') return { ok: true, json: async () => ({ data: { tags: [], topics: [] } }) };
      return { ok: true, json: async () => resultFor({ kind: 'root' }) };
    }));
    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();
    const details = document.querySelector('#tag-explorer-posts details');
    const summary = details.querySelector('summary');
    const body = details.querySelector('.tag-explorer__item-tools-body');
    summary.click();
    await settle();
    expect(details.open).toBe(true);
    expect(details.classList.contains('is-expanded')).toBe(true);
    expect(body.inert).toBe(false);
    summary.click();
    expect(details.open).toBe(true);
    expect(details.classList.contains('is-expanded')).toBe(false);
    expect(body.inert).toBe(true);
    summary.click();
    await new Promise(resolve => setTimeout(resolve, 220));
    expect(details.open).toBe(true);
    expect(details.classList.contains('is-expanded')).toBe(true);
    expect(body.inert).toBe(false);
    summary.click();
    await new Promise(resolve => setTimeout(resolve, 220));
    expect(details.open).toBe(false);
    expect(details.classList.contains('is-expanded')).toBe(false);
    vi.unstubAllGlobals();
  });

  it('closes immediately when reduced motion is requested', async () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })));
    vi.stubGlobal('fetch', vi.fn(async input => {
      if (String(input) === '/post-links/1') return { ok: true, json: async () => ({ data: { tags: [], topics: [] } }) };
      return { ok: true, json: async () => resultFor({ kind: 'root' }) };
    }));
    window.eval(source);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await settle();
    const details = document.querySelector('#tag-explorer-posts details');
    details.querySelector('summary').click();
    await settle();
    details.querySelector('summary').click();
    expect(details.open).toBe(false);
    expect(details.classList.contains('is-expanded')).toBe(false);
    vi.unstubAllGlobals();
  });
});
