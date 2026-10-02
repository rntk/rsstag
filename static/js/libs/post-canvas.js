/**
 * Pure helpers for the post canvas: topic hierarchy, chronological topic runs,
 * rail column layout, navigation and zoom math.
 *
 * Mirrors the extension canvas (extension-canvas/src/domain/topicCards.js):
 * every topic path is rolled up to the selected level, its sentences are split
 * into contiguous runs, and each run becomes one rail card that sits beside the
 * sentences it covers. Runs also break at post boundaries.
 */

export const CARD_WIDTH = 240;
export const SUMMARY_CARD_WIDTH = 418;
export const SUMMARY_CARD_MAX_WIDTH = 4180;
export const COLUMN_GAP = 18;
export const RAIL_PADDING = 24;
export const MIN_SCALE = 0.1;
export const MAX_SCALE = 3;

const CARD_HEIGHT = 72;
const CARD_VERTICAL_GAP = 8;
const CARD_MIN_HEIGHT = 56;
// A card may move this far below its sentences to clear the previous card.
const CARD_MAX_PUSH = 18;
const CARD_BASE_TITLE_FONT_SIZE = 14;
const CARD_TITLE_LINE_HEIGHT = 1.2;
const CARD_CHROME_HEIGHT = 34;
const CARD_COMPACT_HEIGHT = 64;

/**
 * @typedef {{number: number, post_id: string, text?: string, post_sentence_number?: number}} CanvasSentence
 * @typedef {{
 *   key: string, path: string, name: string, depth: number, postId: string,
 *   sentences: number[], start: number, end: number,
 *   top?: number, height?: number
 * }} TopicCard
 */

/** @param {string} name @returns {string[]} */
export function splitTopicPath(name) {
  return String(name || '')
    .split('>')
    .map((part) => part.trim())
    .filter(Boolean);
}

/** @param {string[]} parts @returns {string} */
export function formatTopicPath(parts) {
  return parts.join(' > ');
}

/** @param {Object<string, number[]>} groups @returns {number} */
export function getMaxTopicLevel(groups) {
  let max = 0;
  for (const name of Object.keys(groups || {})) {
    max = Math.max(max, splitTopicPath(name).length - 1);
  }
  return max;
}

/** @param {number} value @returns {number} */
export function clampScale(value) {
  const safe = Number.isFinite(value) ? value : 1;
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, safe));
}

/**
 * Split sentence numbers into contiguous runs, also breaking at post
 * boundaries. Unknown sentence numbers are skipped.
 *
 * @param {Iterable<number>} numbers
 * @param {Map<number, CanvasSentence>} sentencesByNumber
 * @returns {number[][]}
 */
export function splitSentenceRuns(numbers, sentencesByNumber) {
  const sorted = [...new Set(numbers)]
    .filter((number) => sentencesByNumber.has(number))
    .sort((a, b) => a - b);
  const runs = [];
  for (const number of sorted) {
    const run = runs.at(-1);
    const previous = run?.at(-1);
    const samePost =
      previous !== undefined &&
      sentencesByNumber.get(previous).post_id === sentencesByNumber.get(number).post_id;
    if (previous === number - 1 && samePost) run.push(number);
    else runs.push([number]);
  }
  return runs;
}

/**
 * Roll topic sentences up to every ancestor path, truncated at `level`.
 *
 * @param {Object<string, number[]>} groups
 * @param {number} level
 * @returns {Map<string, {path: string, name: string, depth: number, sentences: Set<number>}>}
 */
export function buildTopicNodes(groups, level) {
  const nodes = new Map();
  for (const [name, numbers] of Object.entries(groups || {})) {
    const parts = splitTopicPath(name);
    const limit = Math.min(parts.length, level + 1);
    for (let depth = 0; depth < limit; depth += 1) {
      const path = formatTopicPath(parts.slice(0, depth + 1));
      if (!nodes.has(path)) {
        nodes.set(path, { path, name: parts[depth], depth, sentences: new Set() });
      }
      const node = nodes.get(path);
      for (const number of numbers || []) node.sentences.add(number);
    }
  }
  return nodes;
}

/**
 * Build one card per contiguous sentence run for every level up to `level`.
 *
 * @param {{groups: Object<string, number[]>, sentences: CanvasSentence[]}} data
 * @param {number} level
 * @returns {TopicCard[]}
 */
export function buildTopicCards(data, level) {
  const sentencesByNumber = new Map((data.sentences || []).map((s) => [s.number, s]));
  const cards = [];
  for (const node of buildTopicNodes(data.groups, level).values()) {
    splitSentenceRuns(node.sentences, sentencesByNumber).forEach((run, index) => {
      cards.push({
        key: `${node.path}#${node.depth}#${index}`,
        path: node.path,
        name: node.name,
        depth: node.depth,
        postId: sentencesByNumber.get(run[0]).post_id,
        sentences: run,
        start: run[0],
        end: run.at(-1),
      });
    });
  }
  return cards.sort(compareCards);
}

/** @param {TopicCard} a @param {TopicCard} b @returns {number} */
function compareCards(a, b) {
  return a.depth - b.depth || a.start - b.start || a.path.localeCompare(b.path);
}

