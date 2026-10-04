/* global window, document, console, setTimeout, clearTimeout */
// Anthology explorer: themes -> clusters -> snippets.
import {
  escapeHtml,
  fetchJson,
  formatDate,
  formatPercent,
  isActive,
  postJson,
  readJsonScript,
  renderStepper,
  scopeLabel,
} from './libs/anthology-common.js';

export const UNSORTED_ID = 'unsorted';
export const OTHER_THEME_ID = '__other';
export const SORT_MODES = ['relevance', 'newest', 'oldest'];
const POLL_MS = 4000;
const WORD_CHAR = '[\\p{L}\\p{N}]';

// ============================================================
// Selection / navigation
// ============================================================

/** @param {string} hash e.g. "#c3" @returns {string} */
export function parseHash(hash) {
  const raw = String(hash || '').replace(/^#/, '');
  try {
    return decodeURIComponent(raw).trim();
  } catch {
    return raw.trim();
  }
}

/** @param {{kind: string, id: string}|null} selection @returns {string} */
export function selectionHash(selection) {
  return selection ? `#${encodeURIComponent(selection.id)}` : '';
}

/**
 * Themes in display order, plus a virtual theme for clusters without one.
 * @param {Record<string, any>|null} result
 */
export function themesWithOrphans(result) {
  const themes = Array.isArray(result?.themes) ? result.themes : [];
  const clusters = result?.clusters || {};
  const claimed = new Set(themes.flatMap((theme) => theme.cluster_ids || []));
  const orphans = Object.keys(clusters).filter((id) => !claimed.has(id));
  if (!orphans.length) {
    return themes;
  }
  const size = orphans.reduce((sum, id) => sum + (clusters[id].snippet_ids || []).length, 0);
  return [
    ...themes,
    {
      id: OTHER_THEME_ID,
      label: 'Other clusters',
      keywords: [],
      size,
      cluster_ids: orphans,
      virtual: true,
    },
  ];
}

/** @returns {{kind: 'cluster'|'theme'|'unsorted', id: string}|null} */
export function resolveSelection(id, result) {
  if (!id || !result) {
    return null;
  }
  if (id === UNSORTED_ID) {
    return (result.unsorted || []).length ? { kind: 'unsorted', id } : null;
  }
  if (result.clusters && result.clusters[id]) {
    return { kind: 'cluster', id };
  }
  return themesWithOrphans(result).some((theme) => theme.id === id) ? { kind: 'theme', id } : null;
}

export function defaultSelection(result) {
  const themes = themesWithOrphans(result);
  if (themes.length) {
    return { kind: 'theme', id: themes[0].id };
  }
  return resolveSelection(UNSORTED_ID, result);
}

/** Cluster ids in the order the tree shows them. */
export function clusterOrder(result) {
  return themesWithOrphans(result).flatMap((theme) =>
    (theme.cluster_ids || []).filter((id) => result.clusters && result.clusters[id])
  );
}

/** @returns {string|null} cluster id `delta` steps from `currentId` */
export function stepCluster(order, currentId, delta) {
  if (!order.length) {
    return null;
  }
  const index = order.indexOf(currentId);
  if (index === -1) {
    return delta > 0 ? order[0] : order[order.length - 1];
  }
  return order[Math.min(Math.max(index + delta, 0), order.length - 1)];
}

export function themeForCluster(result, clusterId) {
  const theme = themesWithOrphans(result).find((item) =>
    (item.cluster_ids || []).includes(clusterId)
  );
  return theme ? theme.id : null;
}

// ============================================================
// Snippet list operations
// ============================================================

/** Sentence-level read rollup for loaded snippets. */
export function summarizeRead(snippets) {
  return (snippets || []).reduce(
    (acc, snippet) => {
      (snippet.sentences || []).forEach((sentence) => {
        acc.total += 1;
        acc.unread += sentence.read ? 0 : 1;
      });
      return acc;
    },
    { unread: 0, total: 0 }
  );
}

export function filterSnippets(snippets, unreadOnly) {
  const list = snippets || [];
  return unreadOnly ? list.filter((snippet) => !snippet.read) : list.slice();
}

function byDate(direction) {
  return (a, b) => {
    const left = a.date ?? null;
    const right = b.date ?? null;
    if (left === right) return 0;
    if (left === null) return 1;
    if (right === null) return -1;
    return direction * (left - right);
  };
}

/** Relevance keeps server order but lifts the start snippet to the top. */
export function sortSnippets(snippets, mode, startId) {
  const list = (snippets || []).slice();
  if (mode === 'newest') return list.sort(byDate(-1));
  if (mode === 'oldest') return list.sort(byDate(1));
  const start = list.findIndex((snippet) => snippet.id === startId);
  if (start > 0) list.unshift(...list.splice(start, 1));
  return list;
}

/** In skim mode only the start snippet is shown in full. */
export function visibleSentences(snippet, { skim, isStart, expanded }) {
  const sentences = snippet.sentences || [];
  if (!skim || isStart || expanded) {
    return { sentences, truncated: false };
  }
  return { sentences: sentences.slice(0, 1), truncated: sentences.length > 1 };
}

// ============================================================
// Highlighting
// ============================================================

/**
 * Pattern for one keyword. Longer single words drop a short ending so
 * inflected forms match too (e.g. "приставка" also highlights "приставки").
 * @param {string} keyword
 * @returns {string}
 */
export function keywordPattern(keyword) {
  const isPhrase = /\s/.test(keyword);
  let stem = keyword;
  if (!isPhrase && keyword.length >= 8) stem = keyword.slice(0, -2);
  else if (!isPhrase && keyword.length >= 6) stem = keyword.slice(0, -1);
  const escaped = stem.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
  return keyword.length >= 4 ? `${escaped}${WORD_CHAR}*` : escaped;
}

/** @param {string[]} keywords @returns {RegExp|null} */
export function buildKeywordRegex(keywords) {
  const parts = (keywords || [])
    .map((keyword) => String(keyword || '').trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map(keywordPattern);
  if (!parts.length) {
    return null;
  }
  return new RegExp(`(?<!${WORD_CHAR})(?:${parts.join('|')})(?!${WORD_CHAR})`, 'giu');
}

/** Escape `text`, wrapping regex matches in <mark>. */
export function highlightText(text, re) {
  const source = String(text ?? '');
  if (!re) {
    return escapeHtml(source);
  }
  let html = '';
  let last = 0;
  for (const match of source.matchAll(re)) {
    if (!match[0]) continue;
    html += escapeHtml(source.slice(last, match.index));
    html += `<mark>${escapeHtml(match[0])}</mark>`;
    last = match.index + match[0].length;
  }
  return html + escapeHtml(source.slice(last));
}

// ============================================================
// Small render helpers
// ============================================================

export function scoreDots(score) {
  const value = Math.max(0, Math.min(5, Math.round(Number(score) || 0)));
  return (
    `<span class="anth-dots" title="Quality ${value}/5" aria-label="Quality ${value} of 5">` +
    `${'●'.repeat(value)}<span class="anth-dots__off">${'○'.repeat(5 - value)}</span></span>`
  );
}

export function unreadBadge(read) {
  if (!read || !read.total) {
    return '';
  }
  if (!read.unread) {
    return '<span class="anth-count anth-count--done" title="All read">✓</span>';
  }
  return `<span class="anth-count" title="${read.unread} of ${read.total} sentences unread">${read.unread}</span>`;
}

export function formatDateRange(min, max) {
  const from = formatDate(min);
  const to = formatDate(max);
  if (!from && !to) return '';
  if (!from || !to || from === to) return from || to;
  return `${from} – ${to}`;
}

export function keywordChips(keywords, limit = 8) {
  const list = (keywords || []).slice(0, limit);
  if (!list.length) return '';
  return `<ul class="anth-chips">${list.map((word) => `<li class="anth-chip">${escapeHtml(word)}</li>`).join('')}</ul>`;
}

function kindBadge(kind) {
  return kind
    ? `<span class="anth-kind anth-kind--${escapeHtml(kind)}">${escapeHtml(kind)}</span>`
    : '';
}

function intruderFlag(cluster) {
  return cluster.intruder_ok === false
    ? '<span class="anth-warn" title="Failed the intruder test: the cluster may be incoherent">⚠</span>'
    : '';
}

function markButton(kind, id, read, labels = ['Mark read', 'Mark unread']) {
  const allRead = Boolean(read && read.total && !read.unread);
  return (
    `<button type="button" class="anth-btn anth-btn--small" data-action="mark" data-kind="${escapeHtml(kind)}"` +
    ` data-id="${escapeHtml(id)}" data-readed="${allRead ? 'false' : 'true'}">${allRead ? labels[1] : labels[0]}</button>`
  );
}

// ============================================================
// Header
// ============================================================

export function renderMetrics(metrics) {
  if (!metrics) return '';
  const items = [
    ['Snippets', metrics.snippets_total ?? '—'],
    ['Coverage', formatPercent(metrics.coverage)],
    ['Clusters', metrics.clusters_final ?? '—'],
    ['Intruder accuracy', formatPercent(metrics.intruder_accuracy)],
    [
      'LLM calls',
      `${metrics.llm_calls ?? 0}${metrics.llm_cached ? ` (+${metrics.llm_cached} cached)` : ''}`,
    ],
  ];
  if (metrics.recovery_snippets_input > 0) {
    items.push([
      'Recovered from unsorted',
      `${metrics.recovery_snippets_assigned ?? 0}/${metrics.recovery_snippets_input}`,
    ]);
  }
  if (metrics.loose_snippets > 0) {
    items.push(['Loosely labeled', `${metrics.loose_snippets} in ${metrics.loose_clusters ?? 0} topics`]);
  }
  return `<dl class="anth-metrics">${items
    .map(
      ([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`
    )
    .join('')}</dl>`;
}

function renderHeadState(payload) {
  if (isActive(payload)) {
    const note = payload.stuck
      ? 'No progress for an hour. Retry to restart.'
      : payload.status === 'pending'
        ? 'Queued…'
        : 'Building…';
    const retry = payload.stuck
      ? '<button type="button" class="anth-btn" data-action="retry">Retry</button>'
      : '';
    return `<div class="anth-head__progress">${renderStepper(payload.status, payload.stage)}<span class="anth-muted">${note}</span>${retry}</div>`;
  }
  if (payload.status === 'failed') {
    return (
      `<div class="anth-head__progress"><p class="anth-error">${escapeHtml(payload.error || 'Build failed')}</p>` +
      '<button type="button" class="anth-btn" data-action="retry">Retry</button></div>'
    );
  }
  if (payload.stale) {
    return '<div class="anth-head__progress"><span class="anth-muted">Sources changed since this was built.</span><button type="button" class="anth-btn" data-action="retry">Rebuild</button></div>';
  }
  return '';
}

export function renderHeader(payload) {
  const result = payload.result || {};
  const stale = payload.stale ? '<span class="anth-badge anth-badge--warn">stale</span>' : '';
  return (
    '<div class="anth-head__title">' +
    `<h1>${escapeHtml(payload.seed_value)}</h1>` +
    `<span class="anth-badge anth-badge--${escapeHtml(payload.status)}">${escapeHtml(payload.status)}</span>${stale}` +
    `<span class="anth-muted">${escapeHtml(scopeLabel(payload.scope))}</span>` +
    '</div>' +
    renderHeadState(payload) +
    renderMetrics(result.metrics)
  );
}

// ============================================================
// Tree
// ============================================================

function renderTreeCluster(cluster, selection) {
  const active = selection && selection.kind === 'cluster' && selection.id === cluster.id;
  return (
    `<li><button type="button" class="anth-tree__cluster${active ? ' is-active' : ''}" data-action="select" data-id="${escapeHtml(cluster.id)}">` +
    `<span class="anth-tree__label">${intruderFlag(cluster)}${escapeHtml(cluster.label || cluster.id)}</span>` +
    `<span class="anth-tree__meta">${kindBadge(cluster.kind)}${scoreDots(cluster.score)}${unreadBadge(cluster.read)}</span>` +
    '</button></li>'
  );
}

function renderTreeTheme(theme, result, selection, expanded) {
  const clusters = (theme.cluster_ids || []).map((id) => result.clusters[id]).filter(Boolean);
  const open = expanded.has(theme.id);
  const active = selection && selection.kind === 'theme' && selection.id === theme.id;
  const children = open
    ? `<ul class="anth-tree__clusters">${clusters.map((c) => renderTreeCluster(c, selection)).join('')}</ul>`
    : '';
  return (
    `<li class="anth-tree__theme${open ? ' is-open' : ''}${theme.loose ? ' anth-tree__theme--loose' : ''}">` +
    '<div class="anth-tree__row">' +
    `<button type="button" class="anth-tree__toggle" data-action="toggle" data-id="${escapeHtml(theme.id)}" aria-expanded="${open}" aria-label="Toggle clusters">${open ? '▾' : '▸'}</button>` +
    `<button type="button" class="anth-tree__theme-btn${active ? ' is-active' : ''}" data-action="select" data-id="${escapeHtml(theme.id)}">` +
    `<span class="anth-tree__label">${escapeHtml(theme.label || theme.id)}</span>` +
    `<span class="anth-tree__meta"><span class="anth-muted">${escapeHtml(theme.size ?? clusters.length)}</span>${unreadBadge(theme.read)}</span>` +
    '</button></div>' +
    children +
    '</li>'
  );
}

export function renderTree(result, selection, expanded) {
  if (!result) {
    return '<p class="anth-empty">Themes will appear when the build finishes.</p>';
  }
  const themes = themesWithOrphans(result)
    .map((t) => renderTreeTheme(t, result, selection, expanded))
    .join('');
  const unsortedCount = (result.unsorted || []).length;
  const unsortedActive = selection && selection.kind === 'unsorted';
  const unsorted = unsortedCount
    ? `<button type="button" class="anth-tree__unsorted${unsortedActive ? ' is-active' : ''}" data-action="select" data-id="${UNSORTED_ID}">` +
      `<span class="anth-tree__label">Unsorted</span><span class="anth-tree__meta"><span class="anth-muted">${unsortedCount}</span>${unreadBadge(result.unsorted_read)}</span></button>`
    : '';
  return `<h2 class="anth-pane__title">Themes</h2><ul class="anth-tree">${themes}</ul>${unsorted}`;
}

// ============================================================
// Center pane
// ============================================================

function renderClusterCard(cluster) {
  return (
    `<li><button type="button" class="anth-cluster-card" data-action="select" data-id="${escapeHtml(cluster.id)}">` +
    `<span class="anth-cluster-card__head"><strong>${intruderFlag(cluster)}${escapeHtml(cluster.label || cluster.id)}</strong>${kindBadge(cluster.kind)}</span>` +
    keywordChips(cluster.keywords, 5) +
    `<span class="anth-cluster-card__meta"><span>${(cluster.snippet_ids || []).length} snippets</span>${scoreDots(cluster.score)}${unreadBadge(cluster.read)}</span>` +
    '</button></li>'
  );
}

export function renderThemeOverview(theme, result) {
  const clusters = (theme.cluster_ids || []).map((id) => result.clusters[id]).filter(Boolean);
  const action = theme.virtual
    ? ''
    : markButton('theme', theme.id, theme.read, ['Mark theme read', 'Mark theme unread']);
  return (
    `<header class="anth-main__head"><div><h2>${escapeHtml(theme.label || theme.id)}</h2>${keywordChips(theme.keywords)}</div>${action}</header>` +
    `<p class="anth-muted">${clusters.length} subtopics · ${escapeHtml(theme.size ?? 0)} snippets. Pick one to read.</p>` +
    `<ul class="anth-cluster-cards">${clusters.map(renderClusterCard).join('')}</ul>`
  );
}

function renderToolbar(view) {
  const options = SORT_MODES.map(
    (mode) => `<option value="${mode}"${view.sort === mode ? ' selected' : ''}>${mode}</option>`
  ).join('');
  return (
    '<div class="anth-toolbar">' +
    `<label><input type="checkbox" data-control="unreadOnly"${view.unreadOnly ? ' checked' : ''}/> Unread only</label>` +
    `<label><input type="checkbox" data-control="skim"${view.skim ? ' checked' : ''}/> Skim</label>` +
    `<label>Sort <select data-control="sort">${options}</select></label>` +
    '</div>'
  );
}

export function renderClusterHead(cluster, read, feedCount) {
  if (!cluster) {
    return (
      `<header class="anth-main__head"><div><h2>Unsorted</h2><p class="anth-muted">Snippets that did not fit any subtopic.</p></div>` +
      `${markButton(UNSORTED_ID, UNSORTED_ID, read, ['Mark all read', 'Mark all unread'])}</header>`
    );
  }
  const range = formatDateRange(cluster.date_min, cluster.date_max);
  const meta = [
    range,
    `${feedCount} feed${feedCount === 1 ? '' : 's'}`,
    `${read.unread}/${read.total} unread`,
  ]
    .filter(Boolean)
    .map((item) => `<span>${escapeHtml(item)}</span>`)
    .join('');
  return (
    `<header class="anth-main__head"><div><h2>${intruderFlag(cluster)}${escapeHtml(cluster.label || cluster.id)} ${kindBadge(cluster.kind)}</h2>` +
    `${keywordChips(cluster.keywords)}<p class="anth-main__meta">${meta}</p></div>` +
    `${markButton('cluster', cluster.id, read, ['Mark cluster read', 'Mark cluster unread'])}</header>`
  );
}

function renderBreadcrumb(topicPath) {
  const parts = String(topicPath || '')
    .split('>')
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) return '';
  return `<p class="anth-snippet__path">${parts.map(escapeHtml).join(' › ')}</p>`;
}

function renderSentences(snippet, options) {
  const { sentences, truncated } = visibleSentences(snippet, options);
  if (!sentences.length) {
    return `<p class="anth-snippet__text">${highlightText(snippet.preview || '', options.re)}</p>`;
  }
  const body = sentences
    .map(
      (s) =>
        `<span class="anth-sentence${s.read ? ' anth-sentence--read' : ''}">${highlightText(s.text, options.re)}</span>`
    )
    .join(' ');
  const more = truncated
    ? ` <button type="button" class="anth-link" data-action="expand" data-id="${escapeHtml(snippet.id)}">…more</button>`
    : '';
  return `<p class="anth-snippet__text">${body}${more}</p>`;
}

/** Resolve the display feed name for a snippet. */
export function snippetFeedTitle(snippet, feedTitles) {
  if (snippet.feed_title) return String(snippet.feed_title);
  const byId = feedTitles && snippet.feed_id ? feedTitles[snippet.feed_id] : '';
  return String(byId || snippet.feed_id || '');
}

/** Sentence numbers covered by a snippet, e.g. "0, 1". */
export function snippetSentenceLabel(snippet) {
  const indices = (snippet.sentence_indices || []).filter((i) => Number.isInteger(i));
  if (indices.length) return indices.join(', ');
  const numbers = (snippet.sentences || []).map((s) => s.number).filter((n) => Number.isInteger(n));
  return numbers.join(', ');
}

/**
 * @param {Record<string, any>} snippet
 * @param {{isStart?: boolean, skim?: boolean, expanded?: boolean, re?: RegExp|null, feedTitles?: Record<string, string>|null}} options
 */
export function renderSnippetCard(snippet, options = {}) {
  const read = snippet.read ? { unread: 0, total: 1 } : { unread: 1, total: 1 };
  const start = options.isStart
    ? '<span class="anth-badge anth-badge--start">Start here</span>'
    : '';
  const classes = [
    'anth-snippet',
    snippet.read ? 'anth-snippet--read' : '',
    options.isStart ? 'anth-snippet--start' : '',
  ]
    .filter(Boolean)
    .join(' ');
  const feed = snippetFeedTitle(snippet, options.feedTitles);
  const feedHtml = feed ? `<span class="anth-snippet__feed">${escapeHtml(feed)}</span>` : '';
  const label = snippetSentenceLabel(snippet);
  const sentencesHtml = label
    ? `<span title="Sentence numbers in the source post">sentences ${escapeHtml(label)}</span>`
    : '';
  const postId = snippet.post_id ? String(snippet.post_id) : '';
  const postHtml = postId
    ? `<a class="anth-snippet__link" href="/posts/${encodeURIComponent(postId)}" target="_blank" rel="noopener" title="Post ID: ${escapeHtml(postId)}">Full post</a>`
    : '';
  const originalHtml = snippet.post_url
    ? `<a class="anth-snippet__link" href="${escapeHtml(snippet.post_url)}" target="_blank" rel="noopener">Original ↗</a>`
    : '';
  const metaItems = [feedHtml, sentencesHtml, postHtml, originalHtml].filter(Boolean).join('');
  return (
    `<article class="${classes}" data-snippet-id="${escapeHtml(snippet.id)}">` +
    `<header class="anth-snippet__head">${start}` +
    `<a class="anth-snippet__title" href="/post-grouped/${encodeURIComponent(snippet.post_id)}" target="_blank" rel="noopener">${escapeHtml(snippet.title || 'Untitled post')}</a>` +
    `<span class="anth-muted">${escapeHtml(formatDate(snippet.date))}</span>` +
    markButton('snippet', snippet.id, read) +
    '</header>' +
    (metaItems ? `<p class="anth-snippet__meta">${metaItems}</p>` : '') +
    renderBreadcrumb(snippet.topic_path) +
    renderSentences(snippet, options) +
    '</article>'
  );
}

export function renderSnippetList(data, view, expandedSnippets) {
  const cluster = data.cluster;
  const startId = cluster ? cluster.start_snippet_id : null;
  const re = buildKeywordRegex(cluster ? cluster.keywords : []);
  const list = sortSnippets(filterSnippets(data.snippets, view.unreadOnly), view.sort, startId);
  if (!list.length) {
    return `<p class="anth-empty">${view.unreadOnly ? 'Everything here is read.' : 'No snippets.'}</p>`;
  }
  return list
    .map((snippet) =>
      renderSnippetCard(snippet, {
        isStart: snippet.id === startId,
        skim: view.skim,
        expanded: expandedSnippets.has(snippet.id),
        re,
        feedTitles: data.feed_titles || null,
      })
    )
    .join('');
}

// ============================================================
// Right pane
// ============================================================

function statRow(label, value) {
  return value === '' || value === null || value === undefined
    ? ''
    : `<div><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`;
}

function intruderText(value) {
  if (value === true) return 'passed';
  if (value === false) return '<span class="anth-error">failed</span>';
  return 'not run';
}

export function renderClusterStats(cluster, feedTitles) {
  const feeds = (cluster.feed_ids || [])
    .map((id) => `<li>${escapeHtml((feedTitles && feedTitles[id]) || id)}</li>`)
    .join('');
  const cohesion = Number.isFinite(Number(cluster.cohesion))
    ? Number(cluster.cohesion).toFixed(2)
    : '';
  return (
    '<h2 class="anth-pane__title">Subtopic</h2><dl class="anth-stats">' +
    statRow('Quality', `${scoreDots(cluster.score)} ${escapeHtml(cluster.score ?? '—')}/5`) +
    statRow('Cohesion', escapeHtml(cohesion)) +
    statRow('Intruder test', intruderText(cluster.intruder_ok)) +
    statRow('Snippets', escapeHtml((cluster.snippet_ids || []).length)) +
    statRow('Dates', escapeHtml(formatDateRange(cluster.date_min, cluster.date_max))) +
    '</dl>' +
    (feeds ? `<h3 class="anth-pane__subtitle">Feeds</h3><ul class="anth-feeds">${feeds}</ul>` : '')
  );
}

export function renderStatsPane(payload, selection) {
  const result = payload.result;
  if (!result) return '';
  if (selection && selection.kind === 'cluster') {
    return renderClusterStats(result.clusters[selection.id], payload.feed_titles);
  }
  const read = result.total_read || { unread: 0, total: 0 };
  return (
    '<h2 class="anth-pane__title">Overview</h2><dl class="anth-stats">' +
    statRow('Themes', escapeHtml((result.themes || []).length)) +
    statRow('Subtopics', escapeHtml(Object.keys(result.clusters || {}).length)) +
    statRow('Unsorted', escapeHtml((result.unsorted || []).length)) +
    statRow('Unread', escapeHtml(`${read.unread}/${read.total} sentences`)) +
    '</dl><p class="anth-muted anth-hint">Keys: j / k — next / previous subtopic.</p>'
  );
}

// ============================================================
// Controller
// ============================================================

function createState(payload) {
  return {
    payload,
    selection: null,
    expanded: new Set(),
    view: { unreadOnly: false, sort: 'relevance', skim: false },
    clusters: new Map(),
    loadingClusters: new Set(),
    payloadGeneration: 0,
    expandedSnippets: new Set(),
    timer: null,
  };
}

function createController(root, initialPayload) {
  const nodes = {
    head: root.querySelector('#anth-head'),
    tree: root.querySelector('#anth-tree'),
    main: root.querySelector('#anth-main'),
    stats: root.querySelector('#anth-stats'),
    note: root.querySelector('#anth-note'),
  };
  const state = createState(initialPayload);
  const apiBase = `/api/anthologies/${encodeURIComponent(initialPayload.id)}`;

  const note = (text) => {
    if (nodes.note) nodes.note.textContent = text || '';
  };

  function select(selection, updateHash = true) {
    if (!selection || !state.selection || selection.id !== state.selection.id) {
      state.expandedSnippets.clear();
    }
    state.selection = selection;
    if (selection && selection.kind === 'cluster') {
      const themeId = themeForCluster(state.payload.result, selection.id);
      if (themeId) state.expanded.add(themeId);
    }
    if (selection && selection.kind === 'theme') state.expanded.add(selection.id);
    if (updateHash && selection && window.location.hash !== selectionHash(selection)) {
      window.history.replaceState(null, '', selectionHash(selection));
    }
    render();
  }

  async function loadCluster(id) {
    if (state.loadingClusters.has(id)) return;
    const generation = state.payloadGeneration;
    state.loadingClusters.add(id);
    try {
      const data = await fetchJson(`${apiBase}/clusters/${encodeURIComponent(id)}`);
      if (generation !== state.payloadGeneration) return;
      state.clusters.set(id, data);
    } catch (error) {
      if (generation !== state.payloadGeneration) return;
      console.error('Unable to load cluster', id, error);
      state.clusters.set(id, { error: error.message });
    } finally {
      if (generation === state.payloadGeneration) state.loadingClusters.delete(id);
    }
    if (state.selection && state.selection.id === id) renderMain();
  }

  function renderClusterMain(id) {
    const data = state.clusters.get(id);
    if (!data) {
      nodes.main.innerHTML = '<p class="anth-empty">Loading snippets…</p>';
      loadCluster(id);
      return;
    }
    if (data.error) {
      nodes.main.innerHTML = `<p class="anth-error">${escapeHtml(data.error)}</p>`;
      return;
    }
    const cluster = data.cluster;
    const read = summarizeRead(data.snippets);
    nodes.main.innerHTML =
      renderClusterHead(cluster, read, cluster ? (cluster.feed_ids || []).length : 0) +
      renderToolbar(state.view) +
      `<div class="anth-snippets">${renderSnippetList(data, state.view, state.expandedSnippets)}</div>`;
  }

  function renderMain() {
    const result = state.payload.result;
    const selection = state.selection;
    if (!result || !selection) {
      nodes.main.innerHTML = `<p class="anth-empty">${result ? 'Nothing to show yet.' : 'The explorer opens once the build finishes.'}</p>`;
      return;
    }
    if (selection.kind === 'theme') {
      const theme = themesWithOrphans(result).find((item) => item.id === selection.id);
      nodes.main.innerHTML = renderThemeOverview(theme, result);
      return;
    }
    renderClusterMain(selection.id);
  }

  function render() {
    nodes.head.innerHTML = renderHeader(state.payload);
    nodes.tree.innerHTML = renderTree(state.payload.result, state.selection, state.expanded);
    nodes.stats.innerHTML = renderStatsPane(state.payload, state.selection);
    renderMain();
  }

  function applyPayload(payload) {
    state.payloadGeneration += 1;
    state.payload = payload;
    state.clusters.clear();
    state.loadingClusters.clear();
    const result = payload.result;
    const keep = state.selection && resolveSelection(state.selection.id, result);
    select(
      keep || resolveSelection(parseHash(window.location.hash), result) || defaultSelection(result),
      false
    );
  }

  async function poll() {
    clearTimeout(state.timer);
    if (!isActive(state.payload)) return;
    state.timer = setTimeout(async () => {
      try {
        applyPayload(await fetchJson(apiBase));
      } catch (error) {
        console.error('Anthology poll failed', error);
      }
      poll();
    }, POLL_MS);
  }

  async function markRead(button) {
    button.disabled = true;
    note('Updating…');
    try {
      const target = { kind: button.dataset.kind, id: button.dataset.id };
      applyPayload(
        await postJson(`${apiBase}/read`, { target, readed: button.dataset.readed === 'true' })
      );
      note('');
    } catch (error) {
      note(error.message);
      button.disabled = false;
    }
  }

  async function retry(button) {
    button.disabled = true;
    try {
      applyPayload(await postJson(`${apiBase}/retry`, {}));
      poll();
    } catch (error) {
      note(error.message);
      button.disabled = false;
    }
  }

  const actions = {
    select: (button) => select(resolveSelection(button.dataset.id, state.payload.result)),
    toggle: (button) => {
      const id = button.dataset.id;
      if (!state.expanded.delete(id)) state.expanded.add(id);
      nodes.tree.innerHTML = renderTree(state.payload.result, state.selection, state.expanded);
    },
    expand: (button) => {
      state.expandedSnippets.add(button.dataset.id);
      renderMain();
    },
    mark: markRead,
    retry,
  };

  function onClick(event) {
    const button = event.target.closest('[data-action]');
    if (button && actions[button.dataset.action]) actions[button.dataset.action](button);
  }

  function onChange(event) {
    const control = event.target.dataset ? event.target.dataset.control : null;
    if (!control) return;
    state.view[control] = control === 'sort' ? event.target.value : event.target.checked;
    renderMain();
  }

  function onKey(event) {
    if (event.target.closest && event.target.closest('input, select, textarea')) return;
    if ((event.key !== 'j' && event.key !== 'k') || !state.payload.result) return;
    const current =
      state.selection && state.selection.kind === 'cluster' ? state.selection.id : null;
    const next = stepCluster(
      clusterOrder(state.payload.result),
      current,
      event.key === 'j' ? 1 : -1
    );
    if (next) select({ kind: 'cluster', id: next });
  }

  function onHash() {
    const selection = resolveSelection(parseHash(window.location.hash), state.payload.result);
    if (selection && (!state.selection || selection.id !== state.selection.id))
      select(selection, false);
  }

  return {
    start() {
      root.addEventListener('click', onClick);
      root.addEventListener('change', onChange);
      document.addEventListener('keydown', onKey);
      window.addEventListener('hashchange', onHash);
      applyPayload(initialPayload);
      poll();
    },
  };
}

export function initAnthologyDetail() {
  const root = document.getElementById('anthology-app');
  const payload = readJsonScript('anthology-detail-data');
  if (!root || !payload || !payload.id) {
    return;
  }
  createController(root, payload).start();
}
