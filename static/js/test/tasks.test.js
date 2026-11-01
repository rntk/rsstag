import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { startTaskUpdates } from '../tasks.js';

describe('tasks queue updates', () => {
  let taskList;
  let status;
  let fetchQueue;

  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = `
      <div id="queue" data-refresh-url="/tasks/current">Queued</div>
      <p id="status"></p>
      <select id="task-type"><option>Download</option></select>
    `;
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    taskList = document.getElementById('queue');
    status = document.getElementById('status');
    fetchQueue = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => '<span>In progress</span>',
    });
    vi.stubGlobal('fetch', fetchQueue);
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
  });

  it('updates queued and running jobs and removes completed jobs', async () => {
    const selector = document.getElementById('task-type');
    selector.focus();
    startTaskUpdates(taskList, status);
    await vi.advanceTimersByTimeAsync(5000);

    expect(taskList.textContent).toBe('In progress');
    expect(document.activeElement).toBe(selector);
    expect(fetchQueue).toHaveBeenCalledWith('/tasks/current', {
      cache: 'no-store',
      credentials: 'same-origin',
      redirect: 'error',
    });

    fetchQueue.mockResolvedValue({
      ok: true,
      text: async () => '<p>No active tasks.</p>',
    });
    await vi.advanceTimersByTimeAsync(5000);
    expect(taskList.textContent).toBe('No active tasks.');
  });

  it('preserves existing content after failure and retries', async () => {
    fetchQueue.mockRejectedValueOnce(new Error('Network unavailable'));
    startTaskUpdates(taskList, status);
    await vi.advanceTimersByTimeAsync(5000);
    expect(taskList.textContent).toBe('Queued');
    expect(status.textContent).toContain('Could not refresh');

    await vi.advanceTimersByTimeAsync(5000);
    expect(taskList.textContent).toBe('In progress');
    expect(status.textContent).toContain('Updates every 5 seconds');
  });

  it('does not insert an error response into the queue', async () => {
    fetchQueue.mockResolvedValueOnce({ ok: false });
    startTaskUpdates(taskList, status);
    await vi.advanceTimersByTimeAsync(5000);
    expect(taskList.textContent).toBe('Queued');
    expect(status.textContent).toContain('Could not refresh');
  });

  it('pauses while the tab is hidden or a queue action has focus', async () => {
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    startTaskUpdates(taskList, status);
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchQueue).not.toHaveBeenCalled();

    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    taskList.innerHTML = '<button>Remove</button>';
    taskList.querySelector('button').focus();
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchQueue).not.toHaveBeenCalled();
    expect(status.textContent).toContain('Updates paused');

    document.activeElement.blur();
    await vi.advanceTimersByTimeAsync(5000);
    expect(taskList.textContent).toBe('In progress');
    expect(status.textContent).toContain('Updates every 5 seconds');
  });

  it('preserves a queue action focused while the request is in flight', async () => {
    let resolveResponse;
    fetchQueue.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveResponse = resolve;
      })
    );
    taskList.innerHTML = '<button>Remove</button>';
    startTaskUpdates(taskList, status);
    await vi.advanceTimersByTimeAsync(5000);
    const button = taskList.querySelector('button');
    button.focus();
    resolveResponse({ ok: true, text: async () => 'In progress' });
    await vi.advanceTimersByTimeAsync(0);
    expect(document.activeElement).toBe(button);
    expect(taskList.textContent).toBe('Remove');
    expect(status.textContent).toContain('Updates paused');
  });
});
