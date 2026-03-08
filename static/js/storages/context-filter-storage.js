'use strict';

const FILTER_TYPES = ['tags', 'feeds', 'categories', 'topics', 'subtopics'];
const FILTER_TYPE_TO_ITEM_TYPE = {
  tags: 'tag',
  feeds: 'feed',
  categories: 'category',
  topics: 'topic',
  subtopics: 'subtopic',
};

function normalizeFilters(filters = {}) {
  const normalized = {};
  FILTER_TYPES.forEach((type) => {
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

function extractState(responseData = {}) {
  if (responseData.state) {
    return responseData.state;
  }
  if (responseData.data && typeof responseData.data === 'object') {
    return responseData.data;
  }
  return {
    active: responseData.active,
    filters: responseData.filters,
    tags: responseData.tags,
    feeds: responseData.feeds,
    categories: responseData.categories,
    topics: responseData.topics,
    subtopics: responseData.subtopics,
  };
}

export default class ContextFilterStorage {
  constructor(event_system) {
    this.ES = event_system;
    this._state = normalizeState();
    this.urls = {
      get: '/api/context-filter',
      add: '/api/context-filter/item',
      remove: '/api/context-filter/item',
      clear: '/api/context-filter/clear',
    };
  }

  getState() {
    return {
      ...this._state,
      filters: { ...this._state.filters },
    };
  }

  setState(state) {
    this._state = normalizeState(state);
    this.ES.trigger(this.ES.CONTEXT_FILTER_UPDATED, this.getState());
  }

  async fetchFilter() {
    try {
      const response = await fetch(this.urls.get, {
        credentials: 'include',
      });
      const data = await response.json();
      if (data.data) {
        this.setState(extractState(data));
      }
    } catch (err) {
      console.error('Failed to fetch context filter:', err);
    }
  }

  async addFilter(filter) {
    const itemType = FILTER_TYPE_TO_ITEM_TYPE[filter?.type];
    const payload = {
      type: itemType,
      value: filter?.value,
    };

    if (!payload.type || !payload.value) {
      return;
    }

    try {
      const response = await fetch(this.urls.add, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to add filter:', data.error);
        return;
      }
      if (data.data === 'ok') {
        this.setState(extractState(data));
        window.location.reload();
      }
    } catch (err) {
      console.error('Failed to add context filter:', err);
    }
  }

  async removeFilter(filter) {
    const itemType = FILTER_TYPE_TO_ITEM_TYPE[filter?.type];
    const payload = {
      type: itemType,
      value: filter?.value,
    };

    if (!payload.type || !payload.value) {
      return;
    }

    try {
      const response = await fetch(this.urls.remove, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to remove filter:', data.error);
        return;
      }
      if (data.data === 'ok') {
        this.setState(extractState(data));
        window.location.reload();
      }
    } catch (err) {
      console.error('Failed to remove context filter:', err);
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
        this.setState(data);
        window.location.reload();
      }
    } catch (err) {
      console.error('Failed to clear context filter:', err);
    }
  }

  bindEvents() {
    this.ES.bind(this.ES.CONTEXT_FILTER_ADD, (filter) => this.addFilter(filter));
    this.ES.bind(this.ES.CONTEXT_FILTER_REMOVE, (filter) => this.removeFilter(filter));
    this.ES.bind(this.ES.CONTEXT_FILTER_CLEAR, () => this.clearFilter());
  }

  start() {
    this.bindEvents();
    this.fetchFilter();
  }
}
