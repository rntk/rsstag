'use strict';

export default class ContextFilterBar {
  constructor(container_id, event_system) {
    this.ES = event_system;
    this.container_id = container_id;
    this._state = { active: false, tags: [] };
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
      searchTimeout = setTimeout(() => this.searchTags(input.value, results), 300);
    });

    closeBtn.addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    input.focus();
  }

  async searchTags(query, resultsContainer) {
    if (query.length < 2) {
      resultsContainer.innerHTML = '<div class="context-tag-hint">Type at least 2 characters</div>';
      return;
    }

    try {
      // Uses existing /tags-search endpoint
      const response = await fetch('/tags-search', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `req=${encodeURIComponent(query)}`,
      });
      const data = await response.json();

      if (data.data && data.data.length > 0) {
        // Filter out tags already in context
        const filtered = data.data.filter(t => !this._state.tags.includes(t.tag));

        if (filtered.length === 0) {
          resultsContainer.innerHTML = '<div class="no-results">All matching tags already in context</div>';
          return;
        }

        resultsContainer.innerHTML = filtered.slice(0, 10).map(tag => `
          <div class="context-tag-result" data-tag="${this.escapeHtml(tag.tag)}">
            ${this.escapeHtml(tag.tag)}
            <span class="tag-counts">(${tag.unread}/${tag.all})</span>
          </div>
        `).join('');

        resultsContainer.querySelectorAll('.context-tag-result').forEach(el => {
          el.addEventListener('click', () => {
            const tag = el.dataset.tag;
            this.ES.trigger(this.ES.CONTEXT_FILTER_ADD_TAG, tag);
            document.querySelector('.context-filter-modal')?.remove();
          });
        });
      } else {
        resultsContainer.innerHTML = '<div class="no-results">No tags found</div>';
      }
    } catch (err) {
      console.error('Tag search failed:', err);
      resultsContainer.innerHTML = '<div class="no-results">Search failed</div>';
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
