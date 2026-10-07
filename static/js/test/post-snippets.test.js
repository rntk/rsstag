import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PostSnippets from '../components/post-snippets.js';

describe('inline snippets tab', () => {
  let container;
  let root;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    delete window.TAG_WORDS;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  async function render(url = '/tag-grouped-snippets/cat?feed=one') {
    await act(async () => root.render(React.createElement(PostSnippets, { url })));
  }

  function respond(html) {
    fetch.mockResolvedValue({ ok: true, text: async () => html });
  }

  it('renders only the snippet section and keeps matching words and actions', async () => {
    respond(`<html><body><header>Other page navigation</header>
      <div id="snippets_container" data-tag-words='["cats"]'>
        <div class="snippet-item"><mark>cats</mark><button class="toggle-read-btn">Mark Read</button></div>
      </div><script>window.unwanted = true;</script></body></html>`);
    await render();
    expect(fetch.mock.calls[0][0]).toBe('/tag-grouped-snippets/cat?feed=one');
    expect(container.querySelector('mark').textContent).toBe('cats');
    expect(container.querySelector('.toggle-read-btn')).not.toBeNull();
    expect(container.querySelectorAll('.batch-read-btn')).toHaveLength(2);
    expect(container.textContent).not.toContain('Other page navigation');
    expect(container.querySelector('script')).toBeNull();
    expect(window.TAG_WORDS).toEqual(['cats']);
    expect(container.querySelector('a').getAttribute('href')).toBe(
      '/tag-grouped-snippets/cat?feed=one'
    );
  });

  it('groups the same post across topics and keeps excerpt actions and identity', async () => {
    /** @param {string} post @param {string} index @param {string} title @returns {string} */
    function snippet(post, index, title) {
      return `<div class="snippet-item" id="snippet_${post}_${index}" data-post-id="${post}"
        data-base-indices="${index}" data-visible-indices="${index}">
        <div class="snippet-meta"><span class="snippet-primary-meta">From
          <span class="snippet-source-info">${title}</span></span>
          <span class="snippet-actions">
            <span class="toggle-read-btn" data-post-id="${post}" data-indices="${index}" data-read="0">Mark Read</span>
            <a class="snippet-tag-context" href="/posts/${post}">Show full post</a>
            <a class="snippet-tag-original" href="https://example.com/${post}" target="_blank">Original</a>
            <button class="extend-snippet-context-btn" data-post-id="${post}">Extend context</button>
            <button class="show-snippet-tags-btn" data-post-id="${post}">Show tags</button>
          </span></div>
        <div class="snippet-text"><div class="snippet-context-base">Excerpt ${index}</div></div>
        <div class="snippet-tags-content hide"></div></div>`;
    }
    respond(`<div id="snippets_container">
      <div class="topic-card"><span class="topic-title">Science</span>
        ${snippet('one', '1', 'Shared article')}${snippet('two', '2', 'Other article')}</div>
      <div class="topic-card"><span class="topic-title">Technology</span>
        ${snippet('one', '3', 'Shared article')}</div></div>`);
    await render();
    const groups = container.querySelectorAll('.post-snippets__post');
    expect(groups).toHaveLength(2);
    expect([...groups].map((group) => group.dataset.postId)).toEqual(['one', 'two']);
    expect(groups[0].querySelectorAll('.snippet-item')).toHaveLength(2);
    expect(groups[0].querySelector('.post-snippets__post-title').textContent).toBe(
      'Shared article'
    );
    expect(groups[0].querySelector('.post-snippets__post-count').textContent).toBe('2 snippets');
    expect(groups[1].querySelector('.post-snippets__post-count').textContent).toBe('1 snippet');
    expect(
      [...groups[0].querySelectorAll('.post-snippets__topic')].map((el) => el.textContent)
    ).toEqual(['Science', 'Technology']);
    expect(groups[0].querySelectorAll('.snippet-tag-context')).toHaveLength(1);
    expect(groups[0].querySelector('.snippet-tag-original').rel).toBe('noopener noreferrer');
    expect(container.querySelector('.post-snippets__summary').textContent).toContain(
      '3 snippets from 2 posts'
    );
    const excerpt = container.querySelector('#snippet_one_3');
    expect(excerpt.dataset.baseIndices).toBe('3');
    expect(excerpt.dataset.visibleIndices).toBe('3');
    expect(excerpt.querySelector('.toggle-read-btn').dataset.indices).toBe('3');
    expect(excerpt.querySelector('.toggle-read-btn').tagName).toBe('BUTTON');
    expect(excerpt.querySelector('.extend-snippet-context-btn')).not.toBeNull();
    expect(excerpt.querySelector('.show-snippet-tags-btn')).not.toBeNull();
    expect(excerpt.querySelector('.snippet-tags-content')).not.toBeNull();
  });

  it('preserves the server empty state', async () => {
    respond('<div id="snippets_container"><p>No matching snippets found.</p></div>');
    await render('/entity-grouped-snippets/red%20fox?window=3');
    expect(container.textContent).toContain('No matching snippets found.');
    expect(window.TAG_WORDS).toEqual([]);
  });

  it('shows an error for an unexpected response and allows retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    respond('<html><body>Login page</body></html>');
    await render();
    expect(container.querySelector('[role="alert"]').textContent).toContain(
      'Unable to load snippets'
    );
    respond('<div id="snippets_container">Loaded after retry</div>');
    await act(async () => container.querySelector('button').click());
    expect(container.textContent).toContain('Loaded after retry');
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('aborts a pending request when leaving the tab', async () => {
    fetch.mockImplementation(() => new Promise(() => {}));
    await render();
    expect(container.querySelector('[role="status"]').textContent).toBe('Loading snippets…');
    const signal = fetch.mock.calls[0][1].signal;
    await act(async () => root.render(null));
    expect(signal.aborted).toBe(true);
  });
});
