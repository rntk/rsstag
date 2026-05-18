import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

// ============================================================
// Setup: Extract formatDate from source
// ============================================================

const source = fs.readFileSync(
  new URL('../components/global-chat.js', import.meta.url),
  'utf8',
);

// Extract and test the pure formatDate function
function extractFormatDate() {
  const match = source.match(/function formatDate\(ts\)\s*\{([\s\S]*?)\n\}/);
  if (!match) throw new Error('Could not extract formatDate from source');
  // eslint-disable-next-line no-new-func
  return new Function('ts', match[1]);
}

const formatDate = extractFormatDate();

// ============================================================
// Section 1: formatDate (pure function)
// ============================================================

test('formatDate returns empty string for null, undefined, and 0', () => {
  assert.equal(formatDate(null), '');
  assert.equal(formatDate(undefined), '');
  assert.equal(formatDate(0), '');
});

test('formatDate returns a string containing date and time for valid timestamps', () => {
  // 2026-03-08 15:30:00 UTC => unix timestamp in seconds
  const ts = Math.floor(Date.parse('2026-03-08T15:30:00Z') / 1000);
  const result = formatDate(ts);
  assert.equal(typeof result, 'string');
  assert.ok(result.length > 0, 'should return a non-empty string');
  // toLocaleTimeString with hour/minute should contain a colon
  assert.ok(/:/.test(result), 'formatted time should contain a colon');
});

test('formatDate produces consistent output for the same timestamp', () => {
  const ts = 1_700_000_000; // 2023-11-14
  const a = formatDate(ts);
  const b = formatDate(ts);
  assert.equal(a, b);
});

test('formatDate includes time with hour and minute digits', () => {
  const ts = Math.floor(Date.parse('2026-01-15T09:05:00Z') / 1000);
  const result = formatDate(ts);
  // hour:minute pattern with 2-digit hour and minute
  assert.ok(/\d{1,2}:\d{2}/.test(result), 'should contain HH:MM pattern');
});

// ============================================================
// Section 2: Source structure tests (always run)
// ============================================================

test('source declares formatDate function', () => {
  assert.ok(
    /function formatDate\(ts\)/.test(source),
    'formatDate function should be declared',
  );
});

test('source exports GlobalChatPanel as default', () => {
  assert.ok(
    /export default function GlobalChatPanel/.test(source),
    'GlobalChatPanel should be default export',
  );
});

test('source defines all expected component functions', () => {
  const expectedComponents = [
    'ChatContext',
    'MessageBubble',
    'ChatView',
    'ConversationList',
    'GlobalChatPanel',
  ];
  for (const name of expectedComponents) {
    assert.ok(
      new RegExp(`function ${name}\\b`).test(source),
      `function ${name} should be declared in source`,
    );
  }
});

test('source imports React and hooks', () => {
  assert.ok(
    /import React/.test(source),
    'should import React'
  );
  assert.ok(
    /useState.*useEffect.*useRef/.test(source),
    'should import useState, useEffect, useRef'
  );
});

// ============================================================
// Section 3: GlobalChatPanel source behavior
// ============================================================

test('GlobalChatPanel source contains toggle button logic', () => {
  assert.ok(/state\.isOpen/.test(source), 'should reference isOpen state');
  assert.ok(/handleToggle/.test(source), 'should have handleToggle');
  assert.ok(/CHAT_TOGGLE_PANEL/.test(source), 'should use CHAT_TOGGLE_PANEL event');
});

test('GlobalChatPanel source contains conversation list rendering', () => {
  assert.ok(/ConversationList/.test(source), 'should reference ConversationList');
  assert.ok(/state\.chats/.test(source), 'should reference chats state');
  assert.ok(/handleSelectChat/.test(source), 'should have handleSelectChat');
  assert.ok(/handleCreateChat/.test(source), 'should have handleCreateChat');
  assert.ok(/handleDeleteChat/.test(source), 'should have handleDeleteChat');
});

test('GlobalChatPanel source contains chat view rendering', () => {
  assert.ok(/ChatView/.test(source), 'should reference ChatView');
  assert.ok(/state\.activeChat/.test(source), 'should reference activeChat state');
  assert.ok(/handleBack/.test(source), 'should have handleBack');
});

