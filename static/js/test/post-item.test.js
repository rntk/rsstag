import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'post-item.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class extending React.Component', () => {
  const src = readSource();
  assert.ok(/export default class \w+ extends React\.Component/.test(src),
    'should export a default class extending React.Component');
});

test('class name is PostsItem', () => {
  const src = readSource();
  assert.ok(/export default class PostsItem/.test(src),
    'should define class PostsItem');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src),
    'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src),
    'should call super(props)');
});

test('constructor initializes state with post, tag, words', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?post\s*:\s*props\.post/.test(src),
    'should set state.post from props.post');
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?tag\s*:\s*props\.tag/.test(src),
    'should set state.tag from props.tag');
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?words\s*:\s*props\.words/.test(src),
    'should set state.words from props.words');
});

test('constructor initializes showed as false', () => {
  const src = readSource();
  assert.ok(/this\.showed\s*=\s*false/.test(src),
    'should initialize this.showed = false');
});

test('constructor binds clickReadButton method', () => {
  const src = readSource();
  assert.ok(/this\.clickReadButton\s*=\s*this\.clickReadButton\.bind\(this\)/.test(src),
    'should bind clickReadButton');
});

test('constructor binds showPostLinks method', () => {
  const src = readSource();
  assert.ok(/this\.showPostLinks\s*=\s*this\.showPostLinks\.bind\(this\)/.test(src),
    'should bind showPostLinks');
});

test('constructor binds changePostsContentState method', () => {
  const src = readSource();
  assert.ok(/this\.changePostsContentState\s*=\s*this\.changePostsContentState\.bind\(this\)/.test(src),
    'should bind changePostsContentState');
});

test('constructor binds setCurrent method', () => {
  const src = readSource();
  assert.ok(/this\.setCurrent\s*=\s*this\.setCurrent\.bind\(this\)/.test(src),
    'should bind setCurrent');
});

test('constructor binds getNode method', () => {
  const src = readSource();
  assert.ok(/this\.getNode\s*=\s*this\.getNode\.bind\(this\)/.test(src),
    'should bind getNode');
});

test('constructor initializes stopw from stopwords()', () => {
  const src = readSource();
  assert.ok(/this\.stopw\s*=\s*stopwords\s*\(\s*\)/.test(src),
    'should initialize this.stopw from stopwords()');
});

// ============================================================
// Method declaration tests
// ============================================================

