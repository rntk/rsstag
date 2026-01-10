'use strict';

import rsstag_utils from '../libs/rsstag_utils.js';

export default class ContextFilterBar {
  constructor(container_id, event_system) {
    this.ES = event_system;
    this.container_id = container_id;
    this._state = { active: false, tags: [] };
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

    // Always show the bar with at least the "+ Add" button
    container.style.display = 'flex';

    let html = '<div class="context-filter-bar">';
    
    if (this._state.active && this._state.tags.length > 0) {
      html += '<span class="context-filter-label">Context:</span>';

      for (const tag of this._state.tags) {
        const escaped = this.escapeHtml(tag);
        html += `
          <span class="context-filter-tag">
            ${escaped}
            <button class="context-filter-remove" data-tag="${escaped}" title="Remove">&times;</button>
          </span>
        `;
      }

      html += '<button class="context-filter-clear" title="Clear all filters">Clear</button>';
    }
    
    html += '<button class="context-filter-add" title="Add tag to context">+ Add Tag</button>';
    html += '</div>';

    container.innerHTML = html;
    this.bindClickHandlers(container);
  }

  bindClickHandlers(container) {
    // Remove tag buttons
    container.querySelectorAll('.context-filter-remove').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const tag = e.target.dataset.tag;
        this.ES.trigger(this.ES.CONTEXT_FILTER_REMOVE_TAG, tag);
      });
    });

    // Clear all button
    const clearBtn = container.querySelector('.context-filter-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.ES.trigger(this.ES.CONTEXT_FILTER_CLEAR);
      });
    }

    // Add tag button
    const addBtn = container.querySelector('.context-filter-add');
    if (addBtn) {
      addBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.showAddTagModal();
      });
    }
  }

  showAddTagModal() {
    // Remove existing modal if any
    const existing = document.querySelector('.context-filter-modal');
    if (existing) existing.remove();

    this._modalState = {
      suggestions: [],
      selectedIndex: -1,
    };

    const modal = document.createElement('div');
    modal.className = 'context-filter-modal';
    modal.innerHTML = `
      <div class="context-filter-modal-content">
        <h3>Add Context Tag</h3>
        <input type="text" id="context-tag-search" placeholder="Type to search tags..." autocomplete="off" />
        <div id="context-tag-results"></div>
        <button class="context-filter-modal-close">Cancel</button>
      </div>
    `;
    document.body.appendChild(modal);

    const input = modal.querySelector('#context-tag-search');
    const results = modal.querySelector('#context-tag-results');
    const closeBtn = modal.querySelector('.context-filter-modal-close');

    let searchTimeout;
    input.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      this._modalState.selectedIndex = -1;
      searchTimeout = setTimeout(() => this.searchTags(input.value, results), 800);
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

    closeBtn.addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    this.renderHints(results, 'Start typing to search tags');
    input.focus();
  }

  async searchTags(query, resultsContainer) {
    const trimmed = query.trim();
    if (!trimmed) {
      this._modalState.suggestions = [];
      this._modalState.selectedIndex = -1;
      this.renderHints(resultsContainer, 'Start typing to search tags');
      return;
    }
    try {
      const form = new FormData();
      form.append('req', trimmed);
      const data = await rsstag_utils.fetchJSON('/tags-search', {
        method: 'POST',
        credentials: 'include',
        body: form,
      });

      if (data.data && data.data.length > 0) {
        // Filter out tags already in context
        const filtered = data.data.filter(t => !this._state.tags.includes(t.tag));

        if (filtered.length === 0) {
          this._modalState.suggestions = [];
          this._modalState.selectedIndex = -1;
          resultsContainer.innerHTML = '<div class="no-results">All matching tags already in context</div>';
          return;
        }

        this._modalState.suggestions = filtered.slice(0, 10);
        this._modalState.selectedIndex = -1;
        this.renderSuggestions(resultsContainer);
      } else {
        this._modalState.suggestions = [];
        this._modalState.selectedIndex = -1;
        resultsContainer.innerHTML = '<div class="no-results">No tags found</div>';
      }
    } catch (err) {
      console.error('Tag search failed:', err);
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
    container.innerHTML = suggestions.map((tag, index) => `
      <div class="context-tag-result${index === this._modalState.selectedIndex ? ' is-active' : ''}" data-index="${index}">
        <span class="context-tag-label">${this.escapeHtml(tag.tag)}</span>
        <span class="tag-counts">(${tag.unread}/${tag.all})</span>
      </div>
    `).join('');

    container.querySelectorAll('.context-tag-result').forEach(el => {
      el.addEventListener('click', () => {
        const index = Number(el.dataset.index);
        const suggestion = this._modalState.suggestions[index];
        if (!suggestion) {
          return;
        }
        this.ES.trigger(this.ES.CONTEXT_FILTER_ADD_TAG, suggestion.tag);
        document.querySelector('.context-filter-modal')?.remove();
      });
    });
  }

  moveSelection(direction, resultsContainer) {
    const total = this._modalState.suggestions.length;
    if (total === 0) {
      return;
    }
    let nextIndex = this._modalState.selectedIndex + direction;
    if (nextIndex < 0) {
      nextIndex = total - 1;
    } else if (nextIndex >= total) {
      nextIndex = 0;
    }
    this._modalState.selectedIndex = nextIndex;
    this.renderSuggestions(resultsContainer);
  }

  async commitSelection(rawQuery, resultsContainer) {
    let suggestions = this._modalState.suggestions;
    if (suggestions.length === 0) {
      const trimmed = rawQuery.trim();
      if (!trimmed) {
        return;
      }
      await this.searchTags(trimmed, resultsContainer);
      suggestions = this._modalState.suggestions;
      if (suggestions.length === 0) {
        return;
      }
    }
    const trimmed = rawQuery.trim();
    let selectedIndex = this._modalState.selectedIndex;
    if (selectedIndex < 0 && trimmed) {
      selectedIndex = suggestions.findIndex(
        (tag) => tag.tag.toLowerCase() === trimmed.toLowerCase()
      );
    }
    if (selectedIndex < 0 && suggestions.length === 1) {
      selectedIndex = 0;
    }
    if (selectedIndex >= 0) {
      this.ES.trigger(this.ES.CONTEXT_FILTER_ADD_TAG, suggestions[selectedIndex].tag);
      document.querySelector('.context-filter-modal')?.remove();
    }
  }

  update(state) {
    this._state = state;
    this.render();
  }

  bindEvents() {
    this.ES.bind(this.ES.CONTEXT_FILTER_UPDATED, (state) => this.update(state));
  }

  start() {
    this.bindEvents();
    // Initial render with any server-provided state
    if (window.context_filter_data) {
      // Extract tags from the filter data structure
      const filterData = window.context_filter_data.tags || window.context_filter_data;
      const tags = Array.isArray(filterData) ? filterData : (filterData.tags || []);
      this._state = { active: tags.length > 0, tags };
      this.render();
    }
  }
}