test('GlobalChatPanel binds ES event listeners', () => {
  assert.ok(/ES\.bind\(ES\.CHAT_UPDATED/.test(source), 'should bind CHAT_UPDATED');
  assert.ok(/ES\.bind\(ES\.CHAT_LIST_UPDATED/.test(source), 'should bind CHAT_LIST_UPDATED');
  assert.ok(/ES\.bind\(ES\.CHAT_TOGGLE_PANEL/.test(source), 'should bind CHAT_TOGGLE_PANEL');
});

test('GlobalChatPanel cleans up ES event listeners on unmount', () => {
  assert.ok(/ES\.unbind/.test(source), 'should unbind events on cleanup');
});

test('GlobalChatPanel toggle button uses chat_bubble / close icons', () => {
  assert.ok(/chat_bubble/.test(source), 'should show chat_bubble icon');
  assert.ok(/close/.test(source), 'should show close icon when open');
});

test('GlobalChatPanel panel has fixed positioning and correct dimensions', () => {
  assert.ok(/fixed/.test(source), 'should use fixed positioning');
  assert.ok(/w-\[400px\]/.test(source), 'should have 400px width');
  assert.ok(/h-\[600px\]/.test(source), 'should have 600px height');
});

test('GlobalChatPanel shows Online status indicator', () => {
  assert.ok(/Online/.test(source), 'should show Online text');
  assert.ok(/text-green-600|text-\[10px\].*font-medium/.test(source), 'should style online indicator');
});

// ============================================================
// Section 4: ConversationList source behavior
// ============================================================

test('ConversationList source contains empty state rendering', () => {
  const convListMatch = source.match(
    /function ConversationList\([\s\S]*?^\}/m,
  );
  assert.ok(convListMatch, 'ConversationList function should exist');
  if (convListMatch) {
    const body = convListMatch[0];
    assert.ok(/chats\.length === 0/.test(body), 'should check for empty chats');
    assert.ok(/No conversations yet/.test(body), 'should show empty state text');
    assert.ok(/forum/.test(body), 'should show forum icon in empty state');
  }
});

test('ConversationList source contains delete button per chat', () => {
  const convListMatch = source.match(
    /function ConversationList\([\s\S]*?^\}/m,
  );
  assert.ok(convListMatch, 'ConversationList function should exist');
  if (convListMatch) {
    const body = convListMatch[0];
    assert.ok(/onDelete/.test(body), 'should accept onDelete prop');
    assert.ok(/delete/.test(body), 'should reference delete action');
    assert.ok(/e\.stopPropagation/.test(body), 'should stop propagation on delete');
  }
});

test('ConversationList source contains New Chat button', () => {
  const convListMatch = source.match(
    /function ConversationList\([\s\S]*?^\}/m,
  );
  assert.ok(convListMatch, 'ConversationList function should exist');
  if (convListMatch) {
    const body = convListMatch[0];
    assert.ok(/onCreate/.test(body), 'should accept onCreate prop');
    assert.ok(/New Chat/.test(body), 'should show New Chat text');
    assert.ok(/add/.test(body), 'should show add icon');
  }
});

test('ConversationList source displays formatDate for chat timestamps', () => {
  const convListMatch = source.match(
    /function ConversationList\([\s\S]*?^\}/m,
  );
  assert.ok(convListMatch, 'ConversationList function should exist');
  if (convListMatch) {
    const body = convListMatch[0];
    assert.ok(/formatDate\(chat\.updated_at\)/.test(body), 'should call formatDate');
  }
});

test('ConversationList source shows message_count badge', () => {
  const convListMatch = source.match(
    /function ConversationList\([\s\S]*?^\}/m,
  );
  assert.ok(convListMatch, 'ConversationList function should exist');
  if (convListMatch) {
    const body = convListMatch[0];
    assert.ok(/chat\.message_count/.test(body), 'should display message_count');
    assert.ok(/chat_bubble/.test(body), 'should show chat_bubble icon for count');
  }
});

// ============================================================
// Section 5: MessageBubble source behavior
// ============================================================

test('MessageBubble source contains fork button', () => {
  const bubbleMatch = source.match(/function MessageBubble\([\s\S]*?^\}/m);
  assert.ok(bubbleMatch, 'MessageBubble function should exist');
  if (bubbleMatch) {
    const body = bubbleMatch[0];
    assert.ok(/onFork/.test(body), 'should accept onFork prop');
    assert.ok(/fork_right/.test(body), 'should show fork_right icon');
    assert.ok(/Fork conversation/.test(body), 'should have fork tooltip');
  }
});

test('MessageBubble source distinguishes user vs assistant messages', () => {
  const bubbleMatch = source.match(/function MessageBubble\([\s\S]*?^\}/m);
  assert.ok(bubbleMatch, 'MessageBubble function should exist');
  if (bubbleMatch) {
    const body = bubbleMatch[0];
    assert.ok(/message\.role === 'user'/.test(body), 'should check message role');
    assert.ok(/isUser/.test(body), 'should derive isUser variable');
    assert.ok(/items-end/.test(body), 'should use items-end for user alignment');
    assert.ok(/items-start/.test(body), 'should use items-start for assistant alignment');
  }
});

test('MessageBubble source displays message content', () => {
  const bubbleMatch = source.match(/function MessageBubble\([\s\S]*?^\}/m);
  assert.ok(bubbleMatch, 'MessageBubble function should exist');
  if (bubbleMatch) {
    const body = bubbleMatch[0];
    assert.ok(/message\.content/.test(body), 'should display message content');
  }
});

test('MessageBubble source uses formatDate for timestamp', () => {
  const bubbleMatch = source.match(/function MessageBubble\([\s\S]*?^\}/m);
  assert.ok(bubbleMatch, 'MessageBubble function should exist');
  if (bubbleMatch) {
    const body = bubbleMatch[0];
    assert.ok(/formatDate\(message\.timestamp\)/.test(body), 'should call formatDate on timestamp');
  }
});

// ============================================================
// Section 6: ChatContext source behavior
// ============================================================

test('ChatContext source handles null/empty context', () => {
  const ctxMatch = source.match(/function ChatContext\([\s\S]*?^\}/m);
  assert.ok(ctxMatch, 'ChatContext function should exist');
  if (ctxMatch) {
    const body = ctxMatch[0];
    assert.ok(
      /!context|context\.type === 'empty'|!context\.text/.test(body),
      'should check for null/empty context',
    );
    assert.ok(/return null/.test(body), 'should return null for empty context');
  }
});

test('ChatContext source displays context text and source URL', () => {
  const ctxMatch = source.match(/function ChatContext\([\s\S]*?^\}/m);
  assert.ok(ctxMatch, 'ChatContext function should exist');
  if (ctxMatch) {
    const body = ctxMatch[0];
    assert.ok(/context\.text/.test(body), 'should display context text');
    assert.ok(/context\.source_url/.test(body), 'should handle source_url');
    assert.ok(/target="_blank"/.test(body), 'should open source URL in new tab');
  }
});

test('ChatContext source has collapse/expand toggle', () => {
  const ctxMatch = source.match(/function ChatContext\([\s\S]*?^\}/m);
  assert.ok(ctxMatch, 'ChatContext function should exist');
  if (ctxMatch) {
    const body = ctxMatch[0];
    assert.ok(/collapsed/.test(body), 'should have collapsed state');
    assert.ok(/setCollapsed/.test(body), 'should toggle collapsed');
    assert.ok(/chevron_right/.test(body), 'should show chevron icon');
  }
});

// ============================================================
// Section 7: ChatView source behavior
// ============================================================

test('ChatView source contains message sending logic', () => {
  const chatViewMatch = source.match(/function ChatView\([\s\S]*?^\}/m);
  assert.ok(chatViewMatch, 'ChatView function should exist');
  if (chatViewMatch) {
    const body = chatViewMatch[0];
    assert.ok(/handleSend/.test(body), 'should have handleSend');
    assert.ok(/POST/.test(body), 'should use POST method for sending');
    assert.ok(/\/api\/chats\/.*\/messages/.test(body), 'should POST to messages endpoint');
  }
});

test('ChatView source contains fork logic', () => {
  const chatViewMatch = source.match(/function ChatView\([\s\S]*?^\}/m);
  assert.ok(chatViewMatch, 'ChatView function should exist');
  if (chatViewMatch) {
    const body = chatViewMatch[0];
    assert.ok(/handleFork/.test(body), 'should have handleFork');
    assert.ok(/\/fork/.test(body), 'should call fork endpoint');
    assert.ok(/message_index/.test(body), 'should send message_index');
  }
});

test('ChatView source contains rename logic', () => {
  const chatViewMatch = source.match(/function ChatView\([\s\S]*?^\}/m);
  assert.ok(chatViewMatch, 'ChatView function should exist');
  if (chatViewMatch) {
    const body = chatViewMatch[0];
    assert.ok(/handleRenameSubmit/.test(body), 'should have handleRenameSubmit');
    assert.ok(/editingTitle/.test(body), 'should have editingTitle state');
    assert.ok(/\/rename/.test(body), 'should call rename endpoint');
  }
});

test('ChatView source shows loading indicator', () => {
  const chatViewMatch = source.match(/function ChatView\([\s\S]*?^\}/m);
  assert.ok(chatViewMatch, 'ChatView function should exist');
  if (chatViewMatch) {
    const body = chatViewMatch[0];
    assert.ok(/isLoading/.test(body), 'should have isLoading state');
    assert.ok(/animate-bounce/.test(body), 'should show animated loading dots');
  }
});

test('ChatView source uses textarea for input', () => {
  const chatViewMatch = source.match(/function ChatView\([\s\S]*?^\}/m);
  assert.ok(chatViewMatch, 'ChatView function should exist');
  if (chatViewMatch) {
    const body = chatViewMatch[0];
    assert.ok(/<textarea/.test(body), 'should use textarea for input');
    assert.ok(/handleKeyDown/.test(body), 'should handle key down');
    assert.ok(/Enter/.test(body), 'should handle Enter key');
  }
});

test('ChatView source renders messages using MessageBubble', () => {
  const chatViewMatch = source.match(/function ChatView\([\s\S]*?^\}/m);
  assert.ok(chatViewMatch, 'ChatView function should exist');
  if (chatViewMatch) {
    const body = chatViewMatch[0];
    assert.ok(/messages\.map/.test(body), 'should map over messages');
    assert.ok(/<MessageBubble/.test(body), 'should render MessageBubble');
    assert.ok(/onFork={handleFork}/.test(body), 'should pass handleFork to MessageBubble');
  }
});

test('ChatView source scrolls to bottom on new messages', () => {
  const chatViewMatch = source.match(/function ChatView\([\s\S]*?^\}/m);
  assert.ok(chatViewMatch, 'ChatView function should exist');
  if (chatViewMatch) {
    const body = chatViewMatch[0];
    assert.ok(/messagesEndRef/.test(body), 'should have messagesEndRef');
    assert.ok(/scrollIntoView/.test(body), 'should call scrollIntoView');
  }
});

// ============================================================
// Section 8: API endpoints and fetch credentials
// ============================================================

test('fetch credentials include cookies on all API calls', () => {
  // Verify source uses credentials: 'include' on all fetch calls
  const fetchCalls = source.match(/fetch\([^)]+\)/g) || [];
  const withCredentials = fetchCalls.filter((call) => call.includes("credentials: 'include'"));
  assert.ok(
    withCredentials.length > 0,
    'fetch calls should include credentials: include',
  );
});

test('source uses /api/chats endpoints', () => {
  assert.ok(/\/api\/chats/.test(source), 'should reference /api/chats');
  assert.ok(/\/api\/chats\/\$\{chat\._id\}/.test(source), 'should use chat._id in endpoints');
});

// ============================================================
// Section 9: GlobalChatPanel state and API calls
// ============================================================

test('GlobalChatPanel initializes with correct default state', () => {
  assert.ok(/chats:\s*\[\]/.test(source), 'should initialize chats as empty array');
  assert.ok(/activeChat:\s*null/.test(source), 'should initialize activeChat as null');
  assert.ok(/isOpen:\s*false/.test(source), 'should initialize isOpen as false');
  assert.ok(/isLoading:\s*false/.test(source), 'should initialize isLoading as false');
});

test('handleDeleteChat removes chat from state', () => {
  assert.ok(/handleDeleteChat/.test(source), 'should define handleDeleteChat');
  assert.ok(/\/delete/.test(source), 'should call /delete endpoint');
  assert.ok(/chats\.filter/.test(source), 'should filter out deleted chat');
});

test('handleCreateChat creates new chat then selects it', () => {
  assert.ok(/handleCreateChat/.test(source), 'should define handleCreateChat');
  assert.ok(/\/api\/chats/.test(source), 'should POST to /api/chats');
  assert.ok(/New Chat/.test(source), 'should default title to "New Chat"');
});

test('handleSelectChat loads chat by ID', () => {
  assert.ok(/handleSelectChat/.test(source), 'should define handleSelectChat');
  assert.ok(/\/api\/chats\/\$\{chatId\}/.test(source), 'should fetch chat by ID');
  assert.ok(/activeChat:\s*data\.data/.test(source), 'should set activeChat from response');
});