/**
 * Cards readers step through: the deepest card of each branch, in source order.
 *
 * @param {TopicCard[]} cards
 * @returns {TopicCard[]}
 */
export function buildNavigationList(cards) {
  const parents = new Set();
  for (const card of cards) {
    const parts = splitTopicPath(card.path);
    for (let depth = 1; depth < parts.length; depth += 1) {
      parents.add(formatTopicPath(parts.slice(0, depth)));
    }
  }
  return cards
    .filter((card) => !parents.has(card.path))
    .sort((a, b) => a.start - b.start || a.path.localeCompare(b.path));
}

/**
 * Pick the navigation card for `direction` relative to the current card.
 *
 * @param {TopicCard[]} list
 * @param {?TopicCard} current
 * @param {'first'|'prev'|'next'|'last'} direction
 * @returns {?TopicCard}
 */
export function findNavigationTarget(list, current, direction) {
  if (!list.length) return null;
  if (direction === 'first') return list[0];
  if (direction === 'last') return list.at(-1);
  if (!current) return direction === 'next' ? list[0] : list.at(-1);
  const index = list.findIndex((card) => card.key === current.key);
  if (index >= 0) {
    const nextIndex = direction === 'next' ? index + 1 : index - 1;
    return list[Math.max(0, Math.min(list.length - 1, nextIndex))];
  }
  // The current card is an ancestor: step from its sentence range.
  return direction === 'next'
    ? list.find((card) => card.start >= current.start) || list.at(-1)
    : [...list].reverse().find((card) => card.start < current.start) || list[0];
}

/**
 * Place cards beside their measured anchors, falling back to stacking cards
 * that have nothing measured, then resolve overlaps.
 *
 * @param {TopicCard[]} cards
 * @param {function(TopicCard): ?{top: number, bottom: number}} measure
 * @returns {TopicCard[]}
 */
export function layoutCards(cards, measure) {
  const fallbackTopByDepth = new Map();
  const placed = cards.map((card) => {
    const rect = measure(card);
    const fallbackTop = fallbackTopByDepth.get(card.depth) ?? 0;
    const top = rect ? rect.top : fallbackTop;
    const height = rect ? Math.max(CARD_HEIGHT, rect.bottom - rect.top) : CARD_HEIGHT;
    fallbackTopByDepth.set(card.depth, top + height + CARD_VERTICAL_GAP);
    return { ...card, top, height };
  });
  return clampCardsToParents(resolveColumnOverlaps(placed));
}

/**
 * Within a column, keep cards in source order without overlapping where that
 * is possible without pulling them far from their sentences. Dense columns
 * keep some overlap; alignment with the text wins (see extension topicCards).
 *
 * @param {TopicCard[]} cards
 * @returns {TopicCard[]}
 */
export function resolveColumnOverlaps(cards) {
  const byDepth = new Map();
  for (const card of cards) {
    if (!byDepth.has(card.depth)) byDepth.set(card.depth, []);
    byDepth.get(card.depth).push(card);
  }
  const adjusted = new Map();
  for (const column of byDepth.values()) {
    resolveColumn(
      [...column].sort((a, b) => a.start - b.start || a.top - b.top),
      adjusted
    );
  }
  return cards.map((card) => ({ ...card, ...adjusted.get(card.key) }));
}

/** @param {TopicCard[]} ordered @param {Map<string, {top: number, height: number}>} adjusted */
function resolveColumn(ordered, adjusted) {
  let prevBottom = -Infinity;
  let measuredFloor = -Infinity;
  let resolvedFloor = -Infinity;
  ordered.forEach((card, index) => {
    const stackedTop = Math.max(card.top, prevBottom + CARD_VERTICAL_GAP);
    // A card measured above its predecessor is mis-measured: stack it.
    const boundedTop =
      card.top < measuredFloor ? stackedTop : Math.min(stackedTop, card.top + CARD_MAX_PUSH);
    const top = Math.max(boundedTop, resolvedFloor);
    measuredFloor = Math.max(measuredFloor, card.top);
    resolvedFloor = top;
    let bottom = Math.max(card.top + card.height, top + CARD_MIN_HEIGHT);
    const next = ordered[index + 1];
    if (next && next.top - CARD_VERTICAL_GAP >= top + CARD_MIN_HEIGHT) {
      bottom = Math.min(bottom, next.top - CARD_VERTICAL_GAP);
    }
    prevBottom = bottom;
    adjusted.set(card.key, { top, height: bottom - top });
  });
}

/**
 * Keep each child card inside the extent of the parent run that contains it.
 *
 * @param {TopicCard[]} cards
 * @returns {TopicCard[]}
 */
export function clampCardsToParents(cards) {
  const resolved = new Map();
  const ordered = [...cards].sort((a, b) => a.depth - b.depth);
  for (const card of ordered) {
    const parent = findParentCard(card, resolved);
    resolved.set(card.key, parent ? clampToParent(card, parent) : card);
  }
  return cards.map((card) => resolved.get(card.key));
}

