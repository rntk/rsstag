import { describe, it, expect, beforeEach } from 'vitest';
import { FeedHierarchy } from '../components/feed-hierarchy.js';

function topic(name, text, snippet, number = 1) {
  return {
    name,
    word_chain: true,
    posts_count: 1,
    sentences_count: 1,
    sources: [
      { post_id: 'post-1', title: 'Post', sentences: [{ number, text, snippet, read: false }] },
    ],
  };
}

beforeEach(() => {
  document.body.innerHTML =
    '<main id="feed_hierarchy" data-hierarchy-kind="words"><a id="hierarchy_switch" href="/hierarchy"></a><div id="feed_hierarchy_levels"></div><div id="feed_hierarchy_tree"></div></main>';
  window.history.replaceState({}, '', '/tag-hierarchy?tag=codex&feed=one');
  window.hierarchyOnlyUnread = false;
  window.TAG_WORDS = ['codex'];
});

describe('tag word hierarchy', () => {
  it('shows snippets, opens full originals, and preserves scope in the switch', () => {
    const full = 'This full codex CLI tool sentence is much longer than the preview.';
    window.hierarchyTopics = [topic('codex > cli > tool', full, 'codex CLI tool')];
    const hierarchy = new FeedHierarchy();
    hierarchy.init();
    expect(document.querySelector('.fh-leaf-sentences').textContent).toBe('codex CLI tool');
    expect(document.querySelector('#hierarchy_switch').search).toBe('?tag=codex&feed=one');
    document.querySelector('.fh-leaf-sentences').click();
    expect(document.querySelector('.canvas-original-sentence__text').textContent).toBe(full);
  });

  it('keeps originals for shorter chains that are also parents', () => {
    window.hierarchyTopics = [
      topic('codex > cli', 'CLI codex', 'CLI codex'),
      topic('codex > cli > tool', 'codex CLI tool', 'codex CLI tool', 2),
    ];
    new FeedHierarchy().init();
    expect(
      [...document.querySelectorAll('.fh-leaf-sentences')].map((el) => el.textContent)
    ).toEqual(['CLI codex', 'codex CLI tool']);
  });

  it('deduplicates full ungrouped posts when opening a shared parent', () => {
    const full = 'codex CLI tool and CLI codex app';
    window.hierarchyTopics = [
      topic('codex > cli > tool', full, 'codex CLI tool', null),
      topic('codex > cli > app', full, 'CLI codex app', null),
    ];
    const hierarchy = new FeedHierarchy();
    hierarchy.init();
    hierarchy.showOriginal(hierarchy.roots[0]);
    expect(document.querySelectorAll('.canvas-original-sentence__text')).toHaveLength(1);
    expect(document.querySelector('.canvas-original-sentence__text').textContent).toBe(full);
  });

  it('bounds the combined preview and provides a word-specific empty state', () => {
    window.hierarchyTopics = [topic('codex > tool', 'codex full', 'x'.repeat(600))];
    new FeedHierarchy().init();
    expect(document.querySelector('.fh-leaf-sentences').textContent.length).toBe(481);
    document.body.querySelectorAll('dialog').forEach((el) => el.remove());
    window.hierarchyTopics = [];
    new FeedHierarchy().init();
    expect(document.querySelector('.fh-empty').textContent).toBe(
      'No matching word chains in this scope.'
    );
  });
});
