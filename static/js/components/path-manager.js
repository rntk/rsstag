'use strict';

export default class PathManager {
  constructor(pathStorage) {
    this.storage = pathStorage;
  }

  async createAndNavigate(contentType, filterset, exclude = {}) {
    const result = await this.storage.createPath(contentType, filterset, exclude);
    if (result && result.path_id) {
      window.location.href = `/paths/${contentType}/${result.path_id}`;
    }
    return result;
  }

  static makeFilterset({ tags, topics, feeds, categories } = {}) {
    const fs = {};
    if (tags && tags.length) fs.tags = { values: tags, logic: 'and' };
    if (topics && topics.length) fs.topics = { values: topics, logic: 'and' };
    if (feeds && feeds.length) fs.feeds = { values: feeds, logic: 'or' };
    if (categories && categories.length) fs.categories = { values: categories, logic: 'or' };
    return fs;
  }

  async loadRecommendations(pathId, container) {
    if (!pathId || !container) {
      return null;
    }

    this.renderRecommendationsState(container, 'loading');
    const payload = await this.storage.getPathRecommendations(pathId);
    if (!payload) {
      this.renderRecommendationsState(container, 'error');
      return null;
    }

    const groups = Array.isArray(payload.groups) ? payload.groups : [];
    if (!groups.length) {
      this.renderRecommendationsState(container, 'empty');
      return payload;
    }

    this.renderRecommendations(container, groups);
    return payload;
  }

  renderRecommendationsState(container, state) {
    container.innerHTML = '';
    const title = document.createElement('h3');
    title.className = 'path-recommendations-title';
    title.textContent = 'Suggested paths';
    container.appendChild(title);

    const message = document.createElement('div');
    message.className = `path-recommendations-state path-recommendations-state-${state}`;
    if (state === 'loading') {
      message.textContent = 'Loading suggestions...';
    } else if (state === 'empty') {
      message.textContent = 'No suggestions for this path yet.';
    } else {
      message.textContent = 'Failed to load suggestions.';
    }
    container.appendChild(message);
  }

  renderRecommendations(container, groups) {
    container.innerHTML = '';

    const title = document.createElement('h3');
    title.className = 'path-recommendations-title';
    title.textContent = 'Suggested paths';
    container.appendChild(title);

    groups.forEach((group) => {
      const items = Array.isArray(group.items) ? group.items : [];
      if (!items.length) {
        return;
      }

      const section = document.createElement('section');
      section.className = 'path-recommendations-group';

      const heading = document.createElement('h4');
      heading.className = 'path-recommendations-group-title';
      heading.textContent = group.title || 'Suggestions';
      section.appendChild(heading);

      const list = document.createElement('div');
      list.className = 'path-recommendations-list';

      items.forEach((item) => {
        list.appendChild(this.createRecommendationItem(item));
      });

      section.appendChild(list);
      container.appendChild(section);
    });
  }

  createRecommendationItem(item) {
    const action = document.createElement('button');
    action.type = 'button';
    action.className = 'path-recommendation-item';
    action.addEventListener('click', async () => {
      action.disabled = true;
      const result = await this.createAndNavigate(
        item.content_type,
        item.filterset,
        item.exclude || {}
      );
      if (!result || !result.path_id) {
        action.disabled = false;
      }
    });

    const title = document.createElement('span');
    title.className = 'path-recommendation-item-title';
    title.textContent = item.title || 'Suggested path';
    action.appendChild(title);

    const meta = document.createElement('span');
    meta.className = 'path-recommendation-item-meta';
    meta.textContent = this.formatRecommendationMeta(item);
    action.appendChild(meta);

    return action;
  }

  formatRecommendationMeta(item) {
    const parts = [];
    const countLabel = this.formatRecommendationCounts(item);
    const source = this.formatFilterValue(item.source_value);
    const suggested = this.formatFilterValue(item.suggested_value);

    if (countLabel) {
      parts.push(countLabel);
    }

    if (source && suggested) {
      parts.push(`${source} -> ${suggested}`);
    }

    if (typeof item.score === 'number') {
      parts.push(`score ${item.score.toFixed(2)}`);
    }

    return parts.join(' · ');
  }

  formatRecommendationCounts(item) {
    const postsCount = Number.isInteger(item.posts_count) ? item.posts_count : null;
    const sentencesCount = Number.isInteger(item.sentences_count) ? item.sentences_count : null;
    const parts = [];

    if (item.content_type === 'sentences') {
      if (sentencesCount !== null) {
        parts.push(`${sentencesCount} sentences`);
      }
      if (postsCount !== null) {
        parts.push(`${postsCount} posts`);
      }
    } else {
      if (postsCount !== null) {
        parts.push(`${postsCount} posts`);
      }
      if (sentencesCount !== null && sentencesCount > 0) {
        parts.push(`${sentencesCount} sentences`);
      }
    }

    return parts.join(' · ');
  }

  async loadClusterRecommendations(pathId, container) {
    if (!pathId || !container) {
      return null;
    }

    this._renderClusterState(container, 'loading');
    const payload = await this.storage.getPathClusterRecommendations(pathId);
    if (!payload) {
      this._renderClusterState(container, 'error');
      return null;
    }

    const clusters = Array.isArray(payload.clusters) ? payload.clusters : [];
    if (!clusters.length) {
      this._renderClusterState(container, 'empty');
      return payload;
    }

    this._renderClusters(container, clusters);
    return payload;
  }

  _renderClusterState(container, state) {
    container.innerHTML = '';
    const title = document.createElement('h3');
    title.className = 'path-recommendations-title';
    title.textContent = 'Related clusters';
    container.appendChild(title);

    const message = document.createElement('div');
    message.className = `path-recommendations-state path-recommendations-state-${state}`;
    if (state === 'loading') {
      message.textContent = 'Loading clusters...';
    } else if (state === 'empty') {
      message.textContent = 'No related clusters found.';
    } else {
      message.textContent = 'Failed to load clusters.';
    }
    container.appendChild(message);
  }

  _renderClusters(container, clusters) {
    container.innerHTML = '';
    const title = document.createElement('h3');
    title.className = 'path-recommendations-title';
    title.textContent = 'Related clusters';
    container.appendChild(title);

    const list = document.createElement('div');
    list.className = 'path-recommendations-list';

    clusters.forEach((cluster) => {
      const link = document.createElement('a');
      link.href = cluster.link;
      link.className = 'path-cluster-recommendation-item';

      const titleEl = document.createElement('span');
      titleEl.className = 'path-recommendation-item-title';
      titleEl.textContent = cluster.title;
      link.appendChild(titleEl);

      const meta = document.createElement('span');
      meta.className = 'path-recommendation-item-meta';
      meta.textContent = `${cluster.overlap_count} shared posts, ${cluster.item_count} total snippets`;
      link.appendChild(meta);

      list.appendChild(link);
    });

    container.appendChild(list);
  }

  formatFilterValue(value) {
    if (typeof value === 'string') {
      return value;
    }

    if (value && typeof value === 'object' && value.mode === 'level') {
      return `level ${value.level}: ${value.value}`;
    }

    return '';
  }
}