/** @param {TopicCard} card @param {Map<string, TopicCard>} resolved @returns {?TopicCard} */
function findParentCard(card, resolved) {
  if (card.depth === 0) return null;
  const parentPath = formatTopicPath(splitTopicPath(card.path).slice(0, -1));
  for (const candidate of resolved.values()) {
    if (
      candidate.path === parentPath &&
      candidate.start <= card.start &&
      candidate.end >= card.end
    ) {
      return candidate;
    }
  }
  return null;
}

/** @param {TopicCard} card @param {TopicCard} parent @returns {TopicCard} */
function clampToParent(card, parent) {
  const parentBottom = parent.top + parent.height;
  const top = Math.min(Math.max(card.top, parent.top), parentBottom - CARD_MIN_HEIGHT);
  const bottom = Math.min(card.top + card.height, parentBottom);
  return { ...card, top, height: Math.max(CARD_MIN_HEIGHT, bottom - top) };
}

/**
 * Union of measured rects, in a coordinate space chosen by the caller.
 *
 * @param {Array<?{top: number, bottom: number}>} rects
 * @returns {?{top: number, bottom: number}}
 */
export function unionRects(rects) {
  let top = Infinity;
  let bottom = -Infinity;
  for (const rect of rects) {
    if (!rect) continue;
    top = Math.min(top, rect.top);
    bottom = Math.max(bottom, rect.bottom);
  }
  return Number.isFinite(top) ? { top, bottom } : null;
}

/** @param {string} value @returns {number} */
function hashString(value) {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

/** @param {string} path @returns {number} */
function topicHue(path) {
  return (hashString(splitTopicPath(path)[0] || '') + 170) % 360;
}

/** Rail accent: same hue per root topic, lighter for deeper levels. */
export function topicAccentColor(path, depth) {
  const saturation = Math.max(24, 52 - depth * 5);
  const lightness = Math.min(66, 42 + depth * 5);
  return `hsl(${topicHue(path)}, ${saturation}%, ${lightness}%)`;
}

/** Sentence highlight tint matching the topic accent. */
export function topicHighlightColor(path, depth) {
  const saturation = Math.max(30, 60 - depth * 5);
  return `hsl(${topicHue(path)}, ${saturation}%, 86%)`;
}

/** Cards widen on zoom-out so titles keep a readable on-screen size. */
export function getZoomCardWidth(scale) {
  return CARD_WIDTH * Math.max(1, 1 / clampScale(scale));
}

/** @param {number} scale @returns {number} */
export function getZoomSummaryWidth(scale) {
  return Math.min(SUMMARY_CARD_MAX_WIDTH, SUMMARY_CARD_WIDTH * Math.max(1, 1 / clampScale(scale)));
}

/** @param {number} scale @returns {number} */
export function getZoomTitleFontSize(scale) {
  return CARD_BASE_TITLE_FONT_SIZE * Math.max(1, 1.25 / clampScale(scale) - 0.25);
}

/** Title lines and the largest title font a card of `height` can hold. */
export function getCardTitleFit(height) {
  const lines = height < CARD_COMPACT_HEIGHT ? 1 : 2;
  const available = Math.max(1, height - CARD_CHROME_HEIGHT);
  return { lines, maxFontSize: Math.max(1, available / (CARD_TITLE_LINE_HEIGHT * lines)) };
}

/** @param {number} levels @param {number} cardWidth @returns {number} */
export function getRailWidth(levels, cardWidth) {
  return levels * cardWidth + (levels - 1) * COLUMN_GAP + RAIL_PADDING * 2;
}

/**
 * Translate that keeps `cursor` over the same content point across a zoom.
 *
 * @param {{cursor: {x: number, y: number}, translate: {x: number, y: number}, scale: number, nextScale: number}} params
 * @returns {{x: number, y: number}}
 */
export function cursorAnchoredTranslate({ cursor, translate, scale, nextScale }) {
  const ratio = nextScale / scale;
  return {
    x: cursor.x - (cursor.x - translate.x) * ratio,
    y: cursor.y - (cursor.y - translate.y) * ratio,
  };
}

/**
 * Body for `/openai/summary` for one card.
 *
 * @param {TopicCard} card
 * @param {Map<number, CanvasSentence>} sentencesByNumber
 * @returns {{topic: string, sentences: string[]}}
 */
export function buildSummaryRequest(card, sentencesByNumber) {
  return {
    topic: card.path,
    sentences: card.sentences
      .map((number) => sentencesByNumber.get(number)?.text || '')
      .filter((text) => text.trim()),
  };
}

/**
 * Human label for a card's sentence range, in per-post sentence numbers.
 *
 * @param {TopicCard} card
 * @param {Map<number, CanvasSentence>} sentencesByNumber
 * @returns {string}
 */
export function formatSentenceRange(card, sentencesByNumber) {
  const first = sentencesByNumber.get(card.start)?.post_sentence_number ?? card.start;
  const last = sentencesByNumber.get(card.end)?.post_sentence_number ?? card.end;
  return first === last ? `sentence ${first}` : `sentences ${first}–${last}`;
}
