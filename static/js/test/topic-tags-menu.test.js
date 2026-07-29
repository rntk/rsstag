import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { FeedHierarchy } from '../components/feed-hierarchy.js';
import { FeedCanvas } from '../components/feed-canvas.js';

const TOPICS = [
  {
    name: 'Tech > AI',
    posts_count: 2,
    sentences_count: 2,
    sources: [
      {
        post_id: 'p1',
        title: 'First',
        sentences: [{ number: 1, text: 'Model news.', read: false }],
      },
      {
        post_id: 'p2',
        title: 'Second',
        sentences: [{ number: 2, text: 'More model news.', read: false }],
      },
    ],
  },
  {
    name: 'Tech > Hardware',
    posts_count: 1,
    sentences_count: 1,
    sources: [
      {
        post_id: 'p3',
        title: 'Third',
        sentences: [{ number: 1, text: 'Chip news.', read: false }],
      },
    ],
  },
];

function mockFetch() {
  const fetchMock = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: { tags: [], sentences_count: 0 } }),
    })
  );
  globalThis.fetch = fetchMock;
  return fetchMock;
}

describe('hierarchy topic menu', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <main id="feed_hierarchy" class="feed-hierarchy" tabindex="0">
        <div id="feed_hierarchy_levels" class="feed-hierarchy__levels"></div>
        <div id="feed_hierarchy_tree" class="feed-hierarchy__tree"></div>
      </main>`;
    window.hierarchyTopics = TOPICS;
    window.hierarchyOnlyUnread = false;
    window.TAG_WORDS = undefined;
    window.history.replaceState({}, '', '/hierarchy');
    mockFetch();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete globalThis.fetch;
  });

  it('offers a link to the topic snippets alongside its actions', () => {
    new FeedHierarchy().init();
    document.querySelector('.fh-leaf .fh-topic-menu').click();

    const items = [...document.querySelectorAll('.canvas-topic-menu button')];
    expect(items.map((item) => item.textContent)).toEqual(['Summary', 'Original', 'Tags']);
    const snippetsLink = document.querySelector('.canvas-topic-menu a');
    expect(snippetsLink.textContent).toBe('Open snippets');
    expect(snippetsLink.getAttribute('href')).toBe(
      '/topic-grouped-snippets?topic=Tech%20%3E%20AI'
    );
  });

  it('opens the tags dialog for the clicked topic and its posts', async () => {
    const fetchMock = mockFetch();
    new FeedHierarchy().init();
    document.querySelector('.fh-leaf .fh-topic-menu').click();
    [...document.querySelectorAll('.canvas-topic-menu button')]
      .find((button) => button.textContent === 'Tags')
      .click();

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/topic-tags');
    expect(JSON.parse(options.body)).toEqual({
      topic: 'Tech > AI',
      post_ids: ['p1', 'p2'],
    });
    expect(document.querySelector('.canvas-tags-dialog').open).toBe(true);
    // The menu closes as it does for the other items.
    expect(document.querySelector('.canvas-topic-menu')).toBeNull();
  });

  it('scopes a branch topic to every post below it', async () => {
    const fetchMock = mockFetch();
    new FeedHierarchy().init();
    document.querySelector('.fh-branch__label .fh-topic-menu').click();
    [...document.querySelectorAll('.canvas-topic-menu button')]
      .find((button) => button.textContent === 'Tags')
      .click();

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      topic: 'Tech',
      post_ids: ['p1', 'p2', 'p3'],
    });
  });

  it('links a branch topic to every snippet source below it', () => {
    new FeedHierarchy().init();
    document.querySelector('.fh-branch__label .fh-topic-menu').click();

    expect(document.querySelector('.canvas-topic-menu a').getAttribute('href')).toBe(
      '/topic-grouped-snippets?topic=Tech'
    );
  });
});

describe('canvas topic menu', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <main id="feed_canvas">
        <div id="feed_canvas_viewport">
          <div id="feed_canvas_document">
            <section id="canvas_posts">
              <article class="canvas-post" data-post-id="p1">
                <div class="canvas-post__text">
                  <span class="canvas-sentence" data-sentence-number="1">Model news.</span>
                </div>
              </article>
              <article class="canvas-post" data-post-id="p2">
                <div class="canvas-post__text">
                  <span class="canvas-sentence" data-sentence-number="2">More model news.</span>
                </div>
              </article>
            </section>
            <aside id="canvas_topic_rail"><div id="canvas_topic_cards"></div></aside>
          </div>
        </div>
      </main>
      <div id="canvas_levels"></div>`;
    window.canvasPosts = [
      { post_id: 'p1', read: false, groups: { 'Tech > AI': [1] } },
      { post_id: 'p2', read: false, groups: { 'Tech > AI': [2] } },
    ];
    mockFetch();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete globalThis.fetch;
  });

  /** @returns {{canvas: FeedCanvas, layout: object}} */
  function buildCanvasWithLayout(path = 'Tech > AI') {
    const canvas = new FeedCanvas();
    canvas.init();
    const layout = {
      node: canvas.nodes.find((node) => node.path === path),
      postId: 'p1',
      run: [1],
      top: 0,
      height: 40,
      left: 0,
      width: 100,
    };
    return { canvas, layout };
  }

  it('offers a link to the topic snippets alongside its actions', () => {
    const { canvas, layout } = buildCanvasWithLayout();
    const anchor = document.createElement('button');
    document.body.appendChild(anchor);
    canvas.openContextMenu(anchor, layout, document.createElement('div'));

    const items = [...document.querySelectorAll('.canvas-topic-menu button')];
    expect(items.map((item) => item.textContent)).toEqual(['Summary', 'Tags']);
    const snippetsLink = document.querySelector('.canvas-topic-menu a');
    expect(snippetsLink.textContent).toBe('Open snippets');
    expect(snippetsLink.getAttribute('href')).toBe(
      '/topic-grouped-snippets?topic=Tech%20%3E%20AI'
    );
  });

  it('sends every post of the topic node, not just the clicked run', async () => {
    const fetchMock = mockFetch();
    const { canvas, layout } = buildCanvasWithLayout();
    const anchor = document.createElement('button');
    document.body.appendChild(anchor);
    canvas.openContextMenu(anchor, layout, document.createElement('div'));
    [...document.querySelectorAll('.canvas-topic-menu button')]
      .find((button) => button.textContent === 'Tags')
      .click();

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      topic: 'Tech > AI',
      post_ids: ['p1', 'p2'],
    });
  });

  it('keeps the clicked topic even after the card is rebound to another layout', async () => {
    const fetchMock = mockFetch();
    const { canvas, layout } = buildCanvasWithLayout();
    const anchor = document.createElement('button');
    document.body.appendChild(anchor);
    const card = document.createElement('div');
    canvas.openContextMenu(anchor, layout, card);
    // Cards recycle: the layout the menu was opened for is replaced.
    layout.node = canvas.nodes.find((node) => node.path === 'Tech');
    [...document.querySelectorAll('.canvas-topic-menu button')]
      .find((button) => button.textContent === 'Tags')
      .click();

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).topic).toBe('Tech > AI');
  });
});
