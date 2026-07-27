/* global console, document, fetch */

/**
 * Topic tags dialog shared by the canvas (/canvas) and hierarchy (/hierarchy)
 * pages.
 *
 * Both pages expose a per-topic context menu; its "Tags" item opens this
 * dialog with the tags mentioned by the sentences of that topic. Every tag
 * links to its /tag-info page.
 *
 * The dialog has no read/unread filter of its own: the request carries the
 * topic path and its posts, and /api/topic-tags reads the sentences and their
 * read state from the grouping documents, narrowed by the user's only-unread
 * setting just like the pages themselves are.
 */

/**
 * @typedef {{tag: string, url?: string, count?: number, posts_count?: number}} TopicTag
 * @typedef {{topic?: string, tags?: TopicTag[], sentences_count?: number}} TopicTagsPayload
 */

/** Endpoint serving the tags of one topic. */
export const TOPIC_TAGS_ENDPOINT = '/api/topic-tags';

/**
 * Normalize a topic path so "A > B" and "A>B" are sent identically.
 *
 * @param {string} topic
 * @returns {string}
 */
export function normalizeTopicPath(topic) {
  return String(topic || '')
    .split('>')
    .map((part) => part.trim())
    .filter(Boolean)
    .join(' > ');
}

/**
 * Keep the tags whose name contains the search term (case-insensitive). An
 * empty term keeps everything.
 *
 * @param {TopicTag[]} tags
 * @param {string} term
 * @returns {TopicTag[]}
 */
export function filterTagsByTerm(tags, term) {
  const list = Array.isArray(tags) ? tags : [];
  const needle = String(term || '')
    .trim()
    .toLowerCase();
  if (!needle) return list;
  return list.filter((tag) =>
    String(tag?.tag || '')
      .toLowerCase()
      .includes(needle)
  );
}

/**
 * Badge text of one tag row, e.g. "12 sentences · 3 posts".
 *
 * @param {TopicTag} tag
 * @returns {string}
 */
export function formatTagMeta(tag) {
  const count = Number.isFinite(tag?.count) ? tag.count : 0;
  const posts = Number.isFinite(tag?.posts_count) ? tag.posts_count : 0;
  const parts = [`${count} ${count === 1 ? 'sentence' : 'sentences'}`];
  if (posts > 0) parts.push(`${posts} ${posts === 1 ? 'post' : 'posts'}`);
  return parts.join(' · ');
}

class TopicTagsDialog {
  /** @param {{endpoint?: string}} [options] */
  constructor({ endpoint = TOPIC_TAGS_ENDPOINT } = {}) {
    this.endpoint = endpoint;
    this.searchTerm = '';
    /** @type {string} */
    this.topic = '';
    /** @type {string[]} */
    this.postIds = [];
    /** @type {TopicTag[]} */
    this.tags = [];
    /** Sequence number of the newest request, so stale replies are dropped. */
    this.requestId = 0;
    /** @type {HTMLDialogElement|null} */
    this.dialog = null;
  }

  /** @returns {HTMLDialogElement} */
  ensureDialog() {
    if (this.dialog) return this.dialog;
    const dialog = document.createElement('dialog');
    dialog.className = 'canvas-tags-dialog';
    dialog.innerHTML = `<button type="button" class="canvas-summary-dialog__close" aria-label="Close">×</button><p class="canvas-summary-dialog__kicker">Tags</p><h2></h2><div class="canvas-tags-dialog__toolbar"><input type="search" class="canvas-tags-dialog__search" placeholder="Filter tags" aria-label="Filter tags"></div><p class="canvas-tags-dialog__status" role="status" aria-live="polite"></p><ul class="canvas-tags-dialog__list"></ul>`;
    dialog
      .querySelector('.canvas-summary-dialog__close')
      ?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });

    const search = dialog.querySelector('.canvas-tags-dialog__search');
    search?.addEventListener('input', () => {
      this.searchTerm = search.value;
      this.renderTags();
    });

    document.body.appendChild(dialog);
    this.dialog = dialog;
    return dialog;
  }

  /**
   * Open the dialog for one topic. `postIds` is a snapshot taken by the caller:
   * canvas cards recycle, so no layout object may be held across the request.
   *
   * @param {{topic: string, postIds: string[]}} scope
   * @returns {Promise<void>}
   */
  async open({ topic, postIds }) {
    const dialog = this.ensureDialog();
    this.topic = normalizeTopicPath(topic);
    this.postIds = [...new Set((Array.isArray(postIds) ? postIds : []).map(String))].filter(
      Boolean
    );
    this.searchTerm = '';
    const search = dialog.querySelector('.canvas-tags-dialog__search');
    if (search) search.value = '';
    const title = dialog.querySelector('h2');
    if (title) title.textContent = this.topic;
    if (!dialog.open) dialog.showModal();
    await this.load();
  }

  /** @param {string} message @param {boolean} [isError] */
  showStatus(message, isError = false) {
    const status = this.dialog?.querySelector('.canvas-tags-dialog__status');
    if (!status) return;
    status.textContent = message;
    status.classList.toggle('is-error', isError);
  }

  /** @returns {Promise<void>} */
  async load() {
    if (!this.dialog) return;
    const requestId = (this.requestId += 1);
    this.tags = [];
    this.renderTags();
    if (this.postIds.length === 0) {
      this.showStatus('No posts are available for this topic.');
      return;
    }
    this.showStatus('Loading tags…');
    try {
      const response = await fetch(this.endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: this.topic, post_ids: this.postIds }),
      });
      const payload = await response.json();
      if (requestId !== this.requestId) return;
      if (!response.ok || !payload?.data) {
        throw new Error(payload?.error || 'Unable to load tags for this topic.');
      }
      this.applyPayload(payload.data);
    } catch (error) {
      if (requestId !== this.requestId) return;
      console.error('Unable to load topic tags.', error);
      this.showStatus(
        error instanceof Error ? error.message : 'Unable to load tags for this topic.',
        true
      );
    }
  }

  /** @param {TopicTagsPayload} data */
  applyPayload(data) {
    this.tags = Array.isArray(data?.tags) ? data.tags : [];
    const sentences = Number.isFinite(data?.sentences_count) ? data.sentences_count : 0;
    if (this.tags.length === 0) {
      this.showStatus(
        sentences === 0
          ? 'This topic has no sentences to show.'
          : 'No tags were found for this topic.'
      );
    } else {
      const label = this.tags.length === 1 ? 'tag' : 'tags';
      this.showStatus(
        `${this.tags.length} ${label} in ${sentences} ${sentences === 1 ? 'sentence' : 'sentences'}.`
      );
    }
    this.renderTags();
  }

  renderTags() {
    const list = this.dialog?.querySelector('.canvas-tags-dialog__list');
    if (!list) return;
    list.replaceChildren();
    filterTagsByTerm(this.tags, this.searchTerm).forEach((tag) => {
      list.appendChild(this.buildTagItem(tag));
    });
  }

  /** @param {TopicTag} tag @returns {HTMLElement} */
  buildTagItem(tag) {
    const item = document.createElement('li');
    item.className = 'canvas-tags-dialog__item';

    const link = document.createElement('a');
    link.className = 'canvas-tags-dialog__link';
    link.href = tag.url || `/tag-info/${encodeURIComponent(tag.tag)}`;
    link.textContent = tag.tag;
    link.title = `Open the tag page for ${tag.tag}`;
    item.appendChild(link);

    const meta = document.createElement('span');
    meta.className = 'canvas-tags-dialog__meta';
    meta.textContent = formatTagMeta(tag);
    item.appendChild(meta);
    return item;
  }
}

export { TopicTagsDialog };
