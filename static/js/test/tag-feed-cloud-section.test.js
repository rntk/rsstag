import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { setImmediate } from 'node:timers';
import { initTagFeedCloudSection } from '../libs/tag-feed-cloud-section.js';

const { JSDOM } = createRequire(import.meta.url)('jsdom');
const flush = () => new Promise((resolve) => setImmediate(resolve));
const fixture = () =>
  new JSDOM(
    '<button id="load_tag_feeds" data-url="/tag/c%2B%2B/feeds?view=section" aria-expanded="false">Load feeds / sources</button>' +
      '<span id="tag_feeds_error"></span><div id="tag_feeds_cloud"></div>'
  ).window.document;

test('loads on demand, folds, and reloads with current filters', async () => {
  const doc = fixture();
  let calls = 0;
  initTagFeedCloudSection(doc, async (url, options) => {
    calls += 1;
    assert.equal(url, '/tag/c%2B%2B/feeds?view=section');
    assert.equal(options.credentials, 'include');
    return { ok: true, text: async () => '<nav><a href="/tag/c++?feed=one">Source</a></nav>' };
  });
  const button = doc.getElementById('load_tag_feeds');
  const block = doc.getElementById('tag_feeds_cloud');
  assert.equal(calls, 0);
  button.click();
  assert.equal(button.disabled, true);
  await flush();
  assert.equal(button.getAttribute('aria-expanded'), 'true');
  assert.equal(block.querySelector('a').textContent, 'Source');
  assert.equal(button.textContent, 'Hide feeds / sources');
  button.click();
  assert.equal(block.innerHTML, '');
  assert.equal(button.getAttribute('aria-expanded'), 'false');
  assert.equal(calls, 1);
  button.click();
  await flush();
  assert.equal(calls, 2);
});

test('failure leaves a retryable load button', async () => {
  const doc = fixture();
  let fail = true;
  initTagFeedCloudSection(doc, async () => {
    if (fail) {
      throw new Error('Network failed');
    }
    return { ok: true, text: async () => '<p>No matching sources</p>' };
  });
  const button = doc.getElementById('load_tag_feeds');
  button.click();
  await flush();
  assert.equal(button.disabled, false);
  assert.equal(button.getAttribute('aria-expanded'), 'false');
  assert.match(doc.getElementById('tag_feeds_error').textContent, /Try again/);
  fail = false;
  button.click();
  await flush();
  assert.equal(doc.getElementById('tag_feeds_error').textContent, '');
  assert.equal(button.getAttribute('aria-expanded'), 'true');
});

test('error responses and login redirects do not enter the section', async () => {
  for (const response of [{ ok: false }, { ok: true, redirected: true }]) {
    const doc = fixture();
    initTagFeedCloudSection(doc, async () => response);
    doc.getElementById('load_tag_feeds').click();
    await flush();
    assert.equal(doc.getElementById('tag_feeds_cloud').innerHTML, '');
    assert.match(doc.getElementById('tag_feeds_error').textContent, /Unable to load/);
  }
});
