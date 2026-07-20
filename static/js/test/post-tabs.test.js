import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'post-tabs.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Constants and imports tests
// ============================================================

test('source defines TAB_POSTS constant', () => {
  const src = readSource();
  assert.ok(/TAB_POSTS\s*=\s*['"]posts['"]/.test(src), 'should define TAB_POSTS = "posts"');
});

test('source defines TAB_WORDSTREE constant', () => {
  const src = readSource();
  assert.ok(
    /TAB_WORDSTREE\s*=\s*['"]wordstree['"]/.test(src),
    'should define TAB_WORDSTREE = "wordstree"'
  );
});

test('source defines TAB_BIGRAMS constant', () => {
  const src = readSource();
  assert.ok(/TAB_BIGRAMS\s*=\s*['"]bigrams['"]/.test(src), 'should define TAB_BIGRAMS = "bigrams"');
});

test('source defines TAB_WORDSCLOUD constant', () => {
  const src = readSource();
  assert.ok(
    /TAB_WORDSCLOUD\s*=\s*['"]wordscloud['"]/.test(src),
    'should define TAB_WORDSCLOUD = "wordscloud"'
  );
});

test('source defines TAB_TAGS constant', () => {
  const src = readSource();
  assert.ok(/TAB_TAGS\s*=\s*['"]tags['"]/.test(src), 'should define TAB_TAGS = "tags"');
});

test('source defines TAB_CHAT constant', () => {
  const src = readSource();
  assert.ok(/TAB_CHAT\s*=\s*['"]chat['"]/.test(src), 'should define TAB_CHAT = "chat"');
});

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports named PostTabs class extending React.Component', () => {
  const src = readSource();
  assert.ok(
    /export class PostTabs extends React\.Component/.test(src),
    'should export PostTabs class extending React.Component'
  );
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('constructor creates tabs Map', () => {
  const src = readSource();
  assert.ok(/this\.tabs\s*=\s*new Map/.test(src), 'should create this.tabs as Map');
});

test('constructor sets 6 tabs in Map', () => {
  const src = readSource();
  assert.ok(/this\.tabs\.set\s*\(\s*TAB_POSTS/.test(src), 'should set posts tab');
  assert.ok(/this\.tabs\.set\s*\(\s*TAB_TAGS/.test(src), 'should set tags tab');
  assert.ok(/this\.tabs\.set\s*\(\s*TAB_WORDSTREE/.test(src), 'should set wordstree tab');
  assert.ok(/this\.tabs\.set\s*\(\s*TAB_BIGRAMS/.test(src), 'should set bigrams tab');
  assert.ok(/this\.tabs\.set\s*\(\s*TAB_WORDSCLOUD/.test(src), 'should set wordscloud tab');
  assert.ok(/this\.tabs\.set\s*\(\s*TAB_CHAT/.test(src), 'should set chat tab');
});

test('constructor sets current tab to posts', () => {
  const src = readSource();
  assert.ok(
    /this\.state\s*=\s*\{[\s\S]*?current\s*:\s*TAB_POSTS/.test(src),
    'should set state.current to TAB_POSTS'
  );
});

test('constructor parses words_from_hash from props', () => {
  const src = readSource();
  assert.ok(/this\.props\.words_from_hash/.test(src), 'should check props.words_from_hash');
  assert.ok(/decodeURIComponent/.test(src), 'should use decodeURIComponent');
  assert.ok(/\.substr\s*\(\s*1\s*\)/.test(src), 'should strip first character (hash)');
  assert.ok(/\.split\s*\(\s*['"] ['"]/.test(src), 'should split by space');
});

test('constructor sets empty words_from_hash when not provided', () => {
  const src = readSource();
  assert.ok(/this\.words_from_hash\s*=\s*\[\s*\]/.test(src), 'should set empty array when no hash');
});

test('constructor queries container element', () => {
  const src = readSource();
  assert.ok(/document\.querySelector/.test(src), 'should use document.querySelector');
  assert.ok(/#posts_page1/.test(src), 'should query #posts_page1');
});

test('constructor creates WordTree instance', () => {
  const src = readSource();
  assert.ok(/new WordTree/.test(src), 'should create new WordTree');
});

test('constructor calls wordtree.start()', () => {
  const src = readSource();
  assert.ok(/this\.wordtree\.start/.test(src), 'should call wordtree.start()');
});

test('constructor creates PostsWordsCloud instance', () => {
  const src = readSource();
  assert.ok(/new PostsWordsCloud/.test(src), 'should create new PostsWordsCloud');
});

test('constructor binds onTabClick method', () => {
  const src = readSource();
  assert.ok(
    /this\.onTabClick\s*=\s*this\.onTabClick\.bind\(this\)/.test(src),
    'should bind onTabClick'
  );
});

test('constructor binds updatePosts method', () => {
  const src = readSource();
  assert.ok(
    /this\.updatePosts\s*=\s*this\.updatePosts\.bind\(this\)/.test(src),
    'should bind updatePosts'
  );
});

// ============================================================
// Method declaration tests
// ============================================================

test('source declares onTabClick method', () => {
  const src = readSource();
  assert.ok(/onTabClick\s*\(/.test(src), 'should declare onTabClick() method');
});

test('onTabClick reads data-tab attribute', () => {
  const src = readSource();
  assert.ok(/getAttribute\s*\(\s*['"]data-tab['"]/.test(src), 'should read data-tab attribute');
});

test('onTabClick calls changeTab', () => {
  const src = readSource();
  assert.ok(/this\.changeTab/.test(src), 'should call changeTab');
});

test('source declares changeTab method', () => {
  const src = readSource();
  assert.ok(/changeTab\s*\(/.test(src), 'should declare changeTab() method');
});

test('changeTab updates current in state', () => {
  const src = readSource();
  assert.ok(
    /this\.setState\s*\(\s*\{\s*current\s*:/.test(src),
    'should set state.current via setState'
  );
});

test('source declares updatePosts method', () => {
  const src = readSource();
  assert.ok(/updatePosts\s*\(/.test(src), 'should declare updatePosts() method');
});

test('updatePosts merges words_from_hash into data', () => {
  const src = readSource();
  assert.ok(/this\.words_from_hash/.test(src), 'should use words_from_hash');
  assert.ok(/data\.words\.indexOf/.test(src), 'should check word existence before adding');
  assert.ok(/data\.words\.push/.test(src), 'should push new words');
});

test('updatePosts sets posts in state', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*\{\s*posts\s*:/.test(src), 'should set state.posts');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)/.test(src), 'should declare componentDidMount() method');
});

test('componentDidMount binds POSTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/POSTS_UPDATED/.test(src), 'should reference POSTS_UPDATED');
  assert.ok(
    /this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.POSTS_UPDATED/.test(src),
    'should bind POSTS_UPDATED event'
  );
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(
    /componentWillUnmount\s*\(\s*\)/.test(src),
    'should declare componentWillUnmount() method'
  );
});

test('componentWillUnmount unbinds POSTS_UPDATED event', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.POSTS_UPDATED/.test(src),
    'should unbind POSTS_UPDATED event'
  );
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('render maps tabs to li elements', () => {
  const src = readSource();
  assert.ok(/this\.tabs/.test(src) && /for\s*\(/.test(src), 'should iterate over tabs');
  assert.ok(/<li/.test(src), 'should render li elements');
});

test('render uses post_tab CSS class', () => {
  const src = readSource();
  assert.ok(/post_tab/.test(src), 'should use post_tab CSS class');
});

test('render uses post_tab_active CSS class conditionally', () => {
  const src = readSource();
  assert.ok(/post_tab_active/.test(src), 'should conditionally apply post_tab_active class');
});

test('render tab has data-tab attribute', () => {
  const src = readSource();
  assert.ok(/data-tab\s*=\s*\{?\s*name/.test(src), 'should set data-tab attribute');
});

test('render tab has onClick handler', () => {
  const src = readSource();
  assert.ok(/onClick\s*=\s*\{?\s*this\.onTabClick/.test(src), 'should bind onClick to onTabClick');
});

test('render tabs in ul with post_tabs_list class', () => {
  const src = readSource();
  assert.ok(/post_tabs_list/.test(src), 'should use post_tabs_list CSS class');
});

test('render returns ul when posts not set', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*!\s*this\.state\.posts\s*\)/.test(src), 'should check if posts is not set');
  assert.ok(/return\s*<ul/.test(src), 'should return <ul> when no posts');
});

test('render includes group_title CSS class', () => {
  const src = readSource();
  assert.ok(/group_title/.test(src), 'should use group_title CSS class');
});

test('render displays group_title from state', () => {
  const src = readSource();
  assert.ok(/this\.state\.posts\.group_title/.test(src), 'should display posts.group_title');
});

test('render joins words with comma', () => {
  const src = readSource();
  assert.ok(/this\.state\.posts\.words\.join/.test(src), 'should join posts.words');
});

test('render includes post-grouped link', () => {
  const src = readSource();
  assert.ok(/\/post-grouped\//.test(src), 'should include /post-grouped/ path');
  assert.ok(/pids\.join/.test(src), 'should join pids with separator');
});

test('render conditionally shows grouped link', () => {
  const src = readSource();
  assert.ok(/pids\.length\s*>\s*0/.test(src), 'should check pids.length before showing link');
});

test('render includes Open in new page link', () => {
  const src = readSource();
  assert.ok(/Open in new page/.test(src), 'should include "Open in new page" text');
});

test('render uses target="_blank" and rel="noopener noreferrer"', () => {
  const src = readSource();
  assert.ok(/target\s*=\s*['"]_blank['"]/.test(src), 'should use target="_blank"');
  assert.ok(
    /rel\s*=\s*['"]noopener noreferrer['"]/.test(src),
    'should use rel="noopener noreferrer"'
  );
});

test('render conditionally renders PostsBigrams for bigrams tab', () => {
  const src = readSource();
  assert.ok(
    /TAB_BIGRAMS/.test(src) && /PostsBigrams/.test(src),
    'should render PostsBigrams for bigrams tab'
  );
});

test('render conditionally renders PostsTags for tags tab', () => {
  const src = readSource();
  assert.ok(/TAB_TAGS/.test(src) && /PostsTags/.test(src), 'should render PostsTags for tags tab');
});

test('render conditionally renders PostChatS for chat tab', () => {
  const src = readSource();
  assert.ok(/TAB_CHAT/.test(src) && /PostChatS/.test(src), 'should render PostChatS for chat tab');
});

test('render collects pids from posts map', () => {
  const src = readSource();
  assert.ok(/post\.pos/.test(src), 'should read post.pos for pids');
});

// ============================================================
// WordTree and WordsCloud integration tests
// ============================================================

test('render calls wordtree.updateWordTree for wordstree tab', () => {
  const src = readSource();
  assert.ok(/this\.wordtree\.updateWordTree/.test(src), 'should call wordtree.updateWordTree');
});

test('render calls wordscloud.updateWordsCloud for wordscloud tab', () => {
  const src = readSource();
  assert.ok(
    /this\.wordscloud\.updateWordsCloud/.test(src),
    'should call wordscloud.updateWordsCloud'
  );
});

test('render extracts lemmas for wordtree', () => {
  const src = readSource();
  assert.ok(/post\.post\.lemmas/.test(src), 'should read post.post.lemmas');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src), 'should import React');
});

test('source imports PostsListS', () => {
  const src = readSource();
  assert.ok(/import\s*\{\s*PostsListS\s*\}\s*from/.test(src), 'should import PostsListS');
});

test('source imports WordTree', () => {
  const src = readSource();
  assert.ok(/import WordTree from/.test(src), 'should import WordTree');
});

test('source imports PostsWordsCloud', () => {
  const src = readSource();
  assert.ok(/import PostsWordsCloud from/.test(src), 'should import PostsWordsCloud');
});

test('source imports PostsBigrams', () => {
  const src = readSource();
  assert.ok(/import\s*\{\s*PostsBigrams\s*\}\s*from/.test(src), 'should import PostsBigrams');
});

test('source imports PostsTags', () => {
  const src = readSource();
  assert.ok(/import\s*\{\s*PostsTags\s*\}\s*from/.test(src), 'should import PostsTags');
});

test('source imports PostChatS', () => {
  const src = readSource();
  assert.ok(/import PostChatS from/.test(src), 'should import PostChatS');
});
