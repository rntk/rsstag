import { describe, it, expect, beforeEach } from 'vitest';

import {
  buildTopicTree,
  getMaxTopicLevel,
  collectNonLeafPaths,
  hashString,
  highlightColor,
  accentColor,
  formatLeafMeta,
  collectOriginalSources,
  getUrlTagParam,
  getTagHighlightWords,
  buildTagHighlightRe,
  fillHighlightedText,
  renderTree,
  renderLevelButtons,
  FeedHierarchy,
} from '../components/feed-hierarchy.js';

const TOPICS = [
  { name: 'Tech > AI > LLMs', posts_count: 3, sentences_count: 12 },
  { name: 'Tech > AI > Agents', posts_count: 1, sentences_count: 4 },
  { name: 'Tech > Hardware', posts_count: 2, sentences_count: 7 },
  { name: 'Politics', posts_count: 5, sentences_count: 20 },
];

describe('buildTopicTree', () => {
  it('builds roots from flat topic paths and merges shared prefixes', () => {
    const roots = buildTopicTree(TOPICS);
    expect(roots.map((entry) => entry.node.name)).toEqual(['Tech', 'Politics']);

    const tech = roots[0];
    expect(Array.from(tech.children.keys())).toEqual(['AI', 'Hardware']);
    const ai = tech.children.get('AI');
    expect(Array.from(ai.children.keys())).toEqual(['LLMs', 'Agents']);
  });

  it('trims path parts and skips empty segments', () => {
    const roots = buildTopicTree([{ name: '  A  >  B  ' }, { name: 'A > > C' }]);
    expect(roots).toHaveLength(1);
    expect(roots[0].node.name).toBe('A');
    expect(Array.from(roots[0].children.keys())).toEqual(['B', 'C']);
  });

  it('sets fullPath, uid and depth on each node', () => {
    const roots = buildTopicTree(TOPICS);
    const llms = roots[0].children.get('AI').children.get('LLMs');
    expect(llms.node.fullPath).toBe('Tech>AI>LLMs');
    expect(llms.node.uid).toBe('Tech>AI>LLMs');
    expect(llms.node.depth).toBe(2);
  });

  it('attaches the topic object to the terminal node only', () => {
    const roots = buildTopicTree(TOPICS);
    const tech = roots[0];
    expect(tech.node.topic).toBeNull();
    const llms = tech.children.get('AI').children.get('LLMs');
    expect(llms.node.topic).toEqual(TOPICS[0]);
  });

  it('computes leafCount recursively', () => {
    const roots = buildTopicTree(TOPICS);
    const tech = roots[0];
    expect(tech.leafCount).toBe(3);
    expect(tech.children.get('AI').leafCount).toBe(2);
    expect(roots[1].leafCount).toBe(1);
  });

  it('returns an empty array for non-array or empty input', () => {
    expect(buildTopicTree(undefined)).toEqual([]);
    expect(buildTopicTree([])).toEqual([]);
  });
});

describe('getMaxTopicLevel', () => {
  it('returns the deepest zero-based depth', () => {
    expect(getMaxTopicLevel(TOPICS)).toBe(2);
  });

  it('returns 0 for flat topics or empty input', () => {
    expect(getMaxTopicLevel([{ name: 'One' }, { name: 'Two' }])).toBe(0);
    expect(getMaxTopicLevel([])).toBe(0);
    expect(getMaxTopicLevel(undefined)).toBe(0);
  });
});

describe('collectNonLeafPaths', () => {
  it('collects every branch path in pre-order', () => {
    const roots = buildTopicTree(TOPICS);
    expect(collectNonLeafPaths(roots)).toEqual(['Tech', 'Tech>AI']);
  });

  it('respects minDepth so only deeper branches fold', () => {
    const roots = buildTopicTree(TOPICS);
    expect(collectNonLeafPaths(roots, { minDepth: 1 })).toEqual(['Tech>AI']);
    expect(collectNonLeafPaths(roots, { minDepth: 2 })).toEqual([]);
  });

  it('minDepth 0 folds the tree to the top level only', () => {
    const roots = buildTopicTree(TOPICS);
    const collapsed = new Set(collectNonLeafPaths(roots, { minDepth: 0 }));
    expect(collapsed.has('Tech')).toBe(true);
    expect(collapsed.has('Tech>AI')).toBe(true);
  });

  it('handles non-array input', () => {
    expect(collectNonLeafPaths(undefined)).toEqual([]);
  });
});

