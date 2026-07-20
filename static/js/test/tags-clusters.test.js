import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'tags-clusters.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Imports and exports
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src), 'should import React');
});

test('source has named export TagsClustersTxtList', () => {
  const src = readSource();
  assert.ok(
    /export class TagsClustersTxtList extends React\.Component/.test(src),
    'should export TagsClustersTxtList class'
  );
});

test('source has default export TagsClustersList', () => {
  const src = readSource();
  assert.ok(
    /export default class TagsClustersList extends React\.Component/.test(src),
    'should export default TagsClustersList class'
  );
});

// ============================================================
// TagsClustersTxtList class
// ============================================================

test('TagsClustersTxtList constructor accepts props', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('TagsClustersTxtList constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('TagsClustersTxtList constructor binds updateTags', () => {
  const src = readSource();
  assert.ok(
    /this\.updateTags\s*=\s*this\.updateTags\.bind\(this\)/.test(src),
    'should bind updateTags'
  );
});

test('TagsClustersTxtList declares updateTags method', () => {
  const src = readSource();
  assert.ok(/updateTags\s*\(\s*state\s*\)/.test(src), 'should declare updateTags(state) method');
});

test('TagsClustersTxtList updateTags calls setState', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src), 'should call setState with state');
});

test('TagsClustersTxtList declares componentDidMount', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)/.test(src), 'should declare componentDidMount()');
});

test('TagsClustersTxtList componentDidMount binds TAGS_CLUSTERS_UPDATED', () => {
  const src = readSource();
  assert.ok(/TAGS_CLUSTERS_UPDATED/.test(src), 'should reference TAGS_CLUSTERS_UPDATED');
  assert.ok(
    /this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.TAGS_CLUSTERS_UPDATED/.test(src),
    'should bind TAGS_CLUSTERS_UPDATED event'
  );
});

test('TagsClustersTxtList declares componentWillUnmount', () => {
  const src = readSource();
  assert.ok(/componentWillUnmount\s*\(\s*\)/.test(src), 'should declare componentWillUnmount()');
});

test('TagsClustersTxtList componentWillUnmount unbinds TAGS_CLUSTERS_UPDATED', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.TAGS_CLUSTERS_UPDATED/.test(src),
    'should unbind TAGS_CLUSTERS_UPDATED event'
  );
});

test('TagsClustersTxtList declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('TagsClustersTxtList render checks state and clusters', () => {
  const src = readSource();
  assert.ok(
    /this\.state && this\.state\.clusters/.test(src),
    'should check state and state.clusters'
  );
});

test('TagsClustersTxtList render returns "No tags" paragraph when empty', () => {
  const src = readSource();
  assert.ok(/<p>No tags<\/p>/.test(src), 'should return <p>No tags</p> when no clusters');
});

