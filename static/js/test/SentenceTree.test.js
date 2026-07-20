import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

// ============================================================
// Helpers
// ============================================================

const source = fs.readFileSync(new URL('../components/SentenceTree.js', import.meta.url), 'utf8');

// ============================================================
// Section 1: Component Structure
// ============================================================

test('SentenceTree is a default-exported class component', () => {
  assert.ok(
    /export default class SentenceTree\s+extends\s+React\.Component/.test(source),
    'SentenceTree should be a class extending React.Component'
  );
});

test('SentenceTree uses strict mode', () => {
  assert.ok(/'use strict'/.test(source), 'source should start with use strict');
});

// ============================================================
// Section 2: Constructor / State Initialization
// ============================================================

test('SentenceTree constructor reads from props.s_tree_data', () => {
  assert.ok(/props\.s_tree_data/.test(source), 'should read from props.s_tree_data');
});

test('SentenceTree constructor reads from window.s_tree_data', () => {
  assert.ok(/window\.s_tree_data/.test(source), 'should read from window.s_tree_data');
});

test('SentenceTree constructor prefers props over window', () => {
  // The pattern `props.s_tree_data || window.s_tree_data || {}` means props win
  assert.ok(
    /props\.s_tree_data\s*\|\|\s*window\.s_tree_data/.test(source),
    'props should take precedence over window'
  );
});

test('SentenceTree validates words is an array', () => {
  assert.ok(
    /Array\.isArray\(source\.words\)/.test(source),
    'should check words with Array.isArray'
  );
  assert.ok(
    /words:\s*Array\.isArray\(source\.words\)\s*\?\s*source\.words\s*:\s*\[\]/.test(source),
    'should default to empty array if words is not an array'
  );
});

test('SentenceTree validates clusters is an object', () => {
  assert.ok(/typeof source\.clusters\s*===\s*'object'/.test(source), 'should check clusters type');
  assert.ok(
    /clusters:\s*source\.clusters.*\?\s*source\.clusters\s*:\s*\{\}/.test(source),
    'should default to empty object if clusters is invalid'
  );
});

test('SentenceTree validates cluster_links is an object', () => {
  assert.ok(
    /typeof source\.cluster_links\s*===\s*'object'/.test(source),
    'should check cluster_links type'
  );
  assert.ok(
    /cluster_links:\s*[\s\S]*\?\s*source\.cluster_links/.test(source),
    'should default to empty object if cluster_links is invalid'
  );
});

// ============================================================
// Section 3: componentDidMount / Lifecycle
// ============================================================

test('SentenceTree has componentDidMount', () => {
  assert.ok(/componentDidMount\(\)/.test(source), 'should define componentDidMount');
});

test('componentDidMount checks if window data changed before setState', () => {
  assert.ok(
    /componentDidMount[\s\S]*this\.state\.tag/.test(source),
    'should compare state.tag in componentDidMount'
  );
  assert.ok(/JSON\.stringify/.test(source), 'should use JSON.stringify for deep comparison');
});

// ============================================================
// Section 4: Empty State
// ============================================================

test('SentenceTree renders empty state when no clusters', () => {
  assert.ok(
    /!clusters\s*\|\|\s*Object\.keys\(clusters\)\.length\s*===\s*0/.test(source),
    'should check for empty or null clusters'
  );
  assert.ok(/No sentences found/.test(source), 'should show "No sentences found" text');
});

test('SentenceTree empty state shows tag and words', () => {
  assert.ok(/Sentence Tree:\s*\{tag\}/.test(source), 'should display tag in empty state title');
  assert.ok(/Words:.*words\.join/.test(source), 'should display joined words list');
  assert.ok(/className="group_title"/.test(source), 'should have group_title class');
  assert.ok(/className="page"/.test(source), 'should have page class');
});

// ============================================================
// Section 5: Cluster Component
// ============================================================

test('Source defines a Cluster class component', () => {
  assert.ok(
    /class Cluster\s+extends\s+React\.Component/.test(source),
    'Cluster should be a class extending React.Component'
  );
});