describe('color helpers', () => {
  it('hashString is deterministic and non-negative', () => {
    expect(hashString('Tech')).toBe(hashString('Tech'));
    expect(hashString('Tech')).toBeGreaterThanOrEqual(0);
    expect(hashString('abc')).not.toBe(hashString('xyz'));
  });

  it('highlightColor and accentColor return deterministic HSL strings', () => {
    expect(highlightColor('Tech', 1)).toBe(highlightColor('Tech', 1));
    expect(highlightColor('Tech', 0)).toMatch(/^hsl\(\d+, \d+%, \d+%\)$/);
    expect(accentColor('Tech', 0)).toMatch(/^hsl\(\d+, \d+%, \d+%\)$/);
  });

  it('highlightColor gets lighter with depth', () => {
    const lightness = (color) => parseInt(color.match(/(\d+)%\)$/)[1], 10);
    expect(lightness(highlightColor('Tech', 4))).toBeGreaterThanOrEqual(
      lightness(highlightColor('Tech', 0))
    );
  });
});

describe('formatLeafMeta', () => {
  it('formats posts and sentences counts', () => {
    expect(formatLeafMeta({ posts_count: 3, sentences_count: 12 })).toBe('3 posts · 12 sentences');
  });

  it('uses singular labels for counts of one', () => {
    expect(formatLeafMeta({ posts_count: 1, sentences_count: 1 })).toBe('1 post · 1 sentence');
  });

  it('defaults missing counts to zero', () => {
    expect(formatLeafMeta(null)).toBe('0 posts · 0 sentences');
  });
});

describe('collectOriginalSources', () => {
  it('keeps sentences grouped by source and merges repeated posts', () => {
    const roots = buildTopicTree([
      {
        name: 'News > AI',
        sources: [
          { post_id: 'post-1', title: 'First post', sentences: ['First sentence.'] },
          { post_id: 'post-2', title: 'Second post', sentences: ['Second sentence.'] },
        ],
      },
      {
        name: 'News > Hardware',
        sources: [{ post_id: 'post-1', title: 'First post', sentences: ['Third sentence.'] }],
      },
    ]);

    expect(collectOriginalSources(roots[0])).toEqual([
      {
        post_id: 'post-1',
        title: 'First post',
        url: '',
        sentences: [
          { text: 'First sentence.', read: false },
          { text: 'Third sentence.', read: false },
        ],
      },
      {
        post_id: 'post-2',
        title: 'Second post',
        url: '',
        sentences: [{ text: 'Second sentence.', read: false }],
      },
    ]);
  });

  it('falls back to topic sentences for older hierarchy payloads', () => {
    const roots = buildTopicTree([{ name: 'News', sentences: ['Original sentence.'] }]);
    expect(collectOriginalSources(roots[0])[0].sentences).toEqual([
      { text: 'Original sentence.', read: false },
    ]);
  });
});

describe('renderLevelButtons', () => {
  it('renders maxLevel+1 buttons and marks the selected one active', () => {
    const container = document.createElement('div');
    renderLevelButtons(container, 2, 1, () => {});
    const buttons = container.querySelectorAll('button');
    expect(buttons).toHaveLength(3);
    expect([...buttons].map((button) => button.textContent)).toEqual(['1', '2', '3']);
    expect(buttons[1].classList.contains('is-active')).toBe(true);
    expect(buttons[0].classList.contains('is-active')).toBe(false);
  });

  it('invokes onSelect with the zero-based level on click', () => {
    const container = document.createElement('div');
    const selected = [];
    renderLevelButtons(container, 2, 2, (level) => selected.push(level));
    container.querySelectorAll('button')[0].click();
    expect(selected).toEqual([0]);
  });
});

