'use strict';

export default class PathStorage {
  constructor(ES) {
    this.ES = ES;
  }

  start() {
    // No automatic fetching needed; callers invoke methods directly
  }

  async createPath(contentType, filterset, exclude = {}) {
    try {
      const response = await fetch('/api/paths', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_type: contentType, filterset, exclude }),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to create path:', data.error);
        return null;
      }
      const doc = data.data;
      this.ES.trigger(this.ES.PATH_CREATED, doc);
      return doc;
    } catch (err) {
      console.error('Failed to create path:', err);
      return null;
    }
  }

  async listPaths() {
    try {
      const response = await fetch('/api/paths', { credentials: 'include' });
      const data = await response.json();
      const paths = data.data || [];
      this.ES.trigger(this.ES.PATHS_UPDATED, paths);
      return paths;
    } catch (err) {
      console.error('Failed to list paths:', err);
      return [];
    }
  }

  async deletePath(pathId) {
    try {
      const response = await fetch(`/api/paths/${pathId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to delete path:', data.error);
        return false;
      }
      this.ES.trigger(this.ES.PATH_DELETED, pathId);
      return true;
    } catch (err) {
      console.error('Failed to delete path:', err);
      return false;
    }
  }
}
