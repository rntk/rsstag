'use strict';

/** @typedef {{label: string, count: number, children: Map<string, TreeNode>}} TreeNode */
/** @typedef {{label: string, count: number, children: Branch[]}} Branch */
/** @typedef {{root: Branch, occurrences: number, totalPaths: number, shownPaths: number}} TreeResult */
const CONTEXT_WORDS = 18;
const MAX_PATHS = 120;

/** @param {string} text @returns {string[]} */
export function tokenize(text) {
  return (
    (typeof text === 'string' ? text : '').match(
      /[\p{L}\p{N}_]+(?:['’-][\p{L}\p{N}_]+)*|[^\s\p{L}\p{N}_]/gu
    ) || []
  );
}

/** @param {string} label @returns {TreeNode} */
function node(label) {
  return { label, count: 0, children: new Map() };
}

/** @param {TreeNode} source @param {boolean} backwards @returns {Branch} */
function compress(source, backwards) {
  let label = source.label;
  let current = source;
  while (current.children.size === 1) {
    const child = current.children.values().next().value;
    // A phrase ending here must remain a separate branch.
    if (child.count !== current.count) break;
    label = backwards ? `${child.label} ${label}` : `${label} ${child.label}`;
    current = child;
  }
  return {
    label,
    count: source.count,
    children: Array.from(current.children.values())
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
      .map((child) => compress(child, backwards)),
  };
}

/**
 * Count every occurrence and merge shared context paths, including repeated tags.
 * @param {string[]} texts
 * @param {string} tag
 * @param {boolean} backwards
 * @returns {TreeResult}
 */
export function buildWordTree(texts, tag, backwards = false) {
  const words = tokenize(tag).map((word) => word.toLocaleLowerCase());
  const paths = new Map();
  let occurrences = 0;
  for (const text of texts) {
    const tokens = tokenize(text);
    for (let i = 0; words.length && i <= tokens.length - words.length; i++) {
      if (!words.every((word, offset) => tokens[i + offset].toLocaleLowerCase() === word)) continue;
      occurrences++;
      const context = backwards
        ? tokens.slice(Math.max(0, i - CONTEXT_WORDS), i).reverse()
        : tokens.slice(i + words.length, i + words.length + CONTEXT_WORDS);
      const key = JSON.stringify(context);
      const path = paths.get(key);
      if (path) path.count++;
      else paths.set(key, { tokens: context, count: 1 });
    }
  }
  const selected = Array.from(paths.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, MAX_PATHS);
  const root = node(tag.trim());
  root.count = occurrences;
  for (const path of selected) {
    let current = root;
    for (const word of path.tokens) {
      if (!current.children.has(word)) current.children.set(word, node(word));
      current = current.children.get(word);
      current.count += path.count;
    }
  }
  return {
    root: {
      label: root.label,
      count: occurrences,
      children: Array.from(root.children.values())
        .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
        .map((child) => compress(child, backwards)),
    },
    occurrences,
    totalPaths: paths.size,
    shownPaths: selected.length,
  };
}

/**
 * Prefer the full phrase; fall back to matching individual words for tag groups.
 * @param {string[]} texts
 * @param {string} tag
 * @param {boolean} backwards
 * @returns {TreeResult[]}
 */
export function buildWordTrees(texts, tag, backwards = false) {
  const phrase = buildWordTree(texts, tag, backwards);
  const words = Array.from(
    new Map(
      tag
        .trim()
        .split(/\s+/)
        .map((word) => [word.toLocaleLowerCase(), word])
    ).values()
  );
  if (phrase.occurrences || words.length < 2) return [phrase];
  const trees = words
    .map((word) => buildWordTree(texts, word, backwards))
    .filter((tree) => tree.occurrences);
  return trees.length ? trees : [phrase];
}