describe('renderTree', () => {
  it('renders an empty-state message when there are no topics', () => {
    const container = document.createElement('div');
    renderTree(container, [], new Set(), () => {});
    const empty = container.querySelector('.fh-empty');
    expect(empty).toBeTruthy();
    expect(empty.textContent).toBe('No topics have been processed for this feed yet.');
  });

  it('renders branches with toggles and leaves with labels and actions', () => {
    const container = document.createElement('div');
    const roots = buildTopicTree(TOPICS);
    renderTree(container, roots, new Set(), () => {});

    const branchLabels = [...container.querySelectorAll('.fh-branch__label-text')].map(
      (el) => el.textContent
    );
    expect(branchLabels).toEqual(['Tech', 'AI']);

    const leafLabels = [...container.querySelectorAll('.fh-leaf__label')].map(
      (el) => el.textContent
    );
    expect(leafLabels).toEqual(['LLMs', 'Agents', 'Hardware', 'Politics']);

    const llmsLeaf = [...container.querySelectorAll('.fh-leaf')].find(
      (el) => el.querySelector('.fh-leaf__label').textContent === 'LLMs'
    );
    expect(llmsLeaf.querySelector('.fh-leaf__meta')).toBeNull();
    expect(llmsLeaf.querySelector('.fh-topic-menu')).toBeTruthy();
  });

  it('renders a clickable original-sentence preview beside each leaf', () => {
    const container = document.createElement('div');
    const roots = buildTopicTree([
      { name: 'News', sources: [{ sentences: ['The original sentence.'] }] },
    ]);
    const opened = [];
    renderTree(container, roots, new Set(), () => {}, () => {}, (entry) => opened.push(entry));

    const preview = container.querySelector('.fh-leaf-sentences');
    expect(preview?.textContent).toBe('The original sentence.');
    preview.click();
    expect(opened).toEqual([roots[0]]);
  });

  it('highlights the URL tag inside leaf sentence previews', () => {
    const container = document.createElement('div');
    const roots = buildTopicTree([
      { name: 'News', sources: [{ sentences: ['Learning Python is fun.'] }] },
    ]);
    renderTree(
      container,
      roots,
      new Set(),
      () => {},
      () => {},
      () => {},
      buildTagHighlightRe('python')
    );

    const preview = container.querySelector('.fh-leaf-sentences');
    expect(preview?.textContent).toBe('Learning Python is fun.');
    const marks = preview?.querySelectorAll('.canvas-original-sentence__tag') || [];
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe('Python');
  });

  it('renders a collapsed branch as a single row without children', () => {
    const container = document.createElement('div');
    const roots = buildTopicTree(TOPICS);
    renderTree(container, roots, new Set(['Tech>AI']), () => {});

    const collapsed = container.querySelector('.fh-branch--collapsed');
    expect(collapsed).toBeTruthy();
    expect(collapsed.querySelector('.fh-branch__children')).toBeNull();
    expect(collapsed.querySelector('.fh-toggle').getAttribute('aria-expanded')).toBe('false');
    expect(container.querySelectorAll('.fh-leaf')).toHaveLength(2);
  });

  it('applies deterministic per-topic colors to cards', () => {
    const container = document.createElement('div');
    const roots = buildTopicTree(TOPICS);
    renderTree(container, roots, new Set(), () => {});
    const techLabel = container.querySelector('.fh-branch__label');
    expect(techLabel.style.getPropertyValue('--fh-accent-color')).toBe(accentColor('Tech', 0));
    expect(techLabel.style.getPropertyValue('--fh-card-bg')).toBe(highlightColor('Tech', 0));
  });
});