test('source declares setCurrent method', () => {
  const src = readSource();
  assert.ok(/setCurrent\s*\(\s*\)\s*\{/.test(src),
    'should declare setCurrent() method');
});

test('setCurrent triggers SET_CURRENT_POST event', () => {
  const src = readSource();
  assert.ok(/SET_CURRENT_POST/.test(src),
    'should reference SET_CURRENT_POST event');
  assert.ok(/this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.SET_CURRENT_POST/.test(src),
    'should trigger SET_CURRENT_POST via ES');
});

test('source declares clickReadButton method', () => {
  const src = readSource();
  assert.ok(/clickReadButton\s*\(\s*\)\s*\{/.test(src),
    'should declare clickReadButton() method');
});

test('clickReadButton triggers CHANGE_POSTS_STATUS event', () => {
  const src = readSource();
  assert.ok(/CHANGE_POSTS_STATUS/.test(src),
    'should reference CHANGE_POSTS_STATUS event');
  assert.ok(/readed\s*:/.test(src),
    'should pass readed in payload');
});

test('source declares showPostLinks method', () => {
  const src = readSource();
  assert.ok(/showPostLinks\s*\(\s*\)\s*\{/.test(src),
    'should declare showPostLinks() method');
});

test('showPostLinks triggers SHOW_POST_LINKS event', () => {
  const src = readSource();
  assert.ok(/SHOW_POST_LINKS/.test(src),
    'should reference SHOW_POST_LINKS event');
});

test('source declares changePostsContentState method', () => {
  const src = readSource();
  assert.ok(/changePostsContentState\s*\(\s*\)\s*\{/.test(src),
    'should declare changePostsContentState() method');
});

test('changePostsContentState triggers CHANGE_POSTS_CONTENT_STATE event', () => {
  const src = readSource();
  assert.ok(/CHANGE_POSTS_CONTENT_STATE/.test(src),
    'should reference CHANGE_POSTS_CONTENT_STATE event');
  assert.ok(/showed\s*:/.test(src),
    'should pass showed in payload');
});

test('source declares highliteTag method', () => {
  const src = readSource();
  assert.ok(/highliteTag\s*\(/.test(src),
    'should declare highliteTag() method');
});

test('highliteTag uses highlite_tag CSS class', () => {
  const src = readSource();
  assert.ok(/highlite_tag/.test(src),
    'should use highlite_tag CSS class in spans');
});

test('source declares stripGlobalStyles method', () => {
  const src = readSource();
  assert.ok(/stripGlobalStyles\s*\(/.test(src),
    'should declare stripGlobalStyles() method');
});

test('stripGlobalStyles removes style tags via regex', () => {
  const src = readSource();
  assert.ok(/<style[\s\S]*?<\/style>/.test(src) || /<style/.test(src),
    'should strip <style> tags');
});

test('stripGlobalStyles removes stylesheet links via regex', () => {
  const src = readSource();
  assert.ok(/stylesheet/.test(src),
    'should strip stylesheet <link> tags');
});

test('source declares dangerHTML method', () => {
  const src = readSource();
  assert.ok(/dangerHTML\s*\(/.test(src),
    'should declare dangerHTML() method');
});

test('dangerHTML returns object with __html key', () => {
  const src = readSource();
  assert.ok(/__html/.test(src),
    'should return __html object for dangerouslySetInnerHTML');
});

test('source declares getNode method', () => {
  const src = readSource();
  assert.ok(/getNode\s*\(/.test(src),
    'should declare getNode() method');
});

test('getNode stores node reference as this.node', () => {
  const src = readSource();
  assert.ok(/this\.node\s*=\s*node/.test(src),
    'should store node as this.node');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidUpdate lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidUpdate\s*\(\s*\)\s*\{/.test(src),
    'should declare componentDidUpdate() method');
});

test('componentDidUpdate checks post.current and showed state', () => {
  const src = readSource();
  assert.ok(/this\.state\.post\.current/.test(src),
    'should check state.post.current');
});

test('componentDidUpdate calls window.scrollTo', () => {
  const src = readSource();
  assert.ok(/window\.scrollTo/.test(src),
    'should call window.scrollTo');
});

test('componentDidUpdate uses node.offsetTop', () => {
  const src = readSource();
  assert.ok(/this\.node\.offsetTop/.test(src),
    'should use this.node.offsetTop for scroll position');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render returns div with post CSS class', () => {
  const src = readSource();
  assert.ok(/className.*['"]post['"]/.test(src) || /className.*['"]post /.test(src),
    'should render div with "post" class');
});

test('render uses current_post class conditionally', () => {
  const src = readSource();
  assert.ok(/current_post/.test(src),
    'should conditionally apply current_post class');
});

test('render uses ref callback with getNode', () => {
  const src = readSource();
  assert.ok(/ref\s*=\s*\{?\s*this\.getNode/.test(src),
    'should use getNode as ref callback');
});

test('render sets onClick to setCurrent on main div', () => {
  const src = readSource();
  assert.ok(/onClick\s*=\s*\{?\s*this\.setCurrent/.test(src),
    'should bind onClick to setCurrent');
});

test('render includes anchor with post position name', () => {
  const src = readSource();
  assert.ok(/<a name/.test(src),
    'should include anchor with name attribute');
});

test('render includes post_title CSS class', () => {
  const src = readSource();
  assert.ok(/post_title/.test(src),
    'should use post_title CSS class');
});

test('render includes post_title_link CSS class', () => {
  const src = readSource();
  assert.ok(/post_title_link/.test(src),
    'should use post_title_link CSS class');
});

test('render uses dangerouslySetInnerHTML for title', () => {
  const src = readSource();
  assert.ok(/dangerouslySetInnerHTML/.test(src),
    'should use dangerouslySetInnerHTML for HTML content');
});

test('render includes post_meta CSS class', () => {
  const src = readSource();
  assert.ok(/post_meta/.test(src),
    'should use post_meta CSS class');
});

test('render includes post_feed_title CSS class', () => {
  const src = readSource();
  assert.ok(/post_feed_title/.test(src),
    'should use post_feed_title CSS class');
});

test('render includes post-content-isolated wrapper', () => {
  const src = readSource();
  assert.ok(/post-content-isolated/.test(src),
    'should use post-content-isolated wrapper class');
});

test('render includes post_content CSS class', () => {
  const src = readSource();
  assert.ok(/post_content/.test(src),
    'should use post_content CSS class');
});

test('render uses hide class conditionally for content', () => {
  const src = readSource();
  assert.ok(/hide/.test(src),
    'should conditionally apply hide class to content');
});

test('render includes post_tag_contexts CSS class', () => {
  const src = readSource();
  assert.ok(/post_tag_contexts/.test(src),
    'should use post_tag_contexts CSS class');
});

test('render includes post_tag_context_tag CSS class', () => {
  const src = readSource();
  assert.ok(/post_tag_context_tag/.test(src),
    'should use post_tag_context_tag CSS class for highlighted tags');
});

// ============================================================
// Post tools and links tests
// ============================================================

test('render includes post_tools CSS class', () => {
  const src = readSource();
  assert.ok(/post_tools/.test(src),
    'should use post_tools CSS class');
});

test('render includes post_show_content span', () => {
  const src = readSource();
  assert.ok(/post_show_content/.test(src),
    'should use post_show_content CSS class');
});

test('render shows Show/Hide post text', () => {
  const src = readSource();
  assert.ok(/Hide/.test(src) && /Show/.test(src),
    'should include Show/Hide post text');
});

test('render includes post_show_links span', () => {
  const src = readSource();
  assert.ok(/post_show_links/.test(src),
    'should use post_show_links CSS class');
});

test('render includes read_button CSS class', () => {
  const src = readSource();
  assert.ok(/read_button/.test(src),
    'should use read_button CSS class');
});

test('render uses read/unread class conditionally', () => {
  const src = readSource();
  assert.ok(/['"]read['"].*['"]unread['"]|['"]unread['"].*['"]read['"]/.test(src) ||
    (/read_button.*read/.test(src) && /read_button.*unread/.test(src)),
    'should use read/unread classes conditionally');
});

test('render includes download_button CSS class', () => {
  const src = readSource();
  assert.ok(/download_button/.test(src),
    'should use download_button CSS class');
});

test('render includes download link with /download/posts/ path', () => {
  const src = readSource();
  assert.ok(/\/download\/posts\/\$\{.*pos/.test(src),
    'should include download link with post position');
});

test('render includes post_links_content CSS class', () => {
  const src = readSource();
  assert.ok(/post_links_content/.test(src),
    'should use post_links_content CSS class');
});

// ============================================================
// Tag link rendering tests
// ============================================================

test('render includes post_tag_link CSS class', () => {
  const src = readSource();
  assert.ok(/post_tag_link/.test(src),
    'should use post_tag_link CSS class for tag links');
});

test('render includes post_tag_letter_block CSS class', () => {
  const src = readSource();
  assert.ok(/post_tag_letter_block/.test(src),
    'should use post_tag_letter_block for letter grouping');
});

test('render includes post_tag_letter CSS class', () => {
  const src = readSource();
  assert.ok(/post_tag_letter/.test(src),
    'should use post_tag_letter CSS class');
});

test('render includes Cluster link conditionally', () => {
  const src = readSource();
  assert.ok(/Cluster/.test(src),
    'should include Cluster link');
  assert.ok(/clst_url/.test(src),
    'should check clst_url for cluster link');
});

// ============================================================
// Content handling tests
// ============================================================

test('render uses No Title fallback for empty titles', () => {
  const src = readSource();
  assert.ok(/No Title/.test(src),
    'should use "No Title" for empty post titles');
});

test('render includes post position with # prefix', () => {
  const src = readSource();
  assert.ok(/#\{.*pos/.test(src),
    'should display post position with #');
});

test('render displays clusters when present', () => {
  const src = readSource();
  assert.ok(/post\.post\.clusters/.test(src) || /\.clusters/.test(src),
    'should render clusters array');
});

test('render includes "Show links" text', () => {
  const src = readSource();
  assert.ok(/Show links/.test(src),
    'should include Show links text');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});

test('source imports stopwords from libs', () => {
  const src = readSource();
  assert.ok(/import.*stopwords.*from.*libs/.test(src),
    'should import stopwords from libs');
});
