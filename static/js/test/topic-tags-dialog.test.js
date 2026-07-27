import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { TopicTagsDialog } from '../components/topic-tags.js';

const TAGS = [
  { tag: 'bank', url: '/tag-info/bank', count: 3, posts_count: 2 },
  { tag: 'rate', url: '/tag-info/rate', count: 1, posts_count: 1 },
];

function mockFetch(payload, { ok = true, status = 200 } = {}) {
  const fetchMock = vi.fn(() =>
    Promise.resolve({ ok, status, json: () => Promise.resolve(payload) })
  );
  globalThis.fetch = fetchMock;
  return fetchMock;
}

describe('TopicTagsDialog', () => {
  beforeEach(() => {
    document.body.replaceChildren();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete globalThis.fetch;
  });

  it('requests the topic scope and renders one link per tag', async () => {
    const fetchMock = mockFetch({ data: { tags: TAGS, sentences_count: 4 } });
    const dialog = new TopicTagsDialog();
    await dialog.open({ topic: 'Business>Finance', postIds: ['p1', 'p2', 'p1'] });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/topic-tags');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      topic: 'Business > Finance',
      post_ids: ['p1', 'p2'],
    });

    const links = [...document.querySelectorAll('.canvas-tags-dialog__link')];
    expect(links.map((link) => link.textContent)).toEqual(['bank', 'rate']);
    expect(links[0].getAttribute('href')).toBe('/tag-info/bank');
    expect(document.querySelector('.canvas-tags-dialog h2').textContent).toBe('Business > Finance');
    expect(document.querySelector('.canvas-tags-dialog').open).toBe(true);
  });

  it('falls back to a built tag-info url when the payload has none', async () => {
    mockFetch({ data: { tags: [{ tag: 'a b', count: 1 }], sentences_count: 1 } });
    const dialog = new TopicTagsDialog();
    await dialog.open({ topic: 'T', postIds: ['p1'] });

    expect(document.querySelector('.canvas-tags-dialog__link').getAttribute('href')).toBe(
      '/tag-info/a%20b'
    );
  });

  it('offers no read filter of its own', async () => {
    mockFetch({ data: { tags: [], sentences_count: 0 } });
    const dialog = new TopicTagsDialog();
    await dialog.open({ topic: 'T', postIds: ['p1'] });

    // The only-unread user setting is applied server-side.
    expect(document.querySelectorAll('.canvas-tags-dialog__filter')).toHaveLength(0);
  });

  it('filters the rendered list by the search term without refetching', async () => {
    const fetchMock = mockFetch({ data: { tags: TAGS, sentences_count: 4 } });
    const dialog = new TopicTagsDialog();
    await dialog.open({ topic: 'T', postIds: ['p1'] });

    const search = document.querySelector('.canvas-tags-dialog__search');
    search.value = 'rat';
    search.dispatchEvent(new window.Event('input'));

    expect(
      [...document.querySelectorAll('.canvas-tags-dialog__link')].map((link) => link.textContent)
    ).toEqual(['rate']);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('resets the search term on reopen', async () => {
    mockFetch({ data: { tags: TAGS, sentences_count: 4 } });
    const dialog = new TopicTagsDialog();
    await dialog.open({ topic: 'T', postIds: ['p1'] });
    const search = document.querySelector('.canvas-tags-dialog__search');
    search.value = 'rat';
    search.dispatchEvent(new window.Event('input'));

    await dialog.open({ topic: 'Other', postIds: ['p2'] });
    expect(search.value).toBe('');
    expect(document.querySelectorAll('.canvas-tags-dialog__link')).toHaveLength(2);
  });

  it('reuses one dialog element across topics', async () => {
    mockFetch({ data: { tags: TAGS, sentences_count: 4 } });
    const dialog = new TopicTagsDialog();
    await dialog.open({ topic: 'A', postIds: ['p1'] });
    await dialog.open({ topic: 'B', postIds: ['p2'] });

    expect(document.querySelectorAll('.canvas-tags-dialog')).toHaveLength(1);
  });

  it('reports an empty result instead of an error', async () => {
    mockFetch({ data: { tags: [], sentences_count: 0 } });
    const dialog = new TopicTagsDialog();
    await dialog.open({ topic: 'T', postIds: ['p1'] });

    const status = document.querySelector('.canvas-tags-dialog__status');
    expect(status.textContent).toContain('no sentences');
    expect(status.classList.contains('is-error')).toBe(false);
  });

  it('shows the server error message when the request fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    mockFetch({ error: 'Unable to load topic tags' }, { ok: false, status: 500 });
    const dialog = new TopicTagsDialog();
    await dialog.open({ topic: 'T', postIds: ['p1'] });

    const status = document.querySelector('.canvas-tags-dialog__status');
    expect(status.textContent).toBe('Unable to load topic tags');
    expect(status.classList.contains('is-error')).toBe(true);
  });

  it('does not call the endpoint when the topic covers no posts', async () => {
    const fetchMock = mockFetch({ data: { tags: [], sentences_count: 0 } });
    const dialog = new TopicTagsDialog();
    await dialog.open({ topic: 'T', postIds: [] });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(document.querySelector('.canvas-tags-dialog__status').textContent).toContain('No posts');
  });

  it('keeps the newest response when an older one resolves last', async () => {
    const responses = [
      { data: { tags: TAGS, sentences_count: 4 } },
      { data: { tags: [{ tag: 'fresh', count: 1, posts_count: 1 }], sentences_count: 1 } },
    ];
    let call = 0;
    const resolvers = [];
    globalThis.fetch = vi.fn(() => {
      const payload = responses[call];
      call += 1;
      return new Promise((resolve) => {
        resolvers.push(() =>
          resolve({ ok: true, status: 200, json: () => Promise.resolve(payload) })
        );
      });
    });

    const dialog = new TopicTagsDialog();
    const first = dialog.open({ topic: 'T', postIds: ['p1'] });
    // Reopening on another topic supersedes the request still in flight.
    const second = dialog.open({ topic: 'Other', postIds: ['p2'] });
    // Resolve the newest request first, the stale one after it.
    resolvers[1]();
    await vi.waitFor(() =>
      expect(document.querySelector('.canvas-tags-dialog__link')?.textContent).toBe('fresh')
    );
    resolvers[0]();
    await Promise.all([first, second]);

    expect(
      [...document.querySelectorAll('.canvas-tags-dialog__link')].map((link) => link.textContent)
    ).toEqual(['fresh']);
  });
});
