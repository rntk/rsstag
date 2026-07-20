import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'post-chat.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// PostChat class tests
// ============================================================

test('source exports PostChat as a named class', () => {
  const src = readSource();
  assert.ok(
    /export class PostChat extends React\.Component/.test(src),
    'should export class PostChat extending React.Component'
  );
});

test('PostChat constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src), 'should have constructor(props)');
});

test('PostChat constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src), 'should call super(props)');
});

// ============================================================
// State initialization tests
// ============================================================

test('PostChat initializes state with empty message', () => {
  const src = readSource();
  assert.ok(/message\s*:\s*['']['']/.test(src), 'should set state.message to empty string');
});

test('PostChat initializes state with empty response', () => {
  const src = readSource();
  assert.ok(/response\s*:\s*['']['']/.test(src), 'should set state.response to empty string');
});

test('PostChat initializes state with isLoading false', () => {
  const src = readSource();
  assert.ok(/isLoading\s*:\s*false/.test(src), 'should set state.isLoading to false');
});

test('PostChat constructor binds handleChange method', () => {
  const src = readSource();
  assert.ok(
    /this\.handleChange\s*=\s*this\.handleChange\.bind\(this\)/.test(src),
    'should bind handleChange'
  );
});

test('PostChat constructor binds handleSubmit method', () => {
  const src = readSource();
  assert.ok(
    /this\.handleSubmit\s*=\s*this\.handleSubmit\.bind\(this\)/.test(src),
    'should bind handleSubmit'
  );
});

// ============================================================
// handleChange method tests
// ============================================================

test('source declares handleChange method', () => {
  const src = readSource();
  assert.ok(
    /handleChange\s*\(\s*event\s*\)/.test(src),
    'should declare handleChange(event) method'
  );
});

