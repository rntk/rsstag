/** Bind topic generation and resume polling for tasks already running.
 * @param {Document} root
 * @param {object} [options]
 * @returns {void}
 */
export function initTopicGrouping(root, options = {}) {
  const request = options.fetch || globalThis.fetch;
  const reload = options.reload || (() => window.location.reload());
  const schedule = options.schedule || ((callback) => window.setTimeout(callback, 2000));
  for (const panel of root.querySelectorAll('[data-topics-url]')) {
    const button = panel.querySelector('[data-split-topics]');
    const progress = panel.querySelector('progress');
    const message = panel.querySelector('[role="status"]');
    let busy = false;

    const update = async (method = 'GET') => {
      if (busy) return;
      busy = true;
      button.disabled = true;
      if (method === 'POST') {
        progress.hidden = false;
        message.textContent = 'Queuing topic processing…';
      }
      try {
        const response = await request(panel.dataset.topicsUrl, {
          method,
          credentials: 'same-origin',
        });
        if (!response.ok)
          throw new Error('Could not check or start topic processing. Please try again.');
        const result = await response.json();
        if (result.status === 'ready') {
          progress.value = 1;
          progress.max = 1;
          message.textContent = 'Topics are ready. Loading canvas…';
          reload();
          return;
        }
        const pending = result.status === 'queued' || result.status === 'processing';
        progress.hidden = !pending;
        button.hidden = pending;
        message.textContent = pending
          ? result.status === 'queued'
            ? 'Waiting for topic processing…'
            : 'Splitting this post into topics…'
          : result.message || 'This post does not have topics yet.';
        if (pending) schedule(() => update());
      } catch (error) {
        progress.hidden = true;
        button.hidden = false;
        message.textContent =
          error.message || 'Topic processing could not be loaded. Please try again.';
      } finally {
        busy = false;
        button.disabled = false;
      }
    };
    button.addEventListener('click', () => update('POST'));
    update();
  }
}
