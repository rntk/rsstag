import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { rankedComparator, compareByName } from '../libs/tag-sort.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'tags-list.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class extending React.Component', () => {
  const src = readSource();
  assert.ok(
    /export default class \w+ extends React\.Component/.test(src),
    'should export a default class extending React.Component'
  );
});

test('class name is TagsList', () => {
  const src = readSource();
  assert.ok(/export default class TagsList/.test(src), 'should define class TagsList');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('constructor opens score-ranked and server-ranked lists in flat view', () => {
  const src = readSource();
  assert.ok(
    /groupByLetter\s*:\s*!props\.scoreKey\s*&&\s*!props\.preserveOrder/.test(src),
    'should group only when neither a score nor server ordering is selected'
  );
});

test('constructor binds updateTags method', () => {
  const src = readSource();
  assert.ok(
    /this\.updateTags\s*=\s*this\.updateTags\.bind\(this\)/.test(src),
    'should bind updateTags'
  );
});

test('constructor binds toggleGrouping method', () => {
  const src = readSource();
  assert.ok(
    /this\.toggleGrouping\s*=\s*this\.toggleGrouping\.bind\(this\)/.test(src),
    'should bind toggleGrouping'
  );
});

// ============================================================
// Method declaration tests
// ============================================================

test('source declares updateTags method', () => {
  const src = readSource();
  assert.ok(/updateTags\s*\(/.test(src), 'should declare updateTags() method');
});

test('updateTags uses spread operator to copy state', () => {
  const src = readSource();
  assert.ok(/\.\.\.\s*state/.test(src), 'should spread incoming state');
});

test('updateTags deletes groupByLetter from incoming state', () => {
  const src = readSource();
  assert.ok(
    /delete nextState\.groupByLetter/.test(src),
    'should delete groupByLetter from nextState'
  );
});

test('updateTags calls setState with cleaned state', () => {
  const src = readSource();
  assert.ok(
    /this\.setState\s*\(\s*nextState\s*\)/.test(src),
    'should call setState with nextState'
  );
});

test('source declares toggleGrouping method', () => {
  const src = readSource();
  assert.ok(/toggleGrouping\s*\(\s*\)/.test(src), 'should declare toggleGrouping() method');
});

test('toggleGrouping uses functional setState', () => {
  const src = readSource();
  assert.ok(
    /this\.setState\s*\(\s*\(\s*prevState/.test(src),
    'should use prevState in functional setState'
  );
});

test('toggleGrouping negates groupByLetter', () => {
  const src = readSource();
  assert.ok(
    /groupByLetter\s*:\s*!\s*prevState\.groupByLetter/.test(src),
    'should negate groupByLetter'
  );
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)/.test(src), 'should declare componentDidMount() method');
});

test('componentDidMount binds TAGS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/TAGS_UPDATED/.test(src), 'should reference TAGS_UPDATED');
  assert.ok(
    /this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.TAGS_UPDATED/.test(src),
    'should bind TAGS_UPDATED event'
  );
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(
    /componentWillUnmount\s*\(\s*\)/.test(src),
    'should declare componentWillUnmount() method'
  );
});

test('componentWillUnmount unbinds TAGS_UPDATED event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.TAGS_UPDATED/.test(src),
    'should unbind TAGS_UPDATED event'
  );
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('render checks for state and tags existence', () => {
  const src = readSource();
  assert.ok(/this\.state && this\.state\.tags/.test(src), 'should check state and state.tags');
});

test('render returns "No tags" paragraph when no tags', () => {
  const src = readSource();
  assert.ok(
    /<p className="tag-info-empty-state">No tags<\/p>/.test(src),
    'should return <p className="tag-info-empty-state">No tags</p> when empty'
  );
});

test('render sets mode to grouped or flat', () => {
  const src = readSource();
  assert.ok(/const mode\s*=/.test(src), 'should define mode variable');
  assert.ok(/'grouped'/.test(src), 'should use "grouped" mode');
  assert.ok(/'flat'/.test(src), 'should use "flat" mode');
});

// ============================================================
// Toggle and tools row tests
// ============================================================

test('render includes tags_tools_row CSS class', () => {
  const src = readSource();
  assert.ok(/tags_tools_row/.test(src), 'should use tags_tools_row CSS class');
});

test('render includes tags_grouping_toggle CSS class', () => {
  const src = readSource();
  assert.ok(/tags_grouping_toggle/.test(src), 'should use tags_grouping_toggle CSS class');
});

test('toggle button uses type="button"', () => {
  const src = readSource();
  assert.ok(/type\s*=\s*['"]button['"]/.test(src), 'should set button type to "button"');
});

test('toggle button onClick bound to toggleGrouping', () => {
  const src = readSource();
  assert.ok(
    /onClick\s*=\s*\{?\s*this\.toggleGrouping/.test(src),
    'should bind onClick to toggleGrouping'
  );
});

test('toggle button says "Show by frequency" when grouped', () => {
  const src = readSource();
  assert.ok(/Show by frequency/.test(src), 'should include "Show by frequency" text');
});

test('toggle button says "Show grouped by letter" when flat', () => {
  const src = readSource();
  assert.ok(/Show grouped by letter/.test(src), 'should include "Show grouped by letter" text');
});

// ============================================================
// Flat view tests
// ============================================================

test('render returns div with key=flat for flat view', () => {
  const src = readSource();
  assert.ok(/key\s*=\s*\{?\s*mode/.test(src), 'should use mode as key');
});

test('flat view sorts with rankedComparator(scoreKey)', () => {
  const src = readSource();
  assert.ok(
    /rankedComparator\(this\.props\.scoreKey, this\.props\.preserveOrder\)/.test(src),
    'should honor scoreKey and server ordering'
  );
  assert.ok(/tag-sort\.js/.test(src), 'should import the shared comparators');
});

test('grouped view sorts alphabetically with compareByName', () => {
  const src = readSource();
  assert.ok(/tags\.sort\(compareByName\)/.test(src));
});

test('ranked order without scoreKey is count desc, ties by name (unchanged)', () => {
  const tags = [
    { tag: 'b', count: 1, temp: 9 },
    { tag: 'c', count: 5, temp: 0.1 },
    { tag: 'a', count: 1, temp: 5 },
  ];
  assert.deepEqual(
    tags.sort(rankedComparator()).map((t) => t.tag),
    ['c', 'a', 'b']
  );
});

test('server-ranked lists preserve order after grouping and returning to flat view', () => {
  const tags = [
    { tag: 'zebra', count: 1 },
    { tag: 'alpha', count: 30 },
    { tag: 'middle', count: 100 },
  ];
  const names = (items) => items.map((tag) => tag.tag);
  assert.deepEqual(names([...tags].sort(rankedComparator(undefined, true))), [
    'zebra',
    'alpha',
    'middle',
  ]);
  assert.deepEqual(names([...tags].sort(compareByName)), ['alpha', 'middle', 'zebra']);
  assert.deepEqual(names([...tags].sort(rankedComparator(undefined, true))), [
    'zebra',
    'alpha',
    'middle',
  ]);
  assert.deepEqual(names(tags), ['zebra', 'alpha', 'middle']);
});

test('ranked order with scoreKey is score desc, ties by name; alphabetical unaffected', () => {
  const tags = [
    { tag: 'frequent', count: 50, temp: 0.1 },
    { tag: 'b', count: 1, temp: 0.9 },
    { tag: 'a', count: 2, temp: 0.9 },
    { tag: 'noscore', count: 99 },
    { tag: 'best', count: 3, temp: 2.5 },
  ];
  assert.deepEqual(
    [...tags].sort(rankedComparator('temp')).map((t) => t.tag),
    ['best', 'a', 'b', 'frequent', 'noscore']
  );
  assert.deepEqual(
    [...tags].sort(compareByName).map((t) => t.tag),
    ['a', 'b', 'best', 'frequent', 'noscore']
  );
});

test('score-ranked lists open in ranked order and label the toggle "Show by score"', () => {
  const src = readSource();
  assert.ok(/Show by score/.test(src), 'should label ranked toggle by score');
  assert.ok(/Show by frequency/.test(src), 'should keep the frequency label without scoreKey');
});

test('passes scoreKey and scoreLabel to TagItem', () => {
  const src = readSource();
  assert.ok(/scoreKey=\{this\.props\.scoreKey\}/.test(src));
  assert.ok(/scoreLabel=\{this\.props\.scoreLabel\}/.test(src));
});

test('flat view returns ol with cloud class', () => {
  const src = readSource();
  assert.ok(/<ol className\s*=\s*['"]cloud['"]/.test(src), 'should use ol with cloud class');
});

// ============================================================
// Grouped view tests
// ============================================================

test('render creates letter groups', () => {
  const src = readSource();
  assert.ok(/letterGroups/.test(src), 'should define letterGroups array');
});

test('render groups tags by first letter', () => {
  const src = readSource();
  assert.ok(/\.charAt\s*\(\s*0\s*\)/.test(src), 'should get first character for grouping');
  assert.ok(/\.toUpperCase\s*\(\s*\)/.test(src), 'should uppercase first letter');
});

test('render uses alpha_group_container CSS class', () => {
  const src = readSource();
  assert.ok(/alpha_group_container/.test(src), 'should use alpha_group_container CSS class');
});

test('render uses alpha_group_title CSS class', () => {
  const src = readSource();
  assert.ok(/alpha_group_title/.test(src), 'should use alpha_group_title CSS class');
});

test('render uses alpha_group_tags CSS class', () => {
  const src = readSource();
  assert.ok(/alpha_group_tags/.test(src), 'should use alpha_group_tags CSS class');
});

test('render creates group key with group_ prefix', () => {
  const src = readSource();
  assert.ok(/key\s*=\s*\{?\s*[`'"]group_/.test(src), 'should use "group_" prefix for keys');
});

test('render includes h3 with letter in group title', () => {
  const src = readSource();
  assert.ok(/<h3>/.test(src), 'should include h3 for letter title');
});

test('render uses tagItems helper function', () => {
  const src = readSource();
  assert.ok(/tagItems/.test(src), 'should define tagItems helper');
  assert.ok(/TagItem/.test(src), 'should render TagItem components');
});

// ============================================================
// TagItem props tests
// ============================================================

test('render passes is_entities prop to TagItem', () => {
  const src = readSource();
  assert.ok(
    /is_entity\s*=\s*\{?\s*this\.props\.is_entities/.test(src),
    'should pass is_entities prop'
  );
});

test('render passes ES prop to TagItem', () => {
  const src = readSource();
  assert.ok(/ES\s*=\s*\{?\s*this\.props\.ES/.test(src), 'should pass ES prop');
});

test('render passes tags and tag_hash to TagItem', () => {
  const src = readSource();
  assert.ok(/tags\s*=\s*\{?\s*this\.state\.tags/.test(src), 'should pass tags state');
  assert.ok(/tag_hash\s*=\s*\{?\s*this\.state\.tag_hash/.test(src), 'should pass tag_hash state');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src), 'should import React');
});

test('source imports TagItem', () => {
  const src = readSource();
  assert.ok(/import TagItem from/.test(src), 'should import TagItem');
});

test('source uses Array.from for Map conversion', () => {
  const src = readSource();
  assert.ok(/Array\.from/.test(src), 'should use Array.from for Map to array conversion');
});

test('source uses this.state.tags.values()', () => {
  const src = readSource();
  assert.ok(/this\.state\.tags\.values/.test(src), 'should iterate over tags Map values');
});