test('handleChange sets message from event.target.value', () => {
  const src = readSource();
  assert.ok(
    /this\.setState\s*\(\s*\{\s*message\s*:\s*event\.target\.value/.test(src),
    'should set message from event.target.value'
  );
});

// ============================================================
// handleSubmit method tests
// ============================================================

test('source declares handleSubmit method', () => {
  const src = readSource();
  assert.ok(
    /handleSubmit\s*\(\s*event\s*\)/.test(src),
    'should declare handleSubmit(event) method'
  );
});

test('handleSubmit calls event.preventDefault', () => {
  const src = readSource();
  assert.ok(/event\.preventDefault\(\)/.test(src), 'should call preventDefault');
});

test('handleSubmit trims message before validation', () => {
  const src = readSource();
  assert.ok(/this\.state\.message\.trim\(\)/.test(src), 'should trim message');
});

test('handleSubmit returns early for empty message', () => {
  const src = readSource();
  assert.ok(
    /if\s*\(\s*!this\.state\.message\.trim\(\)\s*\)\s*\{?\s*return;?/.test(src),
    'should return early for empty message'
  );
});

test('handleSubmit sets isLoading to true on submit', () => {
  const src = readSource();
  assert.ok(/isLoading\s*:\s*true/.test(src), 'should set isLoading to true');
});

test('handleSubmit clears response on submit', () => {
  const src = readSource();
  assert.ok(/response\s*:\s*['']['']/.test(src), 'should clear response on submit');
});

test('handleSubmit extracts tag from props.posts.group_title', () => {
  const src = readSource();
  assert.ok(
    /const tag\s*=\s*this\.props\.posts\.group_title/.test(src),
    'should extract tag from posts.group_title'
  );
});

test('handleSubmit extracts pids from posts Map', () => {
  const src = readSource();
  assert.ok(
    /Array\.from\s*\(\s*this\.props\.posts\.posts\.values\(\)/.test(src),
    'should use Array.from on posts.values()'
  );
  assert.ok(/post\.post\.pid/.test(src), 'should extract pid from post.post');
});

test('handleSubmit builds request data with tag, pids, and user', () => {
  const src = readSource();
  assert.ok(/tag\s*:\s*tag/.test(src), 'should include tag in request');
  assert.ok(/pids\s*:\s*pids/.test(src), 'should include pids in request');
  assert.ok(/user\s*:\s*this\.state\.message/.test(src), 'should include user message in request');
});

test('handleSubmit POSTs to /chat endpoint', () => {
  const src = readSource();
  assert.ok(/fetch\s*\(\s*['"]\/chat['"]/.test(src), 'should fetch /chat');
  assert.ok(/method\s*:\s*['"]POST['"]/.test(src), 'should use POST method');
});

test('handleSubmit sets Content-Type header to application/json', () => {
  const src = readSource();
  assert.ok(/['"]Content-Type['"]/.test(src), 'should set Content-Type header');
  assert.ok(/['"]application\/json['"]/.test(src), 'should set application/json');
});

test('handleSubmit stringifies request body as JSON', () => {
  const src = readSource();
  assert.ok(
    /JSON\.stringify\s*\(\s*requestData/.test(src),
    'should use JSON.stringify on requestData'
  );
});

test('handleSubmit parses response as JSON', () => {
  const src = readSource();
  assert.ok(
    /\.then\s*\(\s*\(?\s*response\s*\)?\s*=>\s*response\.json\(\)/.test(src),
    'should call response.json()'
  );
});

test('handleSubmit checks for data.error in response', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*data\.error/.test(src), 'should check data.error');
});

test('handleSubmit sets error response with "Error: " prefix', () => {
  const src = readSource();
  assert.ok(/['"]Error: ['"]\s*\+\s*data\.error/.test(src), 'should prefix error with "Error: "');
});

test('handleSubmit sets success response from data.data', () => {
  const src = readSource();
  assert.ok(/response\s*:\s*data\.data/.test(src), 'should set response from data.data');
});

test('handleSubmit sets isLoading to false after response', () => {
  const src = readSource();
  const isLoadingResets = (src.match(/isLoading\s*:\s*false/g) || []).length;
  assert.ok(isLoadingResets >= 2, 'should reset isLoading to false in multiple places');
});

test('handleSubmit catches errors and sets error message', () => {
  const src = readSource();
  assert.ok(/\.catch\s*\(/.test(src), 'should have catch handler');
  assert.ok(
    /Error connecting to server/.test(src),
    'should include "Error connecting to server" message'
  );
  assert.ok(/error\.message/.test(src), 'should include error.message');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src), 'should declare render() method');
});

test('render uses post-chat-container CSS class', () => {
  const src = readSource();
  assert.ok(
    /className\s*=\s*['"]post-chat-container['"]/.test(src),
    'should use post-chat-container class'
  );
});

test('render displays group_title in h3 heading', () => {
  const src = readSource();
  assert.ok(/<h3>/.test(src), 'should include h3 element');
  assert.ok(/Chat with posts about:/.test(src), 'should include "Chat with posts about:" text');
  assert.ok(/this\.props\.posts\.group_title/.test(src), 'should display group_title');
});

// ============================================================
// Form and textarea tests
// ============================================================

test('render creates a form with chat-form class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]chat-form['"]/.test(src), 'should use chat-form class');
});

test('render binds onSubmit to handleSubmit', () => {
  const src = readSource();
  assert.ok(
    /onSubmit\s*=\s*\{?\s*this\.handleSubmit/.test(src),
    'should bind onSubmit to handleSubmit'
  );
});

test('render creates textarea with chat-input class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]chat-input['"]/.test(src), 'should use chat-input class');
});

test('textarea value bound to state.message', () => {
  const src = readSource();
  assert.ok(
    /value\s*=\s*\{?\s*this\.state\.message/.test(src),
    'should bind value to state.message'
  );
});

test('textarea onChange bound to handleChange', () => {
  const src = readSource();
  assert.ok(
    /onChange\s*=\s*\{?\s*this\.handleChange/.test(src),
    'should bind onChange to handleChange'
  );
});

test('textarea has placeholder text', () => {
  const src = readSource();
  assert.ok(/placeholder\s*=\s*['"]Ask a question/.test(src), 'should have placeholder text');
});

test('textarea has rows attribute', () => {
  const src = readSource();
  assert.ok(/rows\s*=\s*['"]4['"]/.test(src), 'should set rows=4');
});

// ============================================================
// Submit button tests
// ============================================================

test('render creates submit button with chat-submit class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]chat-submit['"]/.test(src), 'should use chat-submit class');
});

test('submit button disabled state tied to isLoading', () => {
  const src = readSource();
  assert.ok(
    /disabled\s*=\s*\{?\s*this\.state\.isLoading/.test(src),
    'should disable when isLoading'
  );
});

test('submit button shows "Processing..." when loading', () => {
  const src = readSource();
  assert.ok(/Processing\.\.\./.test(src), 'should include "Processing..." text');
});

test('submit button shows "Send" when not loading', () => {
  const src = readSource();
  assert.ok(/'Send'/.test(src), 'should include "Send" text');
});

// ============================================================
// Loading indicator tests
// ============================================================

test('render conditionally shows loading indicator', () => {
  const src = readSource();
  assert.ok(/this\.state\.isLoading\s*&&/.test(src), 'should conditionally render on isLoading');
});

test('render uses loading-indicator CSS class', () => {
  const src = readSource();
  assert.ok(
    /className\s*=\s*['"]loading-indicator['"]/.test(src),
    'should use loading-indicator class'
  );
});

test('loading indicator shows "Processing your request..." text', () => {
  const src = readSource();
  assert.ok(
    /Processing your request\.\.\./.test(src),
    'should include "Processing your request..."'
  );
});

// ============================================================
// Response display tests
// ============================================================

test('render conditionally shows response when present', () => {
  const src = readSource();
  assert.ok(/this\.state\.response\s*&&/.test(src), 'should conditionally render on response');
});

test('render uses chat-response CSS class', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]chat-response['"]/.test(src), 'should use chat-response class');
});

test('response section includes h4 "Response:" heading', () => {
  const src = readSource();
  assert.ok(/<h4>Response:<\/h4>/.test(src), 'should include <h4>Response:</h4>');
});

test('render uses response-content CSS class', () => {
  const src = readSource();
  assert.ok(
    /className\s*=\s*['"]response-content['"]/.test(src),
    'should use response-content class'
  );
});

// ============================================================
// PostChatS default export tests
// ============================================================

test('source has default export function PostChatS', () => {
  const src = readSource();
  assert.ok(
    /export default function PostChatS\s*\(\s*posts/.test(src),
    'should export default function PostChatS(posts)'
  );
});

test('PostChatS returns PostChat with posts prop', () => {
  const src = readSource();
  assert.ok(/<PostChat posts=\{posts\}/.test(src), 'should return <PostChat posts={posts} />');
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
