import test from 'node:test';
import assert from 'node:assert/strict';

import ChatStorage from '../storages/chat-storage.js';

function createChatEventSystem() {
  const bindings = new Map();
  const calls = [];

  return {
    bindings,
    calls,
    CHAT_LIST_UPDATED: 'chat_list_updated',
    CHAT_UPDATED: 'chat_updated',
    CHAT_TOGGLE_PANEL: 'chat_toggle_panel',
    CHAT_START_WITH_CONTEXT: 'chat_start_with_context',
    bind(event, handler) {
      const handlers = bindings.get(event) || [];
      handlers.push(handler);
      bindings.set(event, handlers);
    },
    trigger(event, payload) {
      calls.push({ event, payload });
      const handlers = bindings.get(event) || [];
      handlers.forEach((handler) => handler(payload));
    },
  };
}

function createFetchResponse(data) {
  return {
    async json() {
      return data;
    },
  };
}

test('start() binds events and triggers initial fetchChats()', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);

  let fetchChatsCalls = 0;
  storage.fetchChats = async () => {
    fetchChatsCalls += 1;
  };

  storage.start();

  assert.equal(fetchChatsCalls, 1);
  assert.equal(es.bindings.has(es.CHAT_TOGGLE_PANEL), true);
  assert.equal(es.bindings.has(es.CHAT_START_WITH_CONTEXT), true);

  const originalCreateChat = storage.createChat;
  let contextArg = null;
  storage.createChat = async (context) => {
    contextArg = context;
    return 'created';
  };
  t.after(() => {
    storage.createChat = originalCreateChat;
  });

  es.trigger(es.CHAT_START_WITH_CONTEXT, 'from-start');
  await Promise.resolve();

  assert.equal(contextArg, 'from-start');
});

test('fetchChats() success updates chats, clears loading, emits CHAT_LIST_UPDATED', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;

  global.fetch = async (url) => {
    assert.equal(url, storage.urls.list);
    return createFetchResponse({ data: [{ _id: 'chat-1' }, { _id: 'chat-2' }] });
  };

  t.after(() => {
    global.fetch = originalFetch;
  });

  await storage.fetchChats();

  assert.equal(storage.getState().isLoading, false);
  assert.deepEqual(storage.getState().chats, [{ _id: 'chat-1' }, { _id: 'chat-2' }]);
  assert.deepEqual(es.calls.at(-1), {
    event: es.CHAT_LIST_UPDATED,
    payload: storage.getState(),
  });
});

test('fetchChats() failure clears loading without throwing', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async (url) => {
    assert.equal(url, storage.urls.list);
    throw new Error('network failed');
  };
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  await storage.fetchChats();

  assert.equal(storage.getState().isLoading, false);
});

test('createChat(context) sends payload, chains loadChat/fetchChats, opens panel, emits CHAT_UPDATED, and returns id', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;

  let loadChatArg = null;
  let fetchChatsCalls = 0;
  storage.loadChat = async (chatId) => {
    loadChatArg = chatId;
  };
  storage.fetchChats = async () => {
    fetchChatsCalls += 1;
  };

  global.fetch = async (url, options) => {
    assert.equal(url, storage.urls.create);
    assert.equal(options.method, 'POST');
    assert.equal(options.credentials, 'include');
    assert.equal(options.headers['Content-Type'], 'application/json');
    assert.equal(options.body, JSON.stringify({ title: 'New Chat', context: 'ctx-value' }));

    return createFetchResponse({ data: { chat_id: 'chat-42' } });
  };

  t.after(() => {
    global.fetch = originalFetch;
  });

  const chatId = await storage.createChat('ctx-value');

  assert.equal(chatId, 'chat-42');
  assert.equal(loadChatArg, 'chat-42');
  assert.equal(fetchChatsCalls, 1);
  assert.equal(storage.getState().isOpen, true);
  assert.equal(es.calls.at(-1).event, es.CHAT_UPDATED);
});

test('createChat(context) returns null on API error', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async (url) => {
    assert.equal(url, storage.urls.create);
    return createFetchResponse({ error: 'boom' });
  };
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const chatId = await storage.createChat('ctx');

  assert.equal(chatId, null);
  assert.equal(storage.getState().isLoading, false);
});

test('sendMessage(chatId, content) posts to messages URL, updates messages through reload path, and emits CHAT_UPDATED', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;

  storage._setState({
    activeChat: {
      _id: 'chat-3',
      messages: [{ role: 'assistant', content: 'hello' }],
    },
  });

  global.fetch = async (url, options) => {
    if (url === storage.urls.messages('chat-3')) {
      assert.equal(options.method, 'POST');
      assert.equal(options.body, JSON.stringify({ content: 'How are you?' }));
      return createFetchResponse({ data: { message_id: 'msg-1' } });
    }

    if (url === storage.urls.detail('chat-3')) {
      return createFetchResponse({
        data: {
          _id: 'chat-3',
          messages: [
            { role: 'assistant', content: 'hello' },
            { role: 'user', content: 'How are you?' },
            { role: 'assistant', content: 'I am well.' },
          ],
        },
      });
    }

    if (url === storage.urls.list) {
      return createFetchResponse({ data: [{ _id: 'chat-3' }] });
    }

    throw new Error(`Unexpected URL: ${url}`);
  };

  t.after(() => {
    global.fetch = originalFetch;
  });

  const result = await storage.sendMessage('chat-3', 'How are you?');

  assert.deepEqual(result, { message_id: 'msg-1' });
  assert.deepEqual(storage.getState().activeChat.messages, [
    { role: 'assistant', content: 'hello' },
    { role: 'user', content: 'How are you?' },
    { role: 'assistant', content: 'I am well.' },
  ]);
  assert.equal(es.calls.some((call) => call.event === es.CHAT_UPDATED), true);
});

test('sendMessage(chatId, content) handles API error response path', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async (url) => {
    assert.equal(url, storage.urls.messages('chat-x'));
    return createFetchResponse({ error: 'bad request' });
  };
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const result = await storage.sendMessage('chat-x', 'content');

  assert.equal(result, null);
  assert.equal(storage.getState().isLoading, false);
});

test('bindEvents() handles CHAT_TOGGLE_PANEL and CHAT_START_WITH_CONTEXT', async () => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);

  let receivedContext = null;
  storage.createChat = async (context) => {
    receivedContext = context;
    return 'chat-created';
  };

  storage.bindEvents();

  es.trigger(es.CHAT_TOGGLE_PANEL);
  assert.equal(storage.getState().isOpen, true);

  es.trigger(es.CHAT_START_WITH_CONTEXT, 'topic context');
  await Promise.resolve();

  assert.equal(storage.getState().isOpen, true);
  assert.equal(receivedContext, 'topic context');
  assert.equal(es.calls.filter((call) => call.event === es.CHAT_UPDATED).length >= 2, true);
});
