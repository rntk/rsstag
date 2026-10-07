import { describe, it, expect, beforeEach } from 'vitest';
import { buildWordTree, tokenize } from '../libs/wordtree-layout.js';
import WordTree from '../components/wordtree.js';

describe('word tree contexts', () => {
  it('merges shared phrases and counts repeated occurrences', () => {
    const tree = buildWordTree(
      ['love the lord thy god', 'love the lord your god', 'love the lord thy god'],
      'love the'
    );
    expect(tree.occurrences).toBe(3);
    expect(tree.root.label).toBe('love the');
    expect(tree.root.children[0].label).toBe('lord');
    expect(tree.root.children[0].children.map((child) => [child.label, child.count])).toEqual([
      ['thy god', 2],
      ['your god', 1],
    ]);
  });

  it('matches whole tokens, Unicode, and case without matching substrings', () => {
    const tree = buildWordTree(['CAT cats catapult cat café', 'КОТ спит кот ест'], 'cat');
    expect(tree.occurrences).toBe(2);
    expect(buildWordTree(['КОТ спит кот ест'], 'кот').occurrences).toBe(2);
    expect(tokenize('café, déjà-vu')).toEqual(['café', ',', 'déjà-vu']);
  });

  it('preserves endings at shared prefixes', () => {
    const tree = buildWordTree(['tag one', 'tag one two'], 'tag');
    expect(tree.root.children[0].label).toBe('one');
    expect(tree.root.children[0].count).toBe(2);
    expect(tree.root.children[0].children[0].label).toBe('two');
  });

  it('builds preceding phrases in reading order', () => {
    const tree = buildWordTree(['we love the lord', 'they love the lord'], 'lord', true);
    expect(tree.root.children[0].label).toBe('love the');
    expect(tree.root.children[0].children.map((child) => child.label).sort()).toEqual([
      'they',
      'we',
    ]);
  });

  it('bounds large diagrams while reporting all occurrences', () => {
    const texts = Array.from({ length: 200 }, (_, i) => `tag context${i}`);
    const tree = buildWordTree(texts, 'tag');
    expect(tree.occurrences).toBe(200);
    expect(tree.shownPaths).toBe(120);
    expect(tree.totalPaths).toBe(200);
    expect(tree.root.children).toHaveLength(120);
  });

  it('handles empty tags, absent matches and tags at text boundaries', () => {
    expect(buildWordTree(['text'], '').occurrences).toBe(0);
    expect(buildWordTree(['text'], 'missing').occurrences).toBe(0);
    expect(buildWordTree(['tag'], 'tag').occurrences).toBe(1);
    expect(buildWordTree(['tag'], 'tag').root.children).toEqual([]);
  });
});

describe('custom SVG word tree', () => {
  let component;
  let eventSystem;
  beforeEach(() => {
    document.body.innerHTML = '<div id="tree"></div>';
    eventSystem = {
      WORDTREE_TEXTS_UPDATED: 'updated',
      bind: (event, handler) => {
        eventSystem.handler = handler;
      },
    };
    component = new WordTree('#tree', eventSystem);
  });

  it('renders SVG branches and updates through the existing event interface', () => {
    component.start();
    eventSystem.handler({
      tag: 'love the',
      texts: ['love the lord thy god', 'love the lord your god'],
    });
    expect(document.querySelector('svg')).not.toBeNull();
    expect(document.querySelectorAll('path')).toHaveLength(3);
    expect(document.querySelector('.wordtree__root').textContent).toContain('love the');
    expect(document.querySelector('.wordtree__summary').textContent).toBe('2 occurrences');
  });

  it('changes direction and replaces previous drawings', () => {
    component.updateWordTree({ tag: 'lord', texts: ['we love the lord thy god'] });
    const select = document.querySelector('select');
    select.value = 'before';
    select.dispatchEvent(new window.Event('change'));
    expect(document.querySelector('.wordtree__phrase').textContent).toContain('we love the');
    expect(document.querySelectorAll('svg')).toHaveLength(1);
  });

  it('renders untrusted labels as text', () => {
    component.updateWordTree({ tag: '<img>', texts: ['<img> hello'] });
    expect(document.querySelector('img')).toBeNull();
    expect(document.querySelector('.wordtree__root').textContent).toContain('<img>');
  });

  it('shows empty states and clears stale diagrams', () => {
    component.updateWordTree({ tag: 'tag', texts: ['tag context'] });
    component.updateWordTree({ tag: 'tag', texts: [] });
    expect(document.querySelector('svg')).toBeNull();
    expect(document.querySelector('#tree').textContent).toBe('No texts');
    component.updateWordTree({ tag: 'tag', texts: ['no match'] });
    expect(document.querySelector('.tag-info-empty-state').textContent).toContain(
      'No matching contexts'
    );
  });
});

