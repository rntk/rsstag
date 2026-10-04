/* global window, document, console, setTimeout, clearTimeout, fetch, FormData */
// Anthologies list page: create form, cards, retry/delete, progress polling.
import {
  escapeHtml,
  fetchJson,
  formatPercent,
  isActive,
  postJson,
  readJsonScript,
  renderStepper,
  scopeLabel,
} from './libs/anthology-common.js';

const POLL_MS = 4000;
const SEED_SUGGESTIONS_URL = '/tags-search';
const SEED_SUGGEST_DEBOUNCE_MS = 500;

/** @param {Record<string, any>} form @returns {{seed_type: string, seed_value: string, scope: object}} */
export function buildCreatePayload(form) {
  const feedId = String(form.feed_id || '').trim();
  return {
    seed_type: String(form.seed_type || 'tag'),
    seed_value: String(form.seed_value || '').trim(),
    scope: feedId ? { mode: 'feeds', feed_ids: [feedId] } : { mode: 'all' },
  };
}

/** @param {Array<{status?: string}>} items */
export function needsPolling(items) {
  return Array.isArray(items) && items.some(isActive);
}

/**
 * Render tag suggestions like the /group/tag/ search field does.
 * A suggestion fills the Tag input instead of navigating away.
 * @param {Array<{tag?: string, unread?: number, all?: number, info_url?: string}>} items
 * @returns {string}
 */
export function renderTagSuggestions(items) {
  if (!Array.isArray(items) || !items.length) {
    return '';
  }
  return items
    .map((item) => {
      const tag = String(item.tag ?? '');
      const counts = `${item.unread ?? '—'} / ${item.all ?? '—'}`;
      const info = item.info_url
        ? ` <a href="${escapeHtml(item.info_url)}" title="Tag info">...</a>`
        : '';
      return (
        '<p class="anth-suggest__item">' +
        `<button type="button" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)} (${escapeHtml(counts)})</button>` +
        `${info}</p>`
      );
    })
    .join('');
}

function renderCardStats(item) {
  const metrics = item.metrics || {};
  if (!item.has_result) {
    return '';
  }
  return (
    '<dl class="anth-card__stats">' +
    `<div><dt>Themes</dt><dd>${escapeHtml(item.themes_count || 0)}</dd></div>` +
    `<div><dt>Snippets</dt><dd>${escapeHtml(metrics.snippets_total ?? '—')}</dd></div>` +
    `<div><dt>Coverage</dt><dd>${escapeHtml(formatPercent(metrics.coverage))}</dd></div>` +
    '</dl>'
  );
}

function renderCardProgress(item) {
  if (isActive(item)) {
    return (
      renderStepper(item.status, item.stage) +
      (item.stuck ? '<p class="anth-error">No progress for an hour. Retry to restart.</p>' : '')
    );
  }
  if (item.status === 'failed') {
    return `<p class="anth-error">${escapeHtml(item.error || 'Build failed')}</p>`;
  }
  return '';
}

function renderCardActions(item) {
  const id = escapeHtml(item.id);
  const retry =
    item.status === 'processing' && !item.stuck
      ? ''
      : `<button type="button" class="anth-btn" data-action="retry" data-id="${id}">${
          item.status === 'done' ? 'Rebuild' : 'Retry'
        }</button>`;
  return (
    '<div class="anth-card__actions">' +
    `<a class="anth-btn anth-btn--primary" href="/anthologies/${encodeURIComponent(item.id)}">Open</a>` +
    retry +
    `<button type="button" class="anth-btn anth-btn--danger" data-action="delete" data-id="${id}">Delete</button>` +
    '</div>'
  );
}

/** @param {Record<string, any>} item @returns {string} */
export function renderCard(item) {
  const stale = item.stale ? '<span class="anth-badge anth-badge--warn">stale</span>' : '';
  return (
    `<article class="anth-card anth-card--${escapeHtml(item.status)}">` +
    '<header class="anth-card__head">' +
    `<h2 class="anth-card__title"><a href="/anthologies/${encodeURIComponent(item.id)}">${escapeHtml(
      item.seed_value
    )}</a></h2>` +
    `<span class="anth-badge anth-badge--${escapeHtml(item.status)}">${escapeHtml(item.status)}</span>${stale}` +
    '</header>' +
    `<p class="anth-muted">${escapeHtml(scopeLabel(item.scope))}</p>` +
    renderCardProgress(item) +
    renderCardStats(item) +
    renderCardActions(item) +
    '</article>'
  );
}

