'use strict';

import rsstag_utils from '../libs/rsstag_utils.js';

const FILTER_TYPES = [
  { type: 'tags', label: 'Tags', searchUrl: '/tags-search', field: 'tag' },
  { type: 'feeds', label: 'Feeds', searchUrl: '/api/context-filter/suggestions', field: 'value', itemType: 'feed', requireSuggestion: true },
  { type: 'categories', label: 'Categories', searchUrl: '/api/context-filter/suggestions', field: 'value', itemType: 'category', requireSuggestion: true },
  { type: 'topics', label: 'Topics', searchUrl: '/api/context-filter/suggestions', field: 'value', itemType: 'topic', requireSuggestion: true },
  { type: 'subtopics', label: 'Subtopics', searchUrl: '/api/context-filter/suggestions', field: 'value', itemType: 'subtopic', requireSuggestion: true },
];

const FILTER_TYPE_MAP = FILTER_TYPES.reduce((acc, item) => {
  acc[item.type] = item;
  return acc;
}, {});

function normalizeFilters(filters = {}) {
  const normalized = {};
  FILTER_TYPES.forEach(({ type }) => {
    const values = filters[type];
    normalized[type] = Array.isArray(values)
      ? values.filter((value) => typeof value === 'string' && value.trim())
      : [];
  });
  return normalized;
}

function normalizeState(rawState = {}) {
  const filters = rawState.filters || rawState;
  const normalizedFilters = normalizeFilters(filters);
  const hasFilters = Object.values(normalizedFilters).some((values) => values.length > 0);

  return {
    active: typeof rawState.active === 'boolean' ? rawState.active : hasFilters,
    filters: normalizedFilters,
  };
}

export default class ContextFilterBar {
  constructor(container_id, event_system) {
    this.ES = event_system;
    this.container_id = container_id;
    this._state = normalizeState();
    this._modalState = null;
  }

  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  render() {
    const container = document.getElementById(this.container_id);
    if (!container) return;

    container.style.display = 'flex';

    let html = '<div class="context-filter-bar">';

    if (this._state.active) {
      html += '<span class="context-filter-label">Context:</span>';
      FILTER_TYPES.forEach(({ type, label }) => {
        const values = this._state.filters[type];
        if (!values.length) {
          return;
        }

        html += `<span class="context-filter-group"><span class="context-filter-group-label">${this.escapeHtml(label)}:</span>`;
        values.forEach((value) => {
          const escaped = this.escapeHtml(value);
          html += `
            <span class="context-filter-tag">
              ${escaped}
              <button class="context-filter-remove" data-filter-type="${type}" data-filter-value="${encodeURIComponent(value)}" title="Remove">&times;</button>
            </span>
          `;
        });
        html += '</span>';
      });

      html += '<button class="context-filter-clear" title="Clear all filters">Clear</button>';
    }

    html += '<button class="context-filter-add" title="Add filter to context">+ Add Filter</button>';
    html += '</div>';

    container.innerHTML = html;
    this.bindClickHandlers(container);
  }

