import { afterEach, beforeEach, expect, test, vi } from 'vitest';

import { initAnthologyDetail } from '../anthology-detail.js';
import { fetchJson, postJson } from '../libs/anthology-common.js';

vi.mock('../libs/anthology-common.js', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchJson: vi.fn(),
  postJson: vi.fn(),
}));

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

const cluster = { id: 'c1', label: 'Cluster', snippet_ids: ['s1'], feed_ids: [] };
const payload = {
  id: 'a1',
  status: 'done',
  result: {
    themes: [],
    clusters: { c1: cluster },
    unsorted: [],
  },
};

function clusterData(text, read) {
  return {
    cluster,
    snippets: [
      {
        id: 's1',
        post_id: 'p1',
        title: 'Post',
        read,
        sentences: [{ number: 0, text, read }],
      },
    ],
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.spyOn(window, 'addEventListener').mockImplementation(() => {});
  vi.spyOn(document, 'addEventListener').mockImplementation(() => {});
  window.history.replaceState(null, '', '#c1');
  document.body.innerHTML = `
    <div id="anthology-app">
      <div id="anth-head"></div><div id="anth-tree"></div>
      <div id="anth-main"></div>
      <dialog id="anth-feeds-dialog"></dialog>
      <div id="anth-note"></div>
      <button id="update" data-action="mark" data-kind="cluster"
        data-id="c1" data-readed="true">Mark read</button>
    </div>
    <script id="anthology-detail-data" type="application/json">${JSON.stringify(payload)}</script>`;
});

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = '';
});

test.each(['before', 'after', 'error'])(
  'ignores an invalidated cluster response completing %s the refreshed response',
  async (order) => {
    const oldRequest = deferred();
    const newRequest = deferred();
    fetchJson.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    postJson.mockResolvedValue(payload);
    initAnthologyDetail();
    expect(fetchJson).toHaveBeenCalledTimes(1);

    document.getElementById('update').click();
    await vi.waitFor(() => expect(fetchJson).toHaveBeenCalledTimes(2));

    if (order === 'before') {
      oldRequest.resolve(clusterData('Outdated snippet', false));
      await oldRequest.promise;
      expect(document.getElementById('anth-main').textContent).toContain('Loading snippets');
      expect(fetchJson).toHaveBeenCalledTimes(2);
    }

    newRequest.resolve(clusterData('Refreshed snippet', true));
    await vi.waitFor(() =>
      expect(document.getElementById('anth-main').textContent).toContain('Refreshed snippet')
    );

    if (order === 'after') oldRequest.resolve(clusterData('Outdated snippet', false));
    if (order === 'error') oldRequest.reject(new Error('Outdated failure'));
    await oldRequest.promise.catch(() => {});

    const main = document.getElementById('anth-main');
    expect(main.textContent).toContain('Refreshed snippet');
    expect(main.textContent).not.toContain('Outdated');
    expect(main.querySelector('.anth-sentence').classList.contains('anth-sentence--read')).toBe(
      true
    );
    expect(main.querySelector('[data-action="mark"][data-kind="cluster"]').dataset.readed).toBe(
      'false'
    );
  }
);

test('reuses a pending cluster request when the view changes', () => {
  fetchJson.mockReturnValue(deferred().promise);
  initAnthologyDetail();
  const control = document.createElement('input');
  control.dataset.control = 'skim';
  document.getElementById('anthology-app').append(control);
  control.dispatchEvent(new window.Event('change', { bubbles: true }));
  expect(fetchJson).toHaveBeenCalledTimes(1);
});

test('opens and closes the feeds dialog for a cluster', () => {
  fetchJson.mockReturnValue(deferred().promise);
  const withFeeds = { ...cluster, feed_ids: ['f1', 'f2'] };
  const data = document.getElementById('anthology-detail-data');
  data.textContent = JSON.stringify({
    ...payload,
    feed_titles: { f1: 'First feed' },
    result: { ...payload.result, clusters: { c1: withFeeds } },
  });
  initAnthologyDetail();
  const link = document.createElement('button');
  Object.assign(link.dataset, { action: 'feeds', id: 'c1' });
  document.getElementById('anthology-app').append(link);
  link.click();

  const dialog = document.getElementById('anth-feeds-dialog');
  expect(dialog.open).toBe(true);
  expect([...dialog.querySelectorAll('li')].map((li) => li.textContent)).toEqual([
    'First feed',
    'f2',
  ]);
  dialog.querySelector('[data-action="close-feeds"]').click();
  expect(dialog.open).toBe(false);
});
