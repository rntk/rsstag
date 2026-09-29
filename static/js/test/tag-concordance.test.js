import { describe, it, expect, vi } from 'vitest';
import { initConcordance } from '../tag-concordance.js';

function setup(request) {
  const root = document.createElement('div');
  root.innerHTML = `<button data-detail-key="one">Before</button><button data-detail-key="one">After</button>
    <article class="tag-concordance__row" data-post-id="p1" data-sentence-number="1">
    <button class="tag-concordance__read" data-post-id="p1" data-sentence-number="1" data-read="0">Mark Read</button></article>
    <dialog id="concordance-dialog"><button class="tag-concordance__close">Close</button>
    <a class="tag-concordance__article"></a><div class="tag-concordance__sentences"></div>
    <p class="tag-concordance__status"></p></dialog><script id="concordance-details" type="application/json"></script>`;
  const post = {
    title: 'Article',
    url: '/posts/p1',
    sentences: [
      { number: 1, text: 'Matching sentence.', read: false },
      { number: 2, text: '<img src=x> Full read context.', read: true },
      { number: null, text: 'Unaddressable sentence.' },
    ],
    groups: { '<img src=x>': [1, 2], 'Other topic': [1] },
  };
  root.querySelector('script').textContent = JSON.stringify({
    posts: { p1: post },
    entries: {
      one: { pid: 'p1', number: 1, topics: ['<img src=x>', 'Other topic'], sentence_index: 0 },
      fallback: { pid: 'p1', number: null, topics: [], sentence_index: 2 },
    },
  });
  initConcordance(root, request);
  return root;
}

describe('concordance sentences', () => {
  it('opens both sides with full topic sentences and safe text', () => {
    const root = setup(vi.fn());
    for (const button of root.querySelectorAll('[data-detail-key]')) {
      button.click();
      expect(root.querySelector('dialog').open).toBe(true);
      expect(root.querySelectorAll('li')).toHaveLength(3);
      expect(root.querySelectorAll('li button')).toHaveLength(3);
      expect(root.querySelector('img')).toBeNull();
      expect(root.querySelector('.is-read p').textContent).toContain('Full read context.');
      root.querySelector('.tag-concordance__close').click();
      expect(root.querySelector('dialog').open).toBe(false);
    }
  });

  it('opens ungrouped full sentences without read controls', () => {
    const root = setup(vi.fn());
    const button = root.querySelector('[data-detail-key]');
    button.dataset.detailKey = 'fallback';
    button.click();
    expect(root.querySelector('li p').textContent).toBe('Unaddressable sentence.');
    expect(root.querySelectorAll('li button')).toHaveLength(0);
  });

  it('keeps padding and content clicks open but closes on backdrop clicks', () => {
    const root = setup(vi.fn());
    root.querySelector('[data-detail-key]').click();
    const dialog = root.querySelector('dialog');
    vi.spyOn(dialog, 'getBoundingClientRect').mockReturnValue({
      left: 100,
      right: 700,
      top: 100,
      bottom: 600,
    });
    dialog.dispatchEvent(
      new globalThis.MouseEvent('click', { bubbles: true, clientX: 105, clientY: 105 })
    );
    expect(dialog.open).toBe(true);
    root.querySelector('li p').click();
    expect(dialog.open).toBe(true);
    dialog.dispatchEvent(
      new globalThis.MouseEvent('click', { bubbles: true, clientX: 99, clientY: 105 })
    );
    expect(dialog.open).toBe(false);
  });

  it('persists read and unread and synchronizes rows and reopened modal', async () => {
    const request = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: 'ok' }) });
    const root = setup(request);
    root.querySelector('[data-detail-key]').click();
    root.querySelector('li button').click();
    await vi.waitFor(() =>
      expect(root.querySelector('article').classList.contains('is-read')).toBe(true)
    );
    expect(JSON.parse(request.mock.calls[0][1].body)).toEqual({
      readed: true,
      selections: [{ post_id: 'p1', sentence_indices: [1] }],
    });
    root.querySelector('.tag-concordance__close').click();
    root.querySelector('[data-detail-key]').click();
    expect(root.querySelector('li button').textContent).toBe('Mark Unread');
    root.querySelector('article button').click();
    await vi.waitFor(() => expect(root.querySelector('li button').textContent).toBe('Mark Read'));
    expect(JSON.parse(request.mock.calls[1][1].body).readed).toBe(false);
  });

  it('retains state and restores controls after failure', async () => {
    const root = setup(vi.fn().mockRejectedValue(new Error('offline')));
    const button = root.querySelector('article button');
    button.click();
    await vi.waitFor(() =>
      expect(root.querySelector('.tag-concordance__status').textContent).toContain(
        'Please try again'
      )
    );
    expect(button.disabled).toBe(false);
    expect(button.dataset.read).toBe('0');
  });
});