describe('FeedHierarchy (DOM smoke test)', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <main id="feed_hierarchy" class="feed-hierarchy" tabindex="0">
        <div id="feed_hierarchy_levels" class="feed-hierarchy__levels"></div>
        <div id="feed_hierarchy_tree" class="feed-hierarchy__tree"></div>
      </main>`;
    window.hierarchyTopics = TOPICS;
    window.TAG_WORDS = undefined;
    window.history.replaceState({}, '', '/hierarchy');
  });

  it('renders level buttons and a fully unfolded tree by default', () => {
    new FeedHierarchy().init();

    const buttons = document.querySelectorAll('#feed_hierarchy_levels button');
    expect(buttons).toHaveLength(3);
    expect(buttons[2].classList.contains('is-active')).toBe(true);

    const tree = document.getElementById('feed_hierarchy_tree');
    expect(tree.querySelectorAll('.fh-leaf')).toHaveLength(4);
    expect(tree.querySelector('.fh-branch--collapsed')).toBeNull();
  });

  it('folds the tree when a shallower level is selected', () => {
    new FeedHierarchy().init();
    document.querySelectorAll('#feed_hierarchy_levels button')[0].click();

    const tree = document.getElementById('feed_hierarchy_tree');
    // Level 1: every branch collapsed, only root rows visible.
    expect(tree.querySelectorAll('.fh-branch--collapsed')).toHaveLength(1);
    const collapsedText = tree.querySelector('.fh-branch--collapsed .fh-branch__label-text');
    expect(collapsedText.textContent).toBe('Tech');
    // "Politics" is a root leaf and stays visible.
    expect([...tree.querySelectorAll('.fh-leaf__label')].map((el) => el.textContent)).toEqual([
      'Politics',
    ]);

    const buttons = document.querySelectorAll('#feed_hierarchy_levels button');
    expect(buttons[0].classList.contains('is-active')).toBe(true);
    expect(buttons[2].classList.contains('is-active')).toBe(false);
  });

  it('toggle button collapses and re-expands a branch', () => {
    new FeedHierarchy().init();
    const tree = document.getElementById('feed_hierarchy_tree');

    const aiToggle = [...tree.querySelectorAll('.fh-branch')]
      .find((el) => el.querySelector('.fh-branch__label-text').textContent === 'AI')
      .querySelector('.fh-toggle');
    aiToggle.click();

    expect(tree.querySelectorAll('.fh-branch--collapsed')).toHaveLength(1);
    expect([...tree.querySelectorAll('.fh-leaf__label')].map((el) => el.textContent)).toEqual([
      'Hardware',
      'Politics',
    ]);

    // Re-expand.
    tree.querySelector('.fh-branch--collapsed .fh-toggle').click();
    expect(tree.querySelectorAll('.fh-branch--collapsed')).toHaveLength(0);
    expect(tree.querySelectorAll('.fh-leaf')).toHaveLength(4);
  });

  it('shows an empty-state message when there are no topics', () => {
    window.hierarchyTopics = [];
    new FeedHierarchy().init();
    const empty = document.querySelector('#feed_hierarchy_tree .fh-empty');
    expect(empty).toBeTruthy();
    expect(empty.textContent).toBe('No topics have been processed for this feed yet.');
  });

  it('adds Original alongside Summary in the topic context menu', () => {
    new FeedHierarchy().init();
    document.querySelector('.fh-topic-menu').click();

    expect([...document.querySelectorAll('.canvas-topic-menu button')].map((button) => button.textContent)).toEqual([
      'Summary',
      'Original',
    ]);
  });

  it('renders read controls for original sentences', () => {
    const hierarchy = new FeedHierarchy();
    const source = hierarchy.buildOriginalSource(
      {
        post_id: 'post-1',
        title: 'First post',
        sentences: [
          { number: 1, text: 'Unread sentence.', read: false },
          { number: 2, text: 'Read sentence.', read: true },
        ],
      },
      0
    );

    expect(source.querySelectorAll('.canvas-original-sentence')).toHaveLength(2);
    expect([...source.querySelectorAll('.canvas-original-sentence__toggle')].map((button) => button.textContent)).toEqual([
      'Mark Read',
      'Mark Unread',
    ]);
    expect(source.querySelectorAll('.canvas-original-sentence.is-read')).toHaveLength(1);
  });

  it('opens the Original dialog from a leaf sentence preview', () => {
    window.hierarchyTopics = [
      { name: 'News', sources: [{ title: 'Post', sentences: ['The original sentence.'] }] },
    ];
    new FeedHierarchy().init();

    document.querySelector('.fh-leaf-sentences').click();
    expect(document.querySelector('.canvas-original-dialog').open).toBe(true);
  });

  it('highlights the URL tag inside Original sentence text', () => {
    window.TAG_WORDS = undefined;
    window.history.replaceState({}, '', '/hierarchy?tag=python');
    const hierarchy = new FeedHierarchy();
    const source = hierarchy.buildOriginalSource(
      {
        post_id: 'post-1',
        title: 'First post',
        sentences: [
          { number: 1, text: 'Learning Python is fun.', read: false },
          { number: 2, text: 'No match here.', read: false },
        ],
      },
      0
    );

    const marks = source.querySelectorAll('.canvas-original-sentence__tag');
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe('Python');
    expect(source.querySelectorAll('.canvas-original-sentence')[1].querySelectorAll('mark')).toHaveLength(0);
  });

  it('highlights lemma surface forms from TAG_WORDS metadata', () => {
    window.history.replaceState({}, '', '/hierarchy?tag=run');
    window.TAG_WORDS = ['run', 'running', 'ran'];
    const hierarchy = new FeedHierarchy();
    const source = hierarchy.buildOriginalSource(
      {
        post_id: 'post-1',
        title: 'First post',
        sentences: [
          { number: 1, text: 'She is running now.', read: false },
          { number: 2, text: 'He ran yesterday.', read: false },
          { number: 3, text: 'They walk often.', read: false },
        ],
      },
      0
    );

    const marks = [...source.querySelectorAll('.canvas-original-sentence__tag')].map(
      (mark) => mark.textContent
    );
    expect(marks).toEqual(['running', 'ran']);
  });
});

describe('tag highlight helpers', () => {
  it('getUrlTagParam reads and trims the tag query value', () => {
    window.history.replaceState({}, '', '/hierarchy?tag=%20machine+learning%20');
    expect(getUrlTagParam()).toBe('machine learning');
    window.history.replaceState({}, '', '/hierarchy');
    expect(getUrlTagParam()).toBe('');
  });

  it('getTagHighlightWords prefers TAG_WORDS over the URL tag', () => {
    window.history.replaceState({}, '', '/hierarchy?tag=run');
    window.TAG_WORDS = ['run', 'running', 'ran', 'run'];
    expect(getTagHighlightWords()).toEqual(['run', 'running', 'ran']);

    window.TAG_WORDS = [];
    expect(getTagHighlightWords()).toEqual(['run']);

    window.TAG_WORDS = undefined;
    window.history.replaceState({}, '', '/hierarchy');
    expect(getTagHighlightWords()).toEqual([]);
  });

  it('buildTagHighlightRe matches whole words case-insensitively', () => {
    const re = buildTagHighlightRe('AI');
    expect(re).toBeInstanceOf(RegExp);
    expect('AI agents'.match(re)).toEqual(['AI']);
    expect('the ai model'.match(re)).toEqual(['ai']);
    expect('AIs'.match(re)).toBeNull();
    expect(buildTagHighlightRe('')).toBeNull();
    expect(buildTagHighlightRe(['running', 'ran']).test('She is running')).toBe(true);
  });

  it('fillHighlightedText wraps matches in mark nodes without using HTML', () => {
    const el = document.createElement('span');
    fillHighlightedText(el, 'Hello <python> and PYTHON', buildTagHighlightRe('python'));
    expect(el.textContent).toBe('Hello <python> and PYTHON');
    expect([...el.querySelectorAll('mark')].map((mark) => mark.textContent)).toEqual(['python', 'PYTHON']);
  });
});
