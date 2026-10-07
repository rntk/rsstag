import { beforeEach, describe, expect, it } from 'vitest';
import TopicsTexts from '../components/topics-texts.js';

describe('topic text trees', () => {
  let component;
  let events;
  beforeEach(() => {
    document.body.innerHTML = '<div id="topics"></div>';
    events = {
      TOPICS_TEXTS_UPDATED: 'topics',
      bind: (event, handler) => {
        events.handler = handler;
      },
    };
    component = new TopicsTexts('#topics', events);
  });

  it('renders a custom tree for each topic through the event interface', () => {
    component.start();
    events.handler({ topics: ['cat', 'dog'], texts: ['cat sleeps dog runs'] });
    expect(document.querySelectorAll('svg')).toHaveLength(2);
    expect(
      Array.from(document.querySelectorAll('.wordtree__root'), (el) => el.childNodes[0].textContent)
    ).toEqual(['cat', 'dog']);
  });

  it('counts occurrences once without duplicating overlapping context windows', () => {
    component.updateData({ topics: ['cat'], texts: ['cat sees cat'] });
    expect(document.querySelector('.wordtree__summary').textContent).toBe('2 occurrences');
  });

  it('replaces previous topics on updates and clears empty data', () => {
    component.updateData({ topics: ['cat', 'dog'], texts: ['cat dog'] });
    component.updateData({ topics: ['bird'], texts: ['bird sings'] });
    expect(document.querySelectorAll('svg')).toHaveLength(1);
    expect(document.querySelector('.wordtree__root').textContent).toContain('bird');
    component.updateData({ topics: [], texts: [] });
    expect(document.querySelector('#topics').childElementCount).toBe(0);
  });

  it('shows missing contexts and handles missing containers', () => {
    component.updateData({ topics: ['cat'], texts: ['dog runs'] });
    expect(document.querySelector('.tag-info-empty-state').textContent).toContain(
      'No matching contexts'
    );
    expect(() =>
      new TopicsTexts('#missing', events).updateData({ topics: ['cat'], texts: [] })
    ).not.toThrow();
  });
});
