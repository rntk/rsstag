import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'posts-list.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// PostsList class tests
// ============================================================

test('source exports PostsList as a named class', () => {
  const src = readSource();
  assert.ok(
    /export class PostsList extends React\.Component/.test(src),
    'should export class PostsList extending React.Component'
  );
});

test('PostsList constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('PostsList constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

test('PostsList constructor binds updatePosts method', () => {
  const src = readSource();
  assert.ok(
    /this\.updatePosts\s*=\s*this\.updatePosts\.bind\(this\)/.test(src),
    'should bind updatePosts'
  );
});

// ============================================================
// PostsList updatePosts method tests
// ============================================================

test('source declares updatePosts method', () => {
  const src = readSource();
  assert.ok(/updatePosts\s*\(\s*state\s*\)/.test(src), 'should declare updatePosts(state) method');
});

test('updatePosts calls setState with state parameter', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src), 'should call setState(state)');
});

// ============================================================
// PostsList lifecycle method tests
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

test('componentDidMount binds updatePosts as handler', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.bind\s*\([^,]+,\s*this\.updatePosts\s*\)/.test(src),
    'should bind updatePosts as the event handler'
  );
});

test('source declares componentDidUpdate lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidUpdate\s*\(\s*\)/.test(src), 'should declare componentDidUpdate() method');
});

test('componentDidUpdate triggers POSTS_RENDERED event', () => {
  const src = readSource();
  assert.ok(/POSTS_RENDERED/.test(src), 'should reference POSTS_RENDERED');
  assert.ok(
    /this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.POSTS_RENDERED\s*\)/.test(src),
    'should trigger POSTS_RENDERED event'
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

test('componentWillUnmount unbinds updatePosts as handler', () => {
  const src = readSource();
  assert.ok(
    /this\.props\.ES\.unbind\s*\([^,]+,\s*this\.updatePosts\s*\)/.test(src),
    'should unbind updatePosts as the event handler'
  );
});

// ============================================================
// PostsList render method tests
// ============================================================

test('PostsList source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('PostsList render delegates to PostsListS function', () => {
  const src = readSource();
  assert.ok(
    /PostsListS\s*\(\s*this\.state\s*,\s*this\.props\.ES\s*\)/.test(src),
    'should call PostsListS(this.state, this.props.ES)'
  );
});

// ============================================================
// PostsListS function tests
// ============================================================

test('source exports PostsListS as a named function', () => {
  const src = readSource();
  assert.ok(
    /export function PostsListS\s*\(\s*state\s*,\s*ev_sys/.test(src),
    'should export function PostsListS(state, ev_sys)'
  );
});

test('PostsListS checks for state existence', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*state\s*\)/.test(src), 'should check if state');
});

test('PostsListS returns "No posts" paragraph when no state', () => {
  const src = readSource();
  assert.ok(/<p>No posts<\/p>/.test(src), 'should return <p>No posts</p>');
});

// ============================================================
// Post rendering tests
// ============================================================

test('PostsListS iterates over state.posts entries', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let item of state\.posts/.test(src), 'should iterate over state.posts');
});

test('PostsListS renders PostItem components', () => {
  const src = readSource();
  assert.ok(/<PostItem/.test(src), 'should render PostItem');
  assert.ok(/import PostItem from/.test(src), 'should import PostItem');
});

test('PostsListS passes post prop to PostItem', () => {
  const src = readSource();
  assert.ok(/post\s*=\s*\{?\s*post/.test(src), 'should pass post prop');
});

test('PostsListS passes tag prop from state.group_title', () => {
  const src = readSource();
  assert.ok(/tag\s*=\s*\{?\s*state\.group_title/.test(src), 'should pass tag=state.group_title');
});

test('PostsListS passes key prop from post.pos', () => {
  const src = readSource();
  assert.ok(/key\s*=\s*\{?\s*post\.pos/.test(src), 'should pass key=post.pos');
});

test('PostsListS passes ES prop to PostItem', () => {
  const src = readSource();
  assert.ok(/ES\s*=\s*\{?\s*ev_sys/.test(src), 'should pass ES prop');
});

test('PostsListS passes current prop from state.current_post', () => {
  const src = readSource();
  assert.ok(
    /current\s*=\s*\{?\s*state\.current_post/.test(src),
    'should pass current=state.current_post'
  );
});

test('PostsListS passes words prop from state.words', () => {
  const src = readSource();
  assert.ok(/words\s*=\s*\{?\s*state\.words/.test(src), 'should pass words=state.words');
});

test('PostsListS tracks post count with posts_n variable', () => {
  const src = readSource();
  assert.ok(/let posts_n\s*=\s*0/.test(src), 'should initialize posts_n counter');
  assert.ok(/posts_n\+\+/.test(src), 'should increment posts_n');
});

test('PostsListS limits rendering by posts_per_page * current_page', () => {
  const src = readSource();
  assert.ok(
    /state\.posts_per_page\s*\*\s*state\.current_page/.test(src),
    'should check posts_per_page * current_page'
  );
});

test('PostsListS breaks loop when page limit reached', () => {
  const src = readSource();
  assert.ok(/break;?/.test(src), 'should break when limit reached');
});

// ============================================================
// Pagination / LoadMore tests
// ============================================================

test('PostsListS initializes load_page to null', () => {
  const src = readSource();
  assert.ok(/let load_page\s*=\s*null/.test(src), 'should initialize load_page = null');
});

test('PostsListS checks posts.size > posts_per_page', () => {
  const src = readSource();
  assert.ok(
    /state\.posts\.size\s*>\s*state\.posts_per_page/.test(src),
    'should check posts.size > posts_per_page'
  );
});

test('PostsListS checks current_page < Math.ceil', () => {
  const src = readSource();
  assert.ok(
    /state\.current_page\s*<\s*Math\.ceil/.test(src),
    'should check current_page < Math.ceil'
  );
});

test('PostsListS calculates max pages with state.posts.size / state.posts_per_page', () => {
  const src = readSource();
  assert.ok(
    /state\.posts\.size\s*\/\s*state\.posts_per_page/.test(src),
    'should calculate max pages'
  );
});

test('PostsListS renders LoadPosts component for pagination', () => {
  const src = readSource();
  assert.ok(/<LoadPosts/.test(src), 'should render LoadPosts');
  assert.ok(/import.*LoadPosts.*from/.test(src), 'should import LoadPosts');
});

test('PostsListS passes ES prop to LoadPosts', () => {
  const src = readSource();
  assert.ok(/<LoadPosts\s+ES\s*=\s*\{?\s*ev_sys/.test(src), 'should pass ES prop to LoadPosts');
});

// ============================================================
// Container and layout tests
// ============================================================

test('PostsListS wraps content in div with posts_list class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]posts_list['"]/.test(src), 'should use posts_list class');
});

test('PostsListS uses inner div with posts class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]posts['"]/.test(src), 'should use posts class');
});

test('PostsListS shows "No posts" when posts array is empty', () => {
  const src = readSource();
  assert.ok(/posts\.length\s*\?/.test(src), 'should conditionally show posts or "No posts"');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src), 'should import React');
});

test('source uses strict mode', () => {
  const src = readSource();
  assert.ok(/'use strict'/.test(src), 'should use strict mode');
});
