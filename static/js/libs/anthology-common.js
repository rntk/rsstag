/* global document, console, fetch */
// Shared helpers for the anthology list and detail pages.

export const STAGES = [
  { id: 'units', label: 'Snippets' },
  { id: 'candidates', label: 'Candidates' },
  { id: 'merge', label: 'Merge' },
  { id: 'label', label: 'Label' },
  { id: 'intruder', label: 'Intruder test' },
  { id: 'themes', label: 'Themes' },
  { id: 'done', label: 'Done' },
];

export const ACTIVE_STATUSES = ['pending', 'processing'];

/** @param {unknown} value @returns {string} */
export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** @param {{status?: string}|null|undefined} item @returns {boolean} */
export function isActive(item) {
  return Boolean(item) && ACTIVE_STATUSES.includes(String(item.status || ''));
}

/** @param {string|null|undefined} stage @returns {number} -1 when unknown */
export function stageIndex(stage) {
  return STAGES.findIndex((step) => step.id === stage);
}

/**
 * Compute per-step state for a stepper.
 * @param {string} status
 * @param {string|null|undefined} stage
 * @returns {Array<{id: string, label: string, state: 'done'|'current'|'failed'|'todo'}>}
 */
export function stepStates(status, stage) {
  const current = status === 'done' ? STAGES.length : stageIndex(stage);
  return STAGES.map((step, index) => {
    let state = 'todo';
    if (index < current) {
      state = 'done';
    } else if (index === current) {
      state = status === 'failed' ? 'failed' : 'current';
    }
    return { ...step, state };
  });
}

/** @returns {string} HTML for a 7-step progress bar */
export function renderStepper(status, stage) {
  const steps = stepStates(status, stage)
    .map(
      (step) =>
        `<li class="anth-stepper__step anth-stepper__step--${step.state}" title="${escapeHtml(step.label)}">` +
        `<span class="anth-stepper__label">${escapeHtml(step.label)}</span></li>`
    )
    .join('');
  return `<ol class="anth-stepper" aria-label="Progress">${steps}</ol>`;
}

/** @param {number|null|undefined} ratio 0..1 @returns {string} */
export function formatPercent(ratio) {
  const value = Number(ratio);
  if (ratio === null || ratio === undefined || !Number.isFinite(value)) {
    return '—';
  }
  return `${Math.round(value * 100)}%`;
}

/** @param {number|null|undefined} ts unix seconds @returns {string} YYYY-MM-DD */
export function formatDate(ts) {
  const value = Number(ts);
  if (!ts || !Number.isFinite(value)) {
    return '';
  }
  try {
    return new Date(value * 1000).toISOString().slice(0, 10);
  } catch {
    return '';
  }
}

/** @param {{mode?: string, feed_ids?: string[], post_ids?: string[]}|null|undefined} scope */
export function scopeLabel(scope) {
  const mode = scope && scope.mode ? scope.mode : 'all';
  if (mode === 'feeds') {
    const count = (scope.feed_ids || []).length;
    return `${count} feed${count === 1 ? '' : 's'}`;
  }
  if (mode === 'posts') {
    const count = (scope.post_ids || []).length;
    return `${count} post${count === 1 ? '' : 's'}`;
  }
  return 'All feeds';
}

/**
 * Fetch JSON and unwrap `{data}`; throws Error with the server message.
 * @param {string} url
 * @param {RequestInit} [options]
 */
export async function fetchJson(url, options = {}) {
  const response = await fetch(url, { credentials: 'include', ...options });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.error) {
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return payload.data;
}

/** @param {string} url @param {unknown} body */
export function postJson(url, body) {
  return fetchJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
}

/** @param {string} id @returns {any} parsed JSON from a <script type="application/json"> */
export function readJsonScript(id) {
  const node = document.getElementById(id);
  if (!node) {
    return null;
  }
  try {
    return JSON.parse(node.textContent || 'null');
  } catch (error) {
    console.error('Invalid embedded JSON', id, error);
    return null;
  }
}
