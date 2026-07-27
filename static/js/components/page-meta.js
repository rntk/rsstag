/* global document */

/**
 * Header meta strip shared by the canvas (/canvas) and hierarchy (/hierarchy)
 * pages.
 *
 * The scope kicker and title are rendered server-side by the `site_header`
 * macro, so the page is labelled before any script runs. Only the counts are
 * filled in here, because read state changes without a reload.
 *
 * The strip lives inside `.site-header__inner`, whose height is fixed in
 * style.scss: writing counts into it must never change the height that
 * syncGlobalToolsOffset measures into `--global-tools-height`.
 */

/** @typedef {{label: string, value: number|string, accent?: boolean}} MetaStat */

/** Selector of the element the counts are written into. */
const STATS_SELECTOR = '[data-page-meta-stats]';

/**
 * Post totals of a canvas payload.
 *
 * @param {Array<Record<string, unknown>>} posts
 * @returns {{total: number, read: number, unread: number}}
 */
export function countPostsMeta(posts) {
  const list = Array.isArray(posts) ? posts : [];
  const read = list.filter((post) => Boolean(post?.read)).length;
  return { total: list.length, read, unread: list.length - read };
}

/**
 * Sources of a topic, falling back to the older payload that carried plain
 * sentence strings instead of per-post sources.
 *
 * @param {Record<string, unknown>} topic
 * @returns {Array<Record<string, unknown>>}
 */
function topicSources(topic) {
  const sources = Array.isArray(topic?.sources) ? topic.sources : [];
  if (sources.length > 0) return sources;
  const sentences = Array.isArray(topic?.sentences) ? topic.sentences : [];
  return sentences.length > 0 ? [{ post_id: '', sentences }] : [];
}

/**
 * Every distinct path prefix of a topic name: "A > B" contributes both "A" and
 * "A > B", so the count matches the branches and leaves actually drawn.
 *
 * @param {string} name
 * @returns {string[]}
 */
function topicPaths(name) {
  const parts = String(name || '')
    .split('>')
    .map((part) => part.trim())
    .filter(Boolean);
  return parts.map((_, index) => parts.slice(0, index + 1).join(' > '));
}

/**
 * Read state of one sentence, plus a key identifying it within its post.
 *
 * Plain strings carry no read state, so they count as unread -- the same
 * assumption `unreadSourceSentences` makes when it keeps them.
 *
 * @param {Record<string, unknown>|string} sentence
 * @param {string} postId
 * @returns {{key: string, read: boolean}|null}
 */
function sentenceEntry(sentence, postId) {
  const isText = typeof sentence === 'string';
  const text = isText ? sentence : String(sentence?.text || '');
  if (!text.trim()) return null;
  const number = !isText && Number.isInteger(sentence?.number) ? sentence.number : null;
  return {
    key: `${postId}\u0000${number === null ? text.trim() : number}`,
    read: !isText && Boolean(sentence?.read),
  };
}

/**
 * Topic, post and sentence totals of a hierarchy payload.
 *
 * One sentence usually belongs to several topics -- which is why
 * `FeedHierarchy#applyReadState` updates every match -- so summing the
 * per-topic `posts_count` / `sentences_count` would over-count. Posts and
 * sentences are therefore deduplicated by id before being counted.
 *
 * @param {Array<Record<string, unknown>>} topics
 * @returns {{topics: number, posts: number, sentences: number, read: number, unread: number}}
 */
export function countTopicsMeta(topics) {
  /** @type {Set<string>} */
  const paths = new Set();
  /** @type {Set<string>} */
  const posts = new Set();
  /** @type {Map<string, boolean>} */
  const sentences = new Map();

  (Array.isArray(topics) ? topics : []).forEach((topic) => {
    topicPaths(topic?.name).forEach((path) => paths.add(path));
    topicSources(topic).forEach((source) => {
      const postId = String(source?.post_id || source?.url || source?.title || '');
      if (postId) posts.add(postId);
      (Array.isArray(source?.sentences) ? source.sentences : []).forEach((sentence) => {
        const entry = sentenceEntry(sentence, postId);
        if (!entry) return;
        sentences.set(entry.key, sentences.get(entry.key) || entry.read);
      });
    });
  });

  const read = [...sentences.values()].filter(Boolean).length;
  return {
    topics: paths.size,
    posts: posts.size,
    sentences: sentences.size,
    read,
    unread: sentences.size - read,
  };
}

/**
 * Plain-text form of the stats, used as the strip's tooltip so the full
 * wording survives the ellipsis that truncates a narrow header.
 *
 * @param {MetaStat[]} stats
 * @returns {string}
 */
export function formatMetaTitle(stats) {
  return (Array.isArray(stats) ? stats : [])
    .map((stat) => `${stat.value} ${stat.label}`)
    .join(', ');
}

/**
 * Writes counts into the header strip. Every method is a no-op when the page
 * has no strip, so pages without the shared header need no guard of their own.
 */
class PageMeta {
  /** @param {ParentNode} [root] */
  constructor(root = document) {
    /** @type {Element|null} */
    this.statsElement = root?.querySelector?.(STATS_SELECTOR) || null;
  }

  /** @param {MetaStat} stat @returns {HTMLElement} */
  buildStat(stat) {
    const element = document.createElement('span');
    element.className = `site-header__page-stat${
      stat.accent ? ' site-header__page-stat--accent' : ''
    }`;
    const value = document.createElement('b');
    value.textContent = String(stat.value);
    element.append(value, document.createTextNode(` ${stat.label}`));
    return element;
  }

  /** @param {MetaStat[]} stats @returns {void} */
  render(stats) {
    if (!this.statsElement) return;
    const list = Array.isArray(stats) ? stats : [];
    this.statsElement.replaceChildren(...list.map((stat) => this.buildStat(stat)));
    this.statsElement.setAttribute('title', formatMetaTitle(list));
  }
}

export { PageMeta };
