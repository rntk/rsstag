const REFRESH_MESSAGE = 'Updates every 5 seconds. Completed tasks leave the queue.';
const PAUSED_MESSAGE =
  'Updates paused while a queue action is focused. Click elsewhere on the page to resume.';

export function startTaskUpdates(taskList, status, delay = 5000) {
  async function refresh() {
    try {
      if (document.hidden) return;
      if (taskList.contains(document.activeElement)) {
        status.textContent = PAUSED_MESSAGE;
        return;
      }

      const response = await fetch(taskList.dataset.refreshUrl, {
        cache: 'no-store',
        credentials: 'same-origin',
        redirect: 'error',
      });
      if (!response.ok) throw new Error('Queue refresh failed');

      const html = await response.text();
      // Keep a focused queue action stable if focus changed during the request.
      if (taskList.contains(document.activeElement)) {
        status.textContent = PAUSED_MESSAGE;
        return;
      }
      if (taskList.innerHTML !== html) taskList.innerHTML = html;
      status.textContent = REFRESH_MESSAGE;
    } catch {
      status.textContent =
        'Could not refresh the queue. Retrying automatically; you can also reload the page.';
    } finally {
      setTimeout(refresh, delay);
    }
  }

  setTimeout(refresh, delay);
}

const taskList = document.getElementById('current-tasks');
const status = document.getElementById('tasks-refresh-status');
if (taskList && status) startTaskUpdates(taskList, status);