  bindClickHandlers(container) {
    container.querySelectorAll('.context-filter-remove').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.ES.trigger(this.ES.CONTEXT_FILTER_REMOVE, {
          type: e.target.dataset.filterType,
          value: decodeURIComponent(e.target.dataset.filterValue || ''),
        });
      });
    });

    const clearBtn = container.querySelector('.context-filter-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.ES.trigger(this.ES.CONTEXT_FILTER_CLEAR);
      });
    }

    const addBtn = container.querySelector('.context-filter-add');
    if (addBtn) {
      addBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.showAddFilterModal();
      });
    }
  }

  showAddFilterModal() {
    document.querySelector('.context-filter-modal')?.remove();

    this._modalState = {
      type: 'tags',
      suggestions: [],
      selectedIndex: -1,
    };

    const modal = document.createElement('div');
    modal.className = 'context-filter-modal';
    modal.innerHTML = `
      <div class="context-filter-modal-content">
        <h3>Add Context Filter</h3>
        <select id="context-filter-type">
          ${FILTER_TYPES.map(
            ({ type, label }) => `<option value="${type}">${this.escapeHtml(label)}</option>`
          ).join('')}
        </select>
        <input type="text" id="context-filter-search" placeholder="Type value..." autocomplete="off" />
        <div id="context-filter-results"></div>
        <button class="context-filter-modal-add">Add</button>
        <button class="context-filter-modal-close">Cancel</button>
      </div>
    `;

    document.body.appendChild(modal);

    const typeSelect = modal.querySelector('#context-filter-type');
    const input = modal.querySelector('#context-filter-search');
    const results = modal.querySelector('#context-filter-results');
    const addBtn = modal.querySelector('.context-filter-modal-add');
    const closeBtn = modal.querySelector('.context-filter-modal-close');

    let searchTimeout;

    const renderTypeHint = () => {
      this._modalState.suggestions = [];
      this._modalState.selectedIndex = -1;
      const typeConfig = FILTER_TYPE_MAP[this._modalState.type];
      input.placeholder = typeConfig.searchUrl
        ? `Search ${typeConfig.label.toLowerCase()}...`
        : `Type ${typeConfig.label.toLowerCase()} value...`;
      this.renderHints(
        results,
        typeConfig.searchUrl
          ? `Start typing to search ${typeConfig.label.toLowerCase()}`
          : `Enter ${typeConfig.label.toLowerCase()} value and click Add`
      );
    };

    typeSelect.addEventListener('change', () => {
      this._modalState.type = typeSelect.value;
      input.value = '';
      renderTypeHint();
    });

    input.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      this._modalState.selectedIndex = -1;
      searchTimeout = setTimeout(
        () => this.searchFilters(this._modalState.type, input.value, results),
        400
      );
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        this.moveSelection(event.key === 'ArrowDown' ? 1 : -1, results);
        return;
      }
      if (event.key === 'Enter') {
        event.preventDefault();
        this.commitSelection(input.value, results);
      }
    });

    addBtn.addEventListener('click', () => this.commitSelection(input.value, results));
    closeBtn.addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    renderTypeHint();
    input.focus();
  }

  async searchFilters(type, query, resultsContainer) {
    const typeConfig = FILTER_TYPE_MAP[type];
    const trimmed = query.trim();

    if (!trimmed) {
      this._modalState.suggestions = [];
      this._modalState.selectedIndex = -1;
      this.renderHints(
        resultsContainer,
        typeConfig.searchUrl
          ? `Start typing to search ${typeConfig.label.toLowerCase()}`
          : `Enter ${typeConfig.label.toLowerCase()} value and click Add`
      );
      return;
    }

    if (!typeConfig.searchUrl) {
      this._modalState.suggestions = [];
      this._modalState.selectedIndex = -1;
      resultsContainer.innerHTML = `<div class="context-tag-hint">Press Enter or click Add to use "${this.escapeHtml(trimmed)}"</div>`;
      return;
    }

    try {
      const form = new FormData();
      form.append('req', trimmed);
      if (typeConfig.itemType) {
        form.append('type', typeConfig.itemType);
      }
      const data = await rsstag_utils.fetchJSON(typeConfig.searchUrl, {
        method: 'POST',
        credentials: 'include',
        body: form,
      });

      const activeValues = this._state.filters[type] || [];
      const suggestions = (data.data || [])
        .map((item) => item[typeConfig.field] || item.name || item.value)
        .filter((value) => typeof value === 'string' && value.trim())
        .filter((value) => !activeValues.includes(value));

      if (!suggestions.length) {
        this._modalState.suggestions = [];
        this._modalState.selectedIndex = -1;
        resultsContainer.innerHTML = '<div class="no-results">No matching values found</div>';
        return;
      }

      this._modalState.suggestions = suggestions.slice(0, 10);
      this._modalState.selectedIndex = -1;
      this.renderSuggestions(resultsContainer);
    } catch (err) {
      console.error('Filter search failed:', err);
      this._modalState.suggestions = [];
      this._modalState.selectedIndex = -1;
      resultsContainer.innerHTML = '<div class="no-results">Search failed</div>';
    }
  }

  renderHints(container, message) {
    container.innerHTML = `<div class="context-tag-hint">${message}</div>`;
  }

  renderSuggestions(container) {
    const suggestions = this._modalState.suggestions;
    container.innerHTML = suggestions
      .map(
        (value, index) => `
          <div class="context-tag-suggestion ${index === this._modalState.selectedIndex ? 'selected' : ''}" data-value="${encodeURIComponent(value)}" data-index="${index}">
            ${this.escapeHtml(value)}
          </div>
        `
      )
      .join('');

    container.querySelectorAll('.context-tag-suggestion').forEach((el) => {
      el.addEventListener('click', (e) => {
        const value = decodeURIComponent(e.currentTarget.dataset.value || "");
        this.ES.trigger(this.ES.CONTEXT_FILTER_ADD, {
          type: this._modalState.type,
          value,
        });
        document.querySelector('.context-filter-modal')?.remove();
      });
    });
  }

  moveSelection(delta, container) {
    const suggestions = this._modalState.suggestions;
    if (!suggestions.length) {
      return;
    }

    const total = suggestions.length;
    const current = this._modalState.selectedIndex;
    const next = current < 0 ? (delta > 0 ? 0 : total - 1) : (current + delta + total) % total;
    this._modalState.selectedIndex = next;

    container.querySelectorAll('.context-tag-suggestion').forEach((el, index) => {
      el.classList.toggle('selected', index === next);
    });
  }

  commitSelection(inputValue) {
    const { selectedIndex, suggestions, type } = this._modalState;
    let value = inputValue.trim();

    if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
      value = suggestions[selectedIndex];
    }

    if (!value) {
      return;
    }

    const typeConfig = FILTER_TYPE_MAP[type] || {};
    if (typeConfig.requireSuggestion && !suggestions.includes(value)) {
      return;
    }

    if ((this._state.filters[type] || []).includes(value)) {
      return;
    }

    this.ES.trigger(this.ES.CONTEXT_FILTER_ADD, { type, value });
    document.querySelector('.context-filter-modal')?.remove();
  }

  update(state) {
    this._state = normalizeState(state);
    this.render();
  }

  bindEvents() {
    this.ES.bind(this.ES.CONTEXT_FILTER_UPDATED, (state) => this.update(state));
  }

  start() {
    this.bindEvents();
    if (window.context_filter_data) {
      this._state = normalizeState(window.context_filter_data);
      this.render();
    }
  }
}
