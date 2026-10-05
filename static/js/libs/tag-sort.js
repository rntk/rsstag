'use strict';

/**
 * @typedef {Object} TagLike
 * @property {string} [tag]
 * @property {number} [count]
 */

/**
 * @param {TagLike} a
 * @param {TagLike} b
 * @returns {number}
 */
export function compareByName(a, b) {
  const at = (a.tag || '').toString();
  const bt = (b.tag || '').toString();
  return at.localeCompare(bt, undefined, { numeric: true, sensitivity: 'base' });
}

/**
 * Count descending, tag name as tie-break.
 * @param {TagLike} a
 * @param {TagLike} b
 * @returns {number}
 */
export function compareByCount(a, b) {
  const countDiff = (b.count || 0) - (a.count || 0);
  return countDiff !== 0 ? countDiff : compareByName(a, b);
}

/**
 * @param {Object} tag
 * @param {string} scoreKey
 * @returns {number | null} finite numeric value of tag[scoreKey], otherwise null
 */
export function finiteScore(tag, scoreKey) {
  const value = tag ? tag[scoreKey] : null;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/**
 * Builds a comparator: score descending (tags without a finite score go last),
 * tag name as tie-break.
 * @param {string} scoreKey
 * @returns {(a: Object, b: Object) => number}
 */
export function compareByScore(scoreKey) {
  return (a, b) => {
    const as = finiteScore(a, scoreKey);
    const bs = finiteScore(b, scoreKey);
    if (as === null || bs === null) {
      if (as === bs) {
        return compareByName(a, b);
      }
      return as === null ? 1 : -1;
    }
    return bs - as !== 0 ? bs - as : compareByName(a, b);
  };
}

/**
 * Ranked (non-alphabetical) ordering: by score when scoreKey is set, otherwise by count.
 * @param {string} [scoreKey]
 * @param {boolean} [preserveOrder] Keep the server's selected ranking.
 * @returns {(a: Object, b: Object) => number}
 */
export function rankedComparator(scoreKey, preserveOrder = false) {
  if (preserveOrder) {
    return () => 0;
  }
  return scoreKey ? compareByScore(scoreKey) : compareByCount;
}

/**
 * Formats a score to at most 4 decimals ("0.4213", "2", "0.5").
 * @param {number} value
 * @returns {string}
 */
export function formatScore(value) {
  return String(Number(value.toFixed(4)));
}
