// Topic-path hierarchy for the snippets of one anthology subtopic.
// Mirrors the /hierarchy swim lanes (fh-* markup) and adds snippet counts so
// the distribution of topics is visible at a glance.
import { escapeHtml } from './anthology-common.js';
import {
  accentColor,
  buildTopicTree,
  collectNonLeafPaths,
  getMaxTopicLevel,
  highlightColor,
} from '../components/feed-hierarchy.js';

/** @param {string} topicPath e.g. "Tech > AI" @returns {string[]} */
export function topicParts(topicPath) {
  return String(topicPath || '')
    .split('>')
    .map((part) => part.trim())
    .filter(Boolean);
}

/** @param {Array<Record<string, any>>} snippets */
export function hasTopics(snippets) {
  return (snippets || []).some((snippet) => topicParts(snippet.topic_path).length > 0);
}

/**
 * Whether a snippet's topic path lies at or below `path` ("a>b").
 * @param {Record<string, any>} snippet
 * @param {string} path
 */
export function snippetInTopic(snippet, path) {
  const prefix = topicParts(path);
  const parts = topicParts(snippet.topic_path);
  return prefix.length > 0 && prefix.every((part, index) => parts[index] === part);
}

/**
 * One topic per distinct path, in the shape buildTopicTree expects.
 * @param {Array<Record<string, any>>} snippets
 * @returns {Array<{name: string, snippets_count: number, unread_count: number}>}
 */
export function snippetTopics(snippets) {
  const topics = new Map();
  (snippets || []).forEach((snippet) => {
    const name = topicParts(snippet.topic_path).join('>');
    if (!name) return;
    const topic = topics.get(name) || { name, snippets_count: 0, unread_count: 0 };
    topic.snippets_count += 1;
    topic.unread_count += snippet.read ? 0 : 1;
    topics.set(name, topic);
  });
  return Array.from(topics.values());
}

/** Snippet count of an entry including every descendant. */
function entryCount(entry) {
  const own = entry.node.topic ? entry.node.topic.snippets_count : 0;
  return Array.from(entry.children.values()).reduce((sum, child) => sum + entryCount(child), own);
}

/** Biggest topics first so the distribution reads top-down. */
function sortedChildren(children) {
  return Array.from(children.values()).sort((a, b) => entryCount(b) - entryCount(a));
}

function entryStyle(rootName, depth) {
  return `--fh-accent-color: ${accentColor(rootName, depth)}; --fh-card-bg: ${highlightColor(rootName, depth)}`;
}

function shareBar(count, total, color) {
  const share = total ? Math.round((count / total) * 100) : 0;
  return (
    `<span class="anth-topics__share" style="--fh-accent-color: ${color}" title="${count} of ${total} snippets">` +
    `<span class="anth-topics__bar" style="--anth-topic-share: ${share}%"></span>` +
    `<span class="anth-topics__count">${count} · ${share}%</span></span>`
  );
}

function filterButton(entry) {
  return (
    `<button type="button" class="fh-topic-menu" data-action="topic-filter" data-path="${escapeHtml(entry.node.fullPath)}"` +
    ` title="Show these snippets" aria-label="Show snippets of ${escapeHtml(entry.node.name)}">›</button>`
  );
}

function renderLeaf(entry, rootName, total) {
  const { node } = entry;
  return (
    '<div class="fh-leaf-row">' +
    `<div class="fh-leaf" style="${entryStyle(rootName, node.depth)}" title="${escapeHtml(node.fullPath.replace(/>/g, ' › '))}">` +
    '<span class="fh-leaf__spacer" aria-hidden="true"></span>' +
    `<span class="fh-leaf__label">${escapeHtml(node.name)}</span>${filterButton(entry)}</div>` +
    shareBar(entryCount(entry), total, accentColor(rootName, node.depth)) +
    '</div>'
  );
}

