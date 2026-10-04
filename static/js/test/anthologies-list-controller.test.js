import { afterEach, beforeEach, expect, test, vi } from 'vitest';

import { initSeedSuggestions } from '../anthologies-list.js';

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function flush(times = 10) {
  for (let i = 0; i < times; i += 1) {
    await Promise.resolve();
  }
}

const suggestion = { tag: 'xbox', unread: 1, all: 2, info_url: '/tag-info/xbox' };

function jsonResponse(data) {
  return { json: () => Promise.resolve({ data }) };
}

function input() {
  return document.getElementById('anthology-seed-value');
}

function results() {
  return document.getElementById('anthology-seed-suggestions');
}

function type(value) {
  input().value = value;
  input().dispatchEvent(new window.Event('input', { bubbles: true }));
}

beforeEach(() => {
  vi.useFakeTimers();
  document.body.innerHTML = `
    <input id="anthology-seed-value" type="text" />
    <div id="anthology-seed-suggestions" hidden></div>
  `;
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.body.innerHTML = '';
});

test('posts the request to /tags-search and renders matches', async () => {
  const gate = deferred();
  fetch.mockReturnValue(gate.promise);
  initSeedSuggestions();

  type('xb');
  await vi.advanceTimersByTimeAsync(500);

  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe('/tags-search');
  expect(fetch.mock.calls[0][1].method).toBe('POST');
  expect(fetch.mock.calls[0][1].body.get('req')).toBe('xb');

  gate.resolve(jsonResponse([suggestion]));
  await flush();

  expect(results().hidden).toBe(false);
  expect(results().innerHTML).toContain('xbox (1 / 2)');
});

test('late response after clearing the input does not reopen the dropdown', async () => {
  const gate = deferred();
  fetch.mockReturnValue(gate.promise);
  initSeedSuggestions();

  type('xb');
  await vi.advanceTimersByTimeAsync(500);
  type('');
  gate.resolve(jsonResponse([suggestion]));
  await flush();

  expect(fetch).toHaveBeenCalledTimes(1);
  expect(results().hidden).toBe(true);
  expect(results().innerHTML).toBe('');
});

test('late response after selecting a suggestion does not reopen the dropdown', async () => {
  const first = deferred();
  const second = deferred();
  fetch.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  initSeedSuggestions();

  type('x');
  await vi.advanceTimersByTimeAsync(500);
  type('xb');
  await vi.advanceTimersByTimeAsync(500);
  second.resolve(jsonResponse([suggestion]));
  await flush();
  expect(results().hidden).toBe(false);

  results().querySelector('button[data-tag]').click();
  expect(input().value).toBe('xbox');
  expect(results().hidden).toBe(true);

  first.resolve(jsonResponse([suggestion]));
  await flush();

  expect(results().hidden).toBe(true);
  expect(results().innerHTML).toBe('');
});

test('late response after Escape does not reopen the dropdown', async () => {
  const gate = deferred();
  fetch.mockReturnValue(gate.promise);
  initSeedSuggestions();

  type('xb');
  await vi.advanceTimersByTimeAsync(500);
  input().dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  gate.resolve(jsonResponse([suggestion]));
  await flush();

  expect(results().hidden).toBe(true);
  expect(results().innerHTML).toBe('');
});

test('late response after clicking outside does not reopen the dropdown', async () => {
  const first = deferred();
  const second = deferred();
  fetch.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  initSeedSuggestions();

  type('x');
  await vi.advanceTimersByTimeAsync(500);
  type('xb');
  await vi.advanceTimersByTimeAsync(500);
  second.resolve(jsonResponse([suggestion]));
  await flush();
  expect(results().hidden).toBe(false);

  document.body.click();
  expect(results().hidden).toBe(true);

  first.resolve(jsonResponse([suggestion]));
  await flush();

  expect(results().hidden).toBe(true);
  expect(results().innerHTML).toBe('');
});