/** @param {Array<Record<string, any>>} items @returns {string} */
export function renderList(items) {
  if (!Array.isArray(items) || !items.length) {
    return '<p class="anth-empty">No anthologies yet. Start one from a tag above.</p>';
  }
  return items.map(renderCard).join('');
}

async function handleAction(button, refresh) {
  const id = button.dataset.id;
  const action = button.dataset.action;
  if (!id) {
    return;
  }
  if (action === 'delete' && !window.confirm('Delete this anthology?')) {
    return;
  }
  button.disabled = true;
  try {
    if (action === 'delete') {
      await fetchJson(`/api/anthologies/${encodeURIComponent(id)}`, { method: 'DELETE' });
    } else {
      await postJson(`/api/anthologies/${encodeURIComponent(id)}/retry`, {});
    }
    await refresh();
  } catch (error) {
    console.error('Anthology action failed', error);
    window.alert(error.message);
    button.disabled = false;
  }
}

function bindCreateForm(form, statusNode) {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = buildCreatePayload(Object.fromEntries(new FormData(form).entries()));
    statusNode.textContent = 'Creating…';
    try {
      const data = await postJson('/api/anthologies', payload);
      window.location.href = `/anthologies/${encodeURIComponent(data.anthology_id)}`;
    } catch (error) {
      statusNode.textContent = error.message;
    }
  });
}

export function initSeedSuggestions() {
  const input = document.getElementById('anthology-seed-value');
  const results = document.getElementById('anthology-seed-suggestions');
  if (!input || !results) {
    return;
  }
  let timer = 0;
  let generation = 0;

  const hide = () => {
    generation += 1;
    clearTimeout(timer);
    timer = 0;
    results.hidden = true;
    results.innerHTML = '';
  };

  const fetchSuggestions = (request) => {
    if (!request) {
      hide();
      return;
    }
    const id = generation;
    const form = new FormData();
    form.append('req', request);
    fetch(SEED_SUGGESTIONS_URL, { method: 'POST', credentials: 'include', body: form })
      .then((response) => response.json())
      .then((data) => {
        if (id !== generation || request !== input.value.trim()) {
          return;
        }
        results.innerHTML = renderTagSuggestions(data && data.data);
        results.hidden = !results.innerHTML;
      })
      .catch(() => {
        if (id !== generation || request !== input.value.trim()) {
          return;
        }
        hide();
      });
  };

  input.addEventListener('input', () => {
    clearTimeout(timer);
    if (!input.value.trim()) {
      hide();
      return;
    }
    timer = setTimeout(() => {
      fetchSuggestions(input.value.trim());
    }, SEED_SUGGEST_DEBOUNCE_MS);
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      hide();
    }
  });
  results.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-tag]');
    if (!button) {
      return;
    }
    input.value = button.dataset.tag;
    input.focus();
    hide();
  });
  document.addEventListener('click', (event) => {
    if (!results.contains(event.target) && event.target !== input) {
      hide();
    }
  });
}

export function initAnthologiesList() {
  const listNode = document.getElementById('anthology-list');
  const form = document.getElementById('anthology-create-form');
  const statusNode = document.getElementById('anthology-create-status');
  if (!listNode) {
    return;
  }
  let items = readJsonScript('anthologies-data') || [];
  let timer = null;

  const schedule = () => {
    clearTimeout(timer);
    if (needsPolling(items)) {
      timer = setTimeout(refresh, POLL_MS);
    }
  };
  async function refresh() {
    try {
      items = (await fetchJson(`/api/anthologies${window.location.search}`)) || [];
      listNode.innerHTML = renderList(items);
    } catch (error) {
      console.error('Unable to refresh anthologies', error);
    }
    schedule();
  }

  listNode.innerHTML = renderList(items);
  listNode.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (button) {
      handleAction(button, refresh);
    }
  });
  if (form && statusNode) {
    bindCreateForm(form, statusNode);
  }
  initSeedSuggestions();
  schedule();
}