it('accepts an element container for embedded trees', () => {
  document.body.innerHTML = '<div id="embedded"></div>';
  const container = document.querySelector('#embedded');
  const component = new WordTree(container, {});
  component.updateWordTree({ tag: 'tag', texts: ['tag shared branch'] });
  expect(container.querySelector('svg')).not.toBeNull();
});

it('uses a readable layout when rendering inside a hidden section', () => {
  document.body.innerHTML = '<div id="hidden-tree" hidden></div>';
  const original = window.SVGElement.prototype.getComputedTextLength;
  window.SVGElement.prototype.getComputedTextLength = () => 0;
  try {
    const component = new WordTree('#hidden-tree', {});
    component.updateWordTree({ tag: 'tag', texts: ['tag shared branch'] });
    const root = document.querySelector('.wordtree__root');
    const phrase = document.querySelector('.wordtree__phrase');
    expect(Number(phrase.getAttribute('x'))).toBeGreaterThan(Number(root.getAttribute('x')) + 100);
  } finally {
    if (original) window.SVGElement.prototype.getComputedTextLength = original;
    else delete window.SVGElement.prototype.getComputedTextLength;
  }
});

it('falls back to separate word trees when group words never appear adjacently', () => {
  document.body.innerHTML = '<div id="fallback"></div>';
  const component = new WordTree('#fallback', {});
  component.updateWordTree({ tag: 'cat dog', texts: ['we see cat sleeping and dog running'] });
  expect(
    Array.from(document.querySelectorAll('.wordtree__root'), (el) => el.childNodes[0].textContent)
  ).toEqual(['cat', 'dog']);
  expect(document.querySelector('.wordtree__summary').textContent).toBe(
    'Individual word contexts · cat: 1 occurrence · dog: 1 occurrence'
  );
  const direction = document.querySelector('select');
  direction.value = 'before';
  direction.dispatchEvent(new window.Event('change'));
  expect(document.querySelectorAll('svg')).toHaveLength(2);
  expect(document.querySelector('.wordtree__phrase').textContent).toContain('we see');
});

it('keeps an exact phrase as one tree even if its words also appear separately', () => {
  document.body.innerHTML = '<div id="phrase"></div>';
  const component = new WordTree('#phrase', {});
  component.updateWordTree({
    tag: 'cat dog',
    texts: ['cat dog running', 'cat sleeping dog running'],
  });
  expect(document.querySelectorAll('svg')).toHaveLength(1);
  expect(document.querySelector('.wordtree__root').childNodes[0].textContent).toBe('cat dog');
  expect(document.querySelector('.wordtree__summary').textContent).toBe('1 occurrence');
});

it('deduplicates fallback words case-insensitively and skips unmatched words', () => {
  document.body.innerHTML = '<div id="partial"></div>';
  const component = new WordTree('#partial', {});
  component.updateWordTree({ tag: 'cat CAT missing', texts: ['cat sleeping'] });
  expect(document.querySelectorAll('svg')).toHaveLength(1);
  expect(document.querySelector('.wordtree__summary').textContent).toBe(
    'Individual word contexts · CAT: 1 occurrence'
  );
  component.updateWordTree({ tag: 'missing absent', texts: ['cat sleeping'] });
  expect(document.querySelector('svg')).toBeNull();
  expect(document.querySelector('.tag-info-empty-state').textContent).toContain(
    'No matching contexts'
  );
});
