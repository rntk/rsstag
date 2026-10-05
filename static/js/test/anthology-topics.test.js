import test from 'node:test';
import assert from 'node:assert/strict';

import { filterSnippets, renderMainTabs, renderToolbar } from '../anthology-detail.js';
import {
  collapsedForLevel,
  hasTopics,
  maxTopicLevel,
  renderTopicHierarchy,
  snippetInTopic,
  snippetTopics,
  topicParts,
} from '../libs/anthology-topics.js';

const snippets = [
  { id: 's1', topic_path: 'Tech > AI > Models', read: false },
  { id: 's2', topic_path: 'Tech > AI > Models', read: true },
  { id: 's3', topic_path: 'Tech > Hardware', read: false },
  { id: 's4', topic_path: 'Sport', read: false },
  { id: 's5', topic_path: '', read: false },
];

test('topic paths split on ">" and drop blanks', () => {
  assert.deepEqual(topicParts(' Tech >  AI > '), ['Tech', 'AI']);
  assert.deepEqual(topicParts(undefined), []);
});

test('hasTopics needs at least one non-empty path', () => {
  assert.equal(hasTopics(snippets), true);
  assert.equal(hasTopics([{ topic_path: ' > ' }, {}]), false);
  assert.equal(hasTopics(null), false);
});

test('snippetTopics counts snippets and unread per distinct path', () => {
  assert.deepEqual(snippetTopics(snippets), [
    { name: 'Tech>AI>Models', snippets_count: 2, unread_count: 1 },
    { name: 'Tech>Hardware', snippets_count: 1, unread_count: 1 },
    { name: 'Sport', snippets_count: 1, unread_count: 1 },
  ]);
});

test('snippetInTopic matches whole path segments as a prefix', () => {
  assert.equal(snippetInTopic(snippets[0], 'Tech>AI'), true);
  assert.equal(snippetInTopic(snippets[0], 'Tech > AI > Models'), true);
  assert.equal(snippetInTopic(snippets[0], 'Tech>A'), false);
  assert.equal(snippetInTopic(snippets[3], 'Tech'), false);
  assert.equal(snippetInTopic(snippets[0], ''), false);
});

test('filterSnippets combines the topic filter with unread-only', () => {
  assert.deepEqual(
    filterSnippets(snippets, false, 'Tech').map((s) => s.id),
    ['s1', 's2', 's3']
  );
  assert.deepEqual(
    filterSnippets(snippets, true, 'Tech>AI').map((s) => s.id),
    ['s1']
  );
  assert.equal(filterSnippets(snippets, false).length, 5);
});

test('levels collapse branches at or below the chosen depth', () => {
  assert.equal(maxTopicLevel(snippets), 2);
  assert.deepEqual([...collapsedForLevel(snippets, 0)].sort(), ['Tech', 'Tech>AI']);
  assert.deepEqual([...collapsedForLevel(snippets, 1)], ['Tech>AI']);
  assert.equal(collapsedForLevel(snippets, 2).size, 0);
});

test('hierarchy shows aggregated counts and shares, biggest first', () => {
  const html = renderTopicHierarchy(snippets, { level: 2, collapsed: new Set() });
  assert.match(html, /3 topics across 4 snippets · 1 without a topic/);
  assert.match(html, /Tech <span class="anth-topics__count">3<\/span>/);
  assert.match(html, /2 · 40%/);
  assert.ok(html.indexOf('Tech <span') < html.indexOf('fh-leaf__label">Sport'));
  assert.match(html, /data-action="topic-filter" data-path="Tech&gt;AI&gt;Models"/);
  assert.match(html, /data-action="topic-level" data-level="2"/);
});

test('collapsed branches hide their children', () => {
  const html = renderTopicHierarchy(snippets, { level: 0, collapsed: new Set(['Tech']) });
  assert.match(html, /fh-branch--collapsed/);
  assert.doesNotMatch(html, /Models/);
  assert.match(html, /aria-expanded="false"/);
});

test('hierarchy escapes topic names', () => {
  const html = renderTopicHierarchy([{ topic_path: 'a<i & "q"' }], {
    level: 0,
    collapsed: new Set(),
  });
  assert.doesNotMatch(html, /<i /);
  assert.match(html, /a&lt;i &amp; &quot;q&quot;/);
});

test('hierarchy without topics shows an empty note', () => {
  assert.match(renderTopicHierarchy([{}], { level: 0, collapsed: new Set() }), /no topics/);
});

test('tabs mark the active one', () => {
  const html = renderMainTabs('topics');
  assert.match(
    html,
    /is-active" role="tab" aria-selected="true" data-action="tab" data-tab="topics"/
  );
  assert.match(html, /aria-selected="false" data-action="tab" data-tab="snippets"/);
});

test('toolbar shows the topic filter on the snippets tab only', () => {
  const view = { unreadOnly: false, skim: false, sort: 'relevance', topic: 'Tech>AI' };
  assert.match(renderToolbar({ ...view, tab: 'snippets' }), /Topic: Tech › AI.*topic-clear/);
  const topicsToolbar = renderToolbar({ ...view, tab: 'topics' });
  assert.doesNotMatch(topicsToolbar, /topic-clear|data-control="sort"/);
  assert.match(topicsToolbar, /data-control="unreadOnly"/);
});