test('Cluster has isCollapsed state defaulting to false', () => {
  assert.ok(
    /class Cluster[\s\S]*isCollapsed:\s*false/.test(source),
    'Cluster isCollapsed should default to false (expanded)'
  );
});

test('Cluster has toggleClusterContent method', () => {
  assert.ok(/toggleClusterContent/.test(source), 'Cluster should define toggleClusterContent');
  assert.ok(
    /isCollapsed:\s*!prevState\.isCollapsed/.test(source),
    'toggle should flip isCollapsed state'
  );
});

test('Cluster renders a toggle button with correct text', () => {
  assert.ok(/className="toggle-cluster-btn"/.test(source), 'should have toggle-cluster-btn class');
  assert.ok(
    /isCollapsed\s*\?/.test(source),
    'should conditionally render toggle text based on isCollapsed'
  );
  assert.ok(/'Collapse'/.test(source) || />Collapse</.test(source), 'should show Collapse text');
  assert.ok(/'Expand'/.test(source) || />Expand</.test(source), 'should show Expand text');
});

test('Cluster hides table when collapsed', () => {
  assert.ok(
    /display:\s*isCollapsed\s*\?\s*['"]none['"]/.test(source),
    'should set display:none when collapsed'
  );
  assert.ok(/className="table-responsive"/.test(source), 'should have table-responsive container');
});

test('Cluster shows post count from cluster_link', () => {
  assert.ok(/posts_count/.test(source), 'should compute posts_count');
  assert.ok(
    /posts_count\s*=\s*underscore_count\s*\+\s*1/.test(source),
    'should count underscores + 1 for post count'
  );
  assert.ok(
    /posts\?\/\(\[\\d_\]\+\)/.test(source) || /pids_match/.test(source),
    'should extract post IDs from cluster_link pattern'
  );
});

test('Cluster renders link when cluster_link exists', () => {
  assert.ok(/cluster_link\s*\?/.test(source), 'should conditionally render link');
  assert.ok(/href={cluster_link}/.test(source), 'should use cluster_link as href');
});

test('Cluster renders Cluster label text', () => {
  assert.ok(/Cluster\s*\$\{label\}/.test(source), 'should show Cluster label when no link');
});

// ============================================================
// Section 6: SentenceRow Component
// ============================================================

test('Source defines a SentenceRow class component', () => {
  assert.ok(
    /class SentenceRow\s+extends\s+React\.Component/.test(source),
    'SentenceRow should be a class extending React.Component'
  );
});

test('SentenceRow has leftExpanded and rightExpanded state', () => {
  assert.ok(
    /class SentenceRow[\s\S]*leftExpanded:\s*false/.test(source),
    'should have leftExpanded state'
  );
  assert.ok(/rightExpanded:\s*false/.test(source), 'should have rightExpanded state');
});

test('SentenceRow has toggleLeft and toggleRight methods', () => {
  assert.ok(/toggleLeft/.test(source), 'should define toggleLeft');
  assert.ok(/toggleRight/.test(source), 'should define toggleRight');
});

test('SentenceRow renders three cells (left, mid, right)', () => {
  assert.ok(/className="left sentence-cell"/.test(source), 'should have left cell');
  assert.ok(/className="mid sentence-cell"/.test(source), 'should have mid cell');
  assert.ok(/className="right sentence-cell"/.test(source), 'should have right cell');
});

test('SentenceRow left cell renders truncated text', () => {
  assert.ok(/renderLeftTruncated/.test(source), 'should define renderLeftTruncated');
  assert.ok(
    /\.\.\.\{text\.slice\(-MAX_LEN\)\}/.test(source),
    'should show ellipsis + tail when truncated on left'
  );
});

test('SentenceRow right cell renders truncated text', () => {
  assert.ok(/renderTruncated/.test(source), 'should define renderTruncated');
  assert.ok(
    /\{text\.slice\(0,\s*MAX_LEN\)\}\.\.\./.test(source),
    'should show head + ellipsis when truncated on right'
  );
});

test('SentenceRow uses MAX_LEN constant for truncation', () => {
  assert.ok(/const MAX_LEN\s*=\s*150/.test(source), 'should define MAX_LEN as 150');
  assert.ok(/length\s*>\s*MAX_LEN/.test(source), 'should compare text length against MAX_LEN');
});

test('SentenceRow mid cell renders link when post_url exists', () => {
  assert.ok(/context\.post_url\s*\?/.test(source), 'should conditionally render link in mid cell');
  assert.ok(/href={context\.post_url}/.test(source), 'should use context.post_url as href');
  assert.ok(/target="_blank"/.test(source), 'should open link in new tab');
  assert.ok(
    /rel="noopener noreferrer"/.test(source),
    'should set rel="noopener noreferrer" for security'
  );
});

test('SentenceRow mid cell falls back to plain text when no post_url', () => {
  assert.ok(
    /context\.post_url\s*\?[\s\S]*:[\s\S]*context\.mid/.test(source) || /context\.mid/.test(source),
    'should render plain context.mid when no post_url'
  );
});

test('SentenceRow has show-more-less blocks for truncatable cells', () => {
  assert.ok(
    /className="show-more-less-block"/.test(source),
    'should have show-more-less-block class'
  );
  assert.ok(/className="show-more-btn"/.test(source), 'should have show-more-btn class');
  assert.ok(/'show more'/.test(source), 'should show "show more" text');
  assert.ok(/'show less'/.test(source), 'should show "show less" text');
});

// ============================================================
// Section 7: Render Structure
// ============================================================

test('SentenceTree render renders group_title with tag and words', () => {
  assert.ok(
    /<h3>.*Sentence Tree/.test(source) || /Sentence Tree:/.test(source),
    'should render Sentence Tree title'
  );
  assert.ok(
    /words\.join\(\s*['"],\s*['"]\s*\)/.test(source),
    'should join words with comma separator'
  );
});

test('SentenceTree render maps clusters to Cluster components', () => {
  assert.ok(/Object\.entries\(clusters\)\.map/.test(source), 'should iterate over cluster entries');
  assert.ok(/<Cluster/.test(source), 'should render Cluster component');
  assert.ok(
    /ctxs={Array\.isArray\(ctxs\)\s*\?\s*ctxs\s*:\s*\[\]}/.test(source),
    'should ensure ctxs is always an array'
  );
});

// ============================================================
// Section 8: Data Validation Edge Cases
// ============================================================

test('SentenceTree ensures ctxs is always an array in render', () => {
  assert.ok(
    /Array\.isArray\(ctxs\)/.test(source),
    'should check ctxs with Array.isArray in render'
  );
});

test('SentenceTree handles null clusters in render check', () => {
  assert.ok(/!clusters/.test(source), 'should handle null clusters');
});

test('SentenceTree handles non-array words in constructor', () => {
  assert.ok(
    /words:.*Array\.isArray.*\?.*:/.test(source),
    'should default words to [] when not an array'
  );
});

test('SentenceTree handles non-object cluster_links in constructor', () => {
  assert.ok(
    /cluster_links:\s*[\s\S]*typeof[\s\S]*object[\s\S]*\?[\s\S]*:/.test(source),
    'should default cluster_links to {} when not an object'
  );
});

// ============================================================
// Section 9: Cluster Label Format
// ============================================================

test('Cluster label shows posts count in parentheses', () => {
  assert.ok(/\(\s*\{posts_count\}/.test(source), 'should show posts_count in parentheses');
  assert.ok(/\{ctxs\.length\}/.test(source), 'should show ctxs.length');
});

test('Cluster defaults posts_count to at least 1 when link exists', () => {
  assert.ok(/posts_count\s*=\s*1/.test(source), 'should default posts_count to 1');
  assert.ok(
    /If a link exists, there is at least one post/.test(source),
    'should have comment explaining default count'
  );
});
