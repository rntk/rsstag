'use strict';

export default class ContextFilterStorage {
  constructor(event_system) {
    this.ES = event_system;
    this._state = {
      active: false,
      tags: [],
    };
    this.urls = {
      get: '/api/context-filter',
      addTag: '/api/context-filter/tag',
      removeTag: '/api/context-filter/tag',
      clear: '/api/context-filter/clear',
    };
  }

  getState() {
    return { ...this._state };
  }

  setState(state) {
    this._state = state;
    this.ES.trigger(this.ES.CONTEXT_FILTER_UPDATED, this.getState());
  }

  async fetchFilter() {
    try {
      const response = await fetch(this.urls.get, {
        credentials: 'include',
      });
      const data = await response.json();
      if (data.data) {
        this.setState({
          active: data.data.active,
          tags: data.data.tags || [],
        });
      }
    } catch (err) {
      console.error('Failed to fetch context filter:', err);
    }
  }

  async addTag(tag) {
    try {
      const response = await fetch(this.urls.addTag, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag }),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to add tag:', data.error);
        return;
      }
      if (data.data === 'ok') {
        this.setState({
          active: data.tags.length > 0,
          tags: data.tags,
        });
        // Reload page to show filtered results
        window.location.reload();
      }
    } catch (err) {
      console.error('Failed to add context tag:', err);
    }
  }

  async removeTag(tag) {
    try {
      const response = await fetch(this.urls.removeTag, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag }),
      });
      const data = await response.json();
      if (data.data === 'ok') {
        this.setState({
          active: data.tags.length > 0,
          tags: data.tags,
        });
        // Reload page to show unfiltered results
        window.location.reload();
      }
    } catch (err) {
      console.error('Failed to remove context tag:', err);
    }
  }

  async clearFilter() {
    try {
      const response = await fetch(this.urls.clear, {
        method: 'POST',
        credentials: 'include',
      });
      const data = await response.json();
      if (data.data === 'ok') {
        this.setState({ active: false, tags: [] });
        window.location.reload();
      }
    } catch (err) {
      console.error('Failed to clear context filter:', err);
    }
  }

  bindEvents() {
    this.ES.bind(this.ES.CONTEXT_FILTER_ADD_TAG, (tag) => this.addTag(tag));
    this.ES.bind(this.ES.CONTEXT_FILTER_REMOVE_TAG, (tag) => this.removeTag(tag));
    this.ES.bind(this.ES.CONTEXT_FILTER_CLEAR, () => this.clearFilter());
  }

  start() {
    this.bindEvents();
    this.fetchFilter();
  }
}
