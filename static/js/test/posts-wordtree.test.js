import { beforeEach, describe, expect, it } from 'vitest';
import PostsWordTree from '../components/posts-wordtree.js';

describe('legacy posts word tree', () => {
  let component;
  let events;
  beforeEach(() => {
    document.body.innerHTML = '<div id="posts-tree"></div>';
    events = {
      POSTS_UPDATED: 'posts',
      bind: (event, handler) => {
        events.handler = handler;
      },
    };
    component = new PostsWordTree('#posts-tree', events);
  });

  it('renders loaded posts with the shared SVG renderer', () => {
    component.start();
    events.handler({
      group: 'tag',
      group_title: 'love the',
      posts: new Map([[1, { post: { lemmas: 'love the lord thy god' } }]]),
    });
    expect(document.querySelector('svg')).not.toBeNull();
    expect(document.querySelector('.wordtree__root').textContent).toContain('love the');
    expect(document.querySelector('.wordtree__phrase').textContent).toContain('lord thy god');
  });

  it('updates rather than keeping stale posts', () => {
    component.updateWordTree({
      group: 'tag',
      group_title: 'cat',
      posts: [[1, { post: { lemmas: 'cat sleeps' } }]],
    });
    component.updateWordTree({
      group: 'tag',
      group_title: 'dog',
      posts: [[2, { post: { lemmas: 'dog runs' } }]],
    });
    expect(document.querySelectorAll('svg')).toHaveLength(1);
    expect(document.querySelector('.wordtree__root').textContent).toContain('dog');
  });

  it('skips category and feed groups and absent posts', () => {
    for (const group of ['category', 'feed']) {
      component.updateWordTree({
        group,
        group_title: 'cat',
        posts: [[1, { post: { lemmas: 'cat sleeps' } }]],
      });
    }
    component.updateWordTree({ group: 'tag', group_title: 'cat' });
    expect(document.querySelector('svg')).toBeNull();
  });

  it('clears the tree when posts become empty', () => {
    component.updateWordTree({
      group: 'tag',
      group_title: 'cat',
      posts: [[1, { post: { lemmas: 'cat sleeps' } }]],
    });
    component.updateWordTree({ group: 'tag', group_title: 'cat', posts: [] });
    expect(document.querySelector('svg')).toBeNull();
    expect(document.querySelector('#posts-tree').textContent).toBe('No texts');
  });
});

it('renders each group word when a multiword title has no exact phrase in lemmas', () => {
  document.body.innerHTML = '<div id="group-fallback"></div>';
  const component = new PostsWordTree('#group-fallback', {});
  component.updateWordTree({
    group: 'tag',
    group_title: 'cat dog',
    posts: new Map([[1, { post: { lemmas: 'cat sleeping and dog running' } }]]),
  });
  expect(
    Array.from(document.querySelectorAll('.wordtree__root'), (el) => el.childNodes[0].textContent)
  ).toEqual(['cat', 'dog']);
});
