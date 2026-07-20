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
  assert.equal(
    es.calls.some((call) => call.event === es.CHAT_UPDATED),
    true
  );
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

test('fetchChats() with empty response sets empty chats array', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;

  global.fetch = async () => createFetchResponse({ data: [] });

  t.after(() => {
    global.fetch = originalFetch;
  });

  await storage.fetchChats();

  assert.deepEqual(storage.getState().chats, []);
  assert.equal(storage.getState().isLoading, false);
});

test('fetchChats() with response missing data key defaults to empty array', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;

  global.fetch = async () => createFetchResponse({});

  t.after(() => {
    global.fetch = originalFetch;
  });

  await storage.fetchChats();

  assert.deepEqual(storage.getState().chats, []);
});

test('loadChat() success sets activeChat and emits CHAT_UPDATED', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;

  global.fetch = async (url) => {
    if (url === storage.urls.detail('chat-1')) {
      return createFetchResponse({
        data: { _id: 'chat-1', title: 'My Chat', messages: [{ role: 'user', content: 'hi' }] },
      });
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  t.after(() => {
    global.fetch = originalFetch;
  });

  await storage.loadChat('chat-1');

  assert.deepEqual(storage.getState().activeChat, {
    _id: 'chat-1',
    title: 'My Chat',
    messages: [{ role: 'user', content: 'hi' }],
  });
  assert.equal(storage.getState().isLoading, false);
  assert.equal(es.calls.at(-1).event, es.CHAT_UPDATED);
});

test('loadChat() API error response clears loading without throwing', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async () => createFetchResponse({ error: 'chat not found' });
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  await storage.loadChat('nonexistent');

  assert.equal(storage.getState().isLoading, false);
  assert.equal(storage.getState().activeChat, null);
});

test('loadChat() network error clears loading without throwing', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async () => {
    throw new Error('connection refused');
  };
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  await storage.loadChat('chat-1');

  assert.equal(storage.getState().isLoading, false);
});

test('renameChat() success updates activeChat title and returns true', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;

  storage._setState({ activeChat: { _id: 'chat-1', title: 'Old Title' } });

  global.fetch = async (url) => {
    if (url === storage.urls.rename('chat-1')) {
      return createFetchResponse({ data: true });
    }
    if (url === storage.urls.list) {
      return createFetchResponse({ data: [{ _id: 'chat-1' }] });
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  t.after(() => {
    global.fetch = originalFetch;
  });

  const result = await storage.renameChat('chat-1', 'New Title');

  assert.equal(result, true);
  assert.equal(storage.getState().activeChat.title, 'New Title');
});

test('renameChat() API error returns false', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async () => createFetchResponse({ error: 'invalid title' });
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const result = await storage.renameChat('chat-1', '');

  assert.equal(result, false);
});

test('renameChat() network error returns false', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async () => {
    throw new Error('network down');
  };
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const result = await storage.renameChat('chat-1', 'New Title');

  assert.equal(result, false);
});

test('deleteChat() success clears activeChat if it matches and returns true', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;

  storage._setState({ activeChat: { _id: 'chat-9', title: 'To Delete' } });

  global.fetch = async (url) => {
    if (url === storage.urls.delete('chat-9')) {
      return createFetchResponse({ data: true });
    }
    if (url === storage.urls.list) {
      return createFetchResponse({ data: [] });
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  t.after(() => {
    global.fetch = originalFetch;
  });

  const result = await storage.deleteChat('chat-9');

  assert.equal(result, true);
  assert.equal(storage.getState().activeChat, null);
});

test('deleteChat() API error returns false', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async () => createFetchResponse({ error: 'cannot delete' });
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const result = await storage.deleteChat('chat-1');

  assert.equal(result, false);
});

test('deleteChat() network error returns false', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async () => {
    throw new Error('timeout');
  };
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const result = await storage.deleteChat('chat-1');

  assert.equal(result, false);
});

test('forkChat() success loads new chat and returns new id', async (t) => {
  const es = createChatEventSystem();
  const storage = new ChatStorage(es);
  const originalFetch = global.fetch;

  let forkBody = null;
  global.fetch = async (url, options) => {
    if (url === storage.urls.fork('chat-5')) {
      forkBody = options.body;
      return createFetchResponse({ data: { chat_id: 'forked-1' } });
    }
    if (url === storage.urls.detail('forked-1')) {
      return createFetchResponse({ data: { _id: 'forked-1', title: 'Forked', messages: [] } });
    }
    if (url === storage.urls.list) {
      return createFetchResponse({ data: [{ _id: 'chat-5' }] });
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  t.after(() => {
    global.fetch = originalFetch;
  });

  const newId = await storage.forkChat('chat-5', 3);

  assert.equal(newId, 'forked-1');
  assert.equal(forkBody, JSON.stringify({ message_index: 3 }));
});

test('forkChat() API error returns null', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async () => createFetchResponse({ error: 'cannot fork' });
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const result = await storage.forkChat('chat-1', 0);

  assert.equal(result, null);
});

test('forkChat() network error returns null', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async () => {
    throw new Error('connection reset');
  };
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const result = await storage.forkChat('chat-1', 0);

  assert.equal(result, null);
});

test('createChat() network error returns null', async (t) => {
  const storage = new ChatStorage(createChatEventSystem());
  const originalFetch = global.fetch;
  const originalConsoleError = console.error;

  global.fetch = async () => {
    throw new Error('network unreachable');
  };
  console.error = () => {};

  t.after(() => {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const result = await storage.createChat('ctx');

  assert.equal(result, null);
  assert.equal(storage.getState().isLoading, false);
});
