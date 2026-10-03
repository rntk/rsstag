import test from 'node:test';
import { setImmediate } from 'node:timers';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { initTopicGrouping } from '../libs/post-canvas-grouping.js';

const { JSDOM } = createRequire(import.meta.url)('jsdom');
const flush = () => new Promise((resolve) => setImmediate(resolve));
const fixture = () =>
  new JSDOM(
    '<section data-topics-url="/post-canvas/p1/topics"><p role="status"></p><button data-split-topics>Split</button><progress hidden></progress></section>'
  ).window.document;
const response = (status) => ({ ok: true, json: async () => ({ status }) });

test('click queues grouping, polls and reloads when topics are ready', async () => {
  const doc = fixture();
  const methods = [];
  const scheduled = [];
  let reloaded = false;
  const statuses = ['missing', 'queued', 'processing', 'ready'];
  initTopicGrouping(doc, {
    fetch: async (url, options) => {
      assert.equal(url, '/post-canvas/p1/topics');
      methods.push(options.method);
      return response(statuses.shift());
    },
    schedule: (callback) => scheduled.push(callback),
    reload: () => {
      reloaded = true;
    },
  });
  await flush();
  const button = doc.querySelector('button');
  button.click();
  button.click();
  await flush();
  assert.deepEqual(methods, ['GET', 'POST']);
  assert.equal(button.hidden, true);
  assert.equal(doc.querySelector('progress').hidden, false);
  await scheduled.shift()();
  assert.match(doc.querySelector('p').textContent, /Splitting/);
  await scheduled.shift()();
  assert.equal(reloaded, true);
});

test('existing queued task resumes polling on page load', async () => {
  const doc = fixture();
  const scheduled = [];
  initTopicGrouping(doc, {
    fetch: async () => response('queued'),
    schedule: (callback) => scheduled.push(callback),
  });
  await flush();
  assert.equal(doc.querySelector('button').hidden, true);
  assert.equal(scheduled.length, 1);
});

test('polling failure restores retry button with an error', async () => {
  const doc = fixture();
  initTopicGrouping(doc, { fetch: async () => ({ ok: false }) });
  await flush();
  assert.equal(doc.querySelector('button').hidden, false);
  assert.equal(doc.querySelector('button').disabled, false);
  assert.equal(doc.querySelector('progress').hidden, true);
  assert.match(doc.querySelector('p').textContent, /Please try again/);
});