test('TagsClustersTxtList render returns table with cloud class', () => {
  const src = readSource();
  assert.ok(
    /<table className\s*=\s*['"]cloud['"]/.test(src),
    'should render table with cloud class'
  );
});

test('TagsClustersTxtList render uses tag_txt_clusters_tr class for rows', () => {
  const src = readSource();
  assert.ok(/tag_txt_clusters_tr/.test(src), 'should use tag_txt_clusters_tr CSS class');
});

test('TagsClustersTxtList render uses tag_txt_clusters_td_left class', () => {
  const src = readSource();
  assert.ok(/tag_txt_clusters_td_left/.test(src), 'should use tag_txt_clusters_td_left CSS class');
});

test('TagsClustersTxtList render uses tag_txt_clusters_td_middle class', () => {
  const src = readSource();
  assert.ok(
    /tag_txt_clusters_td_middle/.test(src),
    'should use tag_txt_clusters_td_middle CSS class'
  );
});

test('TagsClustersTxtList render uses tag_txt_clusters_td_right class', () => {
  const src = readSource();
  assert.ok(
    /tag_txt_clusters_td_right/.test(src),
    'should use tag_txt_clusters_td_right CSS class'
  );
});

test('TagsClustersTxtList render uses rowSpan for the tag cell', () => {
  const src = readSource();
  assert.ok(/rowSpan\s*=\s*\{/.test(src), 'should use rowSpan attribute');
});

test('TagsClustersTxtList render links to /posts/ with joined pids', () => {
  const src = readSource();
  assert.ok(
    /href=\{\s*['"]\/posts\/['"]\s*\+\s*pids\.join/.test(src),
    'should link to /posts/ with joined pids'
  );
});

test('TagsClustersTxtList render uses tbody with tag_txt_clusters_cluster class', () => {
  const src = readSource();
  assert.ok(/tag_txt_clusters_cluster/.test(src), 'should use tag_txt_clusters_cluster CSS class');
});

test('TagsClustersTxtList render limits context words with words_n', () => {
  const src = readSource();
  assert.ok(/words_n\s*=\s*15/.test(src), 'should limit context to 15 words');
  assert.ok(/bf\.split\(' '\)/.test(src), 'should split before text into words');
  assert.ok(
    /words\.splice\(words\.length\s*-\s*words_n\)/.test(src),
    'should take last words_n words before tag'
  );
  assert.ok(
    /words\.splice\(\s*0\s*,\s*words_n\)/.test(src),
    'should take first words_n words after tag'
  );
});

test('TagsClustersTxtList render searches for tag position in text', () => {
  const src = readSource();
  assert.ok(/txt\.search\(this\.props\.tag\)/.test(src), 'should search for tag in text');
});

test('TagsClustersTxtList render extracts before and after text', () => {
  const src = readSource();
  assert.ok(/txt\.substr\(0,\s*pos\)/.test(src), 'should extract text before tag');
  assert.ok(
    /txt\.substr\(pos\s*\+\s*this\.props\.tag\.length\)/.test(src),
    'should extract text after tag'
  );
});

// ============================================================
// TagsClustersList (default export) class
// ============================================================

test('TagsClustersList constructor accepts props', () => {
  const src = readSource();
  const matches = src.match(/constructor\s*\(\s*props\s*\)/g);
  assert.equal(matches && matches.length, 2, 'both classes should have constructor(props)');
});

test('TagsClustersList constructor binds updateTags', () => {
  const src = readSource();
  const matches = src.match(/this\.updateTags\s*=\s*this\.updateTags\.bind\(this\)/g);
  assert.equal(matches && matches.length, 2, 'both classes should bind updateTags');
});

test('TagsClustersList declares componentDidMount', () => {
  const src = readSource();
  const matches = src.match(/componentDidMount\s*\(\s*\)/g);
  assert.equal(matches && matches.length, 2, 'both classes should declare componentDidMount');
});

test('TagsClustersList declares componentWillUnmount', () => {
  const src = readSource();
  const matches = src.match(/componentWillUnmount\s*\(\s*\)/g);
  assert.equal(matches && matches.length, 2, 'both classes should declare componentWillUnmount');
});

test('TagsClustersList render returns "No clusters" paragraph when empty', () => {
  const src = readSource();
  assert.ok(/<p>No clusters<\/p>/.test(src), 'should return <p>No clusters</p> when no clusters');
});

test('TagsClustersList render returns div with cloud class', () => {
  const src = readSource();
  assert.ok(/<div className\s*=\s*['"]cloud['"]/.test(src), 'should render div with cloud class');
});

test('TagsClustersList render sorts clusters by post count descending', () => {
  const src = readSource();
  assert.ok(/\.sort\s*\(/.test(src), 'should sort clusters');
  assert.ok(
    /b\.pids\.length\s*-\s*a\.pids\.length/.test(src),
    'should sort by pids length descending'
  );
});

test('TagsClustersList render creates links with cluster_link class', () => {
  const src = readSource();
  assert.ok(/cluster_link/.test(src), 'should use cluster_link CSS class');
});

test('TagsClustersList render links to /posts/ with joined pids', () => {
  const src = readSource();
  assert.ok(
    /href=\{\s*[`'"]\/posts\/\$\{/.test(src) || /href=\{\s*['"]\/posts\/['"]\s*\+/.test(src),
    'should link to /posts/ with pids'
  );
});

test('TagsClustersList render shows label and count in parentheses', () => {
  const src = readSource();
  assert.ok(
    /\$\{pids_l\.pids\.length\}/.test(src) || /pids\.length/.test(src),
    'should display cluster count'
  );
});
