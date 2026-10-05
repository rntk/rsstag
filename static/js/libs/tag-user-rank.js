'use strict';

export const USER_RANK_HIDDEN = 'hidden';
export const USER_RANK_PINNED = 'pinned';
export const USER_RANK_URL = '/api/tags/user-rank';

/**
 * Value to store when `action` ("hide" | "pin") is toggled on a tag whose
 * current override is `current`; null clears the override.
 * @param {string | null | undefined} current
 * @param {string} action
 * @returns {string | null}
 */
export function toggledUserRank(current, action) {
  const target = action === 'hide' ? USER_RANK_HIDDEN : USER_RANK_PINNED;
  return current === target ? null : target;
}

/**
 * Item CSS modifier for the current override.
 * @param {string | null | undefined} userRank
 * @returns {string}
 */
export function userRankClass(userRank) {
  if (userRank === USER_RANK_HIDDEN) {
    return ' cloud_item_hidden';
  }
  return userRank === USER_RANK_PINNED ? ' cloud_item_pinned' : '';
}

/**
 * Whether the tag payload supports manual hide / pin (the server sends the
 * `user_rank` key, null when unset, only on the tag list pages).
 * @param {Object} tag
 * @param {boolean} [isBigram]
 * @returns {boolean}
 */
export function supportsUserRank(tag, isBigram) {
  return !isBigram && !!tag && Object.prototype.hasOwnProperty.call(tag, 'user_rank');
}

/**
 * Persists the override; resolves on success, rejects with an Error otherwise.
 * @param {string} tag
 * @param {string | null} value
 * @param {Function} [fetchFn]
 * @returns {Promise<void>}
 */
export async function saveUserRank(tag, value, fetchFn = (...args) => globalThis.fetch(...args)) {
  const response = await fetchFn(USER_RANK_URL, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag, value }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
}
