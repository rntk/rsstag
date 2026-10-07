import React from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PostTopics from '../components/post-topics.js';

const TOPIC = {
  name: 'Animals > Cats',
  posts_count: 1,
  sentences_count: 1,
  sentences: ['Cats sleep a lot.'],
  sources: [
    {
      post_id: '7',
      title: 'Cat post',
      url: '',
      feed_title: '',
      feed_url: '',
      sentences: [{ number: 0, text: 'Cats sleep a lot.', read: false }],
    },
  ],
};

describe('inline topics tab', () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(async () => {
    root.unmount();
    container.remove();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // React's act() is unavailable in this setup, so wait for the DOM instead.
  async function render(props, selector = '.post-topics, [role="alert"]') {
    root.render(React.createElement(PostTopics, props));
    await vi.waitFor(() => expect(container.querySelector(selector)).not.toBeNull());
  }

  function respond(data) {
    fetch.mockResolvedValue({ ok: true, json: async () => ({ data }) });
  }

  it('requests topics of the listed posts filtered by the page tag', async () => {
    respond({ topics: [TOPIC], tag_words: ['cats'], only_unread: false });
    await render({ postIds: [7, 8], tag: 'cat' });
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/api/posts-topics');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ post_ids: [7, 8], tag: 'cat' });
  });

  it('renders the hierarchy tree and level buttons in place', async () => {
    respond({ topics: [TOPIC], tag_words: ['cats'], only_unread: false });
    await render({ postIds: [7], tag: null });
    expect(JSON.parse(fetch.mock.calls[0][1].body).tag).toBe('');
    expect(container.querySelector('.feed-hierarchy__tree').textContent).toContain('Animals');
    expect(container.querySelectorAll('.feed-hierarchy__levels button').length).toBeGreaterThan(0);
  });

  it('removes its dialogs when unmounted', async () => {
    respond({ topics: [TOPIC], tag_words: [], only_unread: false });
    await render({ postIds: [7] });
    expect(document.querySelectorAll('dialog').length).toBeGreaterThan(0);
    root.unmount();
    expect(document.querySelectorAll('dialog').length).toBe(0);
    root = createRoot(container);
  });

  it('shows a retry button when the request fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    fetch.mockResolvedValue({ ok: false, status: 500 });
    await render({ postIds: [7] });
    expect(container.querySelector('[role="alert"]').textContent).toContain(
      'Unable to load topics'
    );
    respond({ topics: [], tag_words: [], only_unread: false });
    container.querySelector('button').click();
    await vi.waitFor(() => expect(container.querySelector('.post-topics')).not.toBeNull());
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
