import assert from 'node:assert/strict';
import test from 'node:test';

import EventsSystem from '../libs/event_system.js';
import SettingsStorage from '../storages/settings-storage.js';

class SpyEventSystem extends EventsSystem {
  constructor() {
    super();
    this.bound = [];
    this.triggered = [];
  }

  bind(eventName, handler) {
    this.bound.push([eventName, handler]);
  }

  trigger(eventName, payload) {
    this.triggered.push([eventName, payload]);
  }
}

test('fetchSettings reads window.rss_settings and emits SETTINGS_UPDATED', () => {
  const es = new SpyEventSystem();
  const storage = new SettingsStorage(es);
  const prevWindow = globalThis.window;

  globalThis.window = {
    rss_settings: {
      only_unread: true,
      tags_on_page: 50,
    },
  };

  try {
    storage.fetchSettings();

    assert.deepEqual(storage.getState(), {
      settings: {
        only_unread: true,
        tags_on_page: 50,
      },
      offset: {},
      showed: false,
    });
    assert.deepEqual(es.triggered, [[es.SETTINGS_UPDATED, storage.getState()]]);
  } finally {
    globalThis.window = prevWindow;
  }
});

test('changeSettingsWindowState toggles showed and stores optional offset', () => {
  const es = new SpyEventSystem();
  const storage = new SettingsStorage(es);

  storage.changeSettingsWindowState({ x: 10, y: 20 });
  assert.equal(storage.getState().showed, true);
  assert.deepEqual(storage.getState().offset, { x: 10, y: 20 });

  storage.changeSettingsWindowState();
  assert.equal(storage.getState().showed, false);
  assert.deepEqual(storage.getState().offset, { x: 10, y: 20 });
});

test('saveSettings posts to /settings and updates state + closes panel on success', async () => {
  const es = new SpyEventSystem();
  const storage = new SettingsStorage(es);
  const previousFetch = globalThis.fetch;
  const settings = { posts_on_page: 100, only_unread: false };

  storage.setState({ settings: {}, offset: {}, showed: true });
  es.triggered = [];

  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/settings');
    assert.equal(options.method, 'POST');
    assert.equal(options.credentials, 'include');
    assert.equal(options.headers['Content-Type'], 'application/json');
    assert.equal(options.body, JSON.stringify(settings));

    return {
      async json() {
        return { data: true };
      },
    };
  };

  try {
    storage.saveSettings(settings);
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(storage.getState().showed, false);
    assert.deepEqual(storage.getState().settings, settings);
    assert.deepEqual(
      es.triggered.map((call) => call[0]),
      [es.SETTINGS_UPDATED, es.SETTINGS_UPDATED],
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('saveSettings emits rollback + error message trigger on API failure', async () => {
  const es = new SpyEventSystem();
  const storage = new SettingsStorage(es);
  const previousFetch = globalThis.fetch;
  const previousLog = console.log;

  storage.setState({ settings: { only_unread: true }, offset: {}, showed: true });
  es.triggered = [];

  globalThis.fetch = async () => ({
    async json() {
      return { data: false };
    },
  });
  console.log = () => {};

  try {
    storage.saveSettings({ only_unread: false });
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(storage.getState().showed, true);
    assert.deepEqual(storage.getState().settings, { only_unread: true });
    assert.deepEqual(es.triggered, [
      [es.SETTINGS_UPDATED, storage.getState()],
      [es.SETTINGS_ERROR_MESSAGE, 'Error. Try later'],
    ]);
  } finally {
    globalThis.fetch = previousFetch;
    console.log = previousLog;
  }
});

test('saveTelegramCode and saveTelegramPassword send expected payload to /telegram-auth', async () => {
  const es = new SpyEventSystem();
  const storage = new SettingsStorage(es);
  const previousFetch = globalThis.fetch;
  const calls = [];

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      async json() {
        return { data: true };
      },
    };
  };

  try {
    storage.saveTelegramCode('123456');
    storage.saveTelegramPassword('my-password');
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(calls.length, 2);
    assert.equal(calls[0].url, '/telegram-auth');
    assert.equal(calls[0].options.method, 'POST');
    assert.equal(calls[0].options.body, JSON.stringify({ telegram_code: '123456' }));

    assert.equal(calls[1].url, '/telegram-auth');
    assert.equal(calls[1].options.method, 'POST');
    assert.equal(calls[1].options.body, JSON.stringify({ telegram_password: 'my-password' }));
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('bindEvents registers handlers for settings/telegram actions', () => {
  const es = new SpyEventSystem();
  const storage = new SettingsStorage(es);

  storage.bindEvents();

  assert.deepEqual(
    es.bound.map(([eventName]) => eventName),
    [
      es.UPDATE_SETTINGS,
      es.CHANGE_SETTINGS_WINDOW_STATE,
      es.SAVE_TELEGRAM_CODE,
      es.SAVE_TELEGRAM_PASSWORD,
    ],
  );
});