function renderBranch(entry, rootName, total, collapsed) {
  const { node } = entry;
  const isCollapsed = collapsed.has(node.fullPath);
  const label = escapeHtml(node.name);
  const own = node.topic
    ? `<div class="fh-leaf-row"><span class="anth-muted">Directly under ${label}</span>${shareBar(node.topic.snippets_count, total, accentColor(rootName, node.depth))}</div>`
    : '';
  const children = isCollapsed
    ? ''
    : `<div class="fh-branch__children">${own}${sortedChildren(entry.children)
        .map((child) => renderEntry(child, rootName, total, collapsed))
        .join('')}</div>`;
  return (
    `<div class="fh-branch${isCollapsed ? ' fh-branch--collapsed' : ''}">` +
    `<div class="fh-branch__label" style="${entryStyle(rootName, node.depth)}" title="${escapeHtml(node.fullPath.replace(/>/g, ' › '))}">` +
    `<button type="button" class="fh-toggle" data-action="topic-toggle" data-path="${escapeHtml(node.fullPath)}"` +
    ` aria-expanded="${!isCollapsed}" aria-label="${isCollapsed ? 'Expand' : 'Collapse'} ${label}">${isCollapsed ? '›' : '‹'}</button>` +
    `<span class="fh-branch__label-text">${label} <span class="anth-topics__count">${entryCount(entry)}</span></span>` +
    `${filterButton(entry)}</div>` +
    children +
    '</div>'
  );
}

function renderEntry(entry, rootName, total, collapsed) {
  return entry.children.size === 0
    ? renderLeaf(entry, rootName, total)
    : renderBranch(entry, rootName, total, collapsed);
}

function renderLevels(maxLevel, level) {
  if (maxLevel < 1) return '';
  const buttons = Array.from({ length: maxLevel + 1 }, (_, index) => {
    const active = index === level ? ' is-active' : '';
    return `<button type="button" class="anth-btn anth-btn--small${active}" data-action="topic-level" data-level="${index}" title="Show topic levels 1–${index + 1}">${index + 1}</button>`;
  }).join('');
  return `<div class="anth-topics__levels" aria-label="Hierarchy depth">Levels ${buttons}</div>`;
}

/**
 * Paths to collapse so only levels 1..level+1 stay open.
 * @param {Array<Record<string, any>>} snippets
 * @param {number} level
 * @returns {Set<string>}
 */
export function collapsedForLevel(snippets, level) {
  const roots = buildTopicTree(snippetTopics(snippets));
  return new Set(collectNonLeafPaths(roots, { minDepth: level }));
}

/** Deepest zero-based topic level among the snippets. */
export function maxTopicLevel(snippets) {
  return getMaxTopicLevel(snippetTopics(snippets));
}

/**
 * @param {Array<Record<string, any>>} snippets
 * @param {{level: number, collapsed: Set<string>}} topicView
 * @returns {string}
 */
export function renderTopicHierarchy(snippets, topicView) {
  const topics = snippetTopics(snippets);
  if (!topics.length) {
    return '<p class="anth-empty">These snippets have no topics.</p>';
  }
  const total = (snippets || []).length;
  const tagged = topics.reduce((sum, topic) => sum + topic.snippets_count, 0);
  const roots = buildTopicTree(topics).sort((a, b) => entryCount(b) - entryCount(a));
  const untagged = total - tagged;
  const summary =
    `${topics.length} topic${topics.length === 1 ? '' : 's'} across ${tagged} snippet${tagged === 1 ? '' : 's'}` +
    (untagged ? ` · ${untagged} without a topic` : '');
  return (
    `<div class="anth-topics__head"><p class="anth-muted">${escapeHtml(summary)}</p>` +
    `${renderLevels(getMaxTopicLevel(topics), topicView.level)}</div>` +
    `<div class="anth-topics"><div class="fh-root">${roots
      .map((entry) => renderEntry(entry, entry.node.name, total, topicView.collapsed))
      .join('')}</div></div>`
  );
}
