'use strict';

import PathManager from './path-manager.js';

export default class TagTopicsRadar {
  constructor(container_id, event_system, options = {}) {
    this.ES = event_system;
    this._container = document.querySelector(container_id);
    this._chart = null;
    this._items = [];
    this._selectedLevel = null;
    this._options = {
      maxTopics: options.maxTopics || 30,
      defaultLevel: options.defaultLevel || 'deepest',
    };

    this.updateChart = this.updateChart.bind(this);
    this.handleLevelChange = this.handleLevelChange.bind(this);
  }

  splitTopicPath(topicName) {
    if (!topicName || typeof topicName !== 'string') {
      return [];
    }

    return topicName
      .split('>')
      .map((part) => part.trim())
      .filter(Boolean);
  }

  normalizeItems(tags) {
    return Array.from(tags.values())
      .map((item) => {
        const parts = this.splitTopicPath(item.tag);
        return {
          ...item,
          parts,
          depth: parts.length,
          postIds: Array.isArray(item.post_ids) ? item.post_ids.map((value) => String(value)) : [],
        };
      })
      .filter((item) => item.depth > 0);
  }

  getMaxDepth(items) {
    return items.reduce((maxDepth, item) => Math.max(maxDepth, item.depth), 0);
  }

  getDefaultLevel(maxDepth) {
    if (maxDepth <= 0) {
      return 1;
    }

    if (this._options.defaultLevel === 'deepest') {
      return maxDepth;
    }

    return 1;
  }

  getCurrentTag() {
    return window.initial_tag && window.initial_tag.tag ? window.initial_tag.tag : '';
  }

  buildTopicFilter(topic) {
    return {
      mode: 'level',
      level: topic.level,
      value: topic.label,
    };
  }

  buildSnippetsUrl(topic) {
    const params = new URLSearchParams({
      topic_level: String(topic.level),
      topic_value: topic.label,
    });

    return `/post-grouped-snippets/${topic.postIds.join('_')}?${params.toString()}`;
  }

  buildCompareUrl(topic) {
    const params = new URLSearchParams({
      topic_level: String(topic.level),
      topic_value: topic.label,
    });

    return `/post-compare/${topic.postIds.join('_')}?${params.toString()}`;
  }

  aggregateItemsByLevel(items, level) {
    const grouped = new Map();

    items.forEach((item) => {
      if (item.depth < level) {
        return;
      }

      const label = item.parts[level - 1];
      if (!grouped.has(label)) {
        grouped.set(label, {
          label,
          level,
          count: 0,
          totalLength: 0,
          postIds: new Set(),
        });
      }

      const aggregated = grouped.get(label);
      aggregated.count += Number(item.count || 0);
      aggregated.totalLength += Number(item.total_length || 0);
      item.postIds.forEach((postId) => aggregated.postIds.add(postId));
    });

    return Array.from(grouped.values())
      .map((item) => ({
        ...item,
        postIds: Array.from(item.postIds).sort(),
      }))
      .filter((item) => item.postIds.length > 0)
      .sort((left, right) => {
        if (right.count !== left.count) {
          return right.count - left.count;
        }
        return left.label.localeCompare(right.label);
      })
      .slice(0, this._options.maxTopics);
  }

  handleLevelChange(event) {
    const level = Number(event.target.value);
    if (!Number.isFinite(level) || level <= 0 || level === this._selectedLevel) {
      return;
    }

    this._selectedLevel = level;
    this.render();
  }

  updateChart(state) {
    const tags = state.tags;
    if (!tags || tags.size === 0) {
      this.destroyChart();
      this._items = [];
      this._container.innerHTML = '<p>No topics data</p>';
      return;
    }

    this._items = this.normalizeItems(tags);
    const maxDepth = this.getMaxDepth(this._items);
    if (!this._selectedLevel || this._selectedLevel > maxDepth) {
      this._selectedLevel = this.getDefaultLevel(maxDepth);
    }

    this.render();
  }

  destroyChart() {
    if (this._chart) {
      this._chart.destroy();
      this._chart = null;
    }
  }

  async navigateToTopic(topic, event = null) {
    if (event) {
      event.preventDefault();
    }

    const tag = this.getCurrentTag();
    if (window.pathManager && tag && topic && topic.filter) {
      const filterset = PathManager.makeFilterset({ tags: [tag], topics: [topic.filter] });
      await window.pathManager.createAndNavigate('sentences', filterset);
      return;
    }

    if (topic && topic.snippetsUrl) {
      window.location.href = topic.snippetsUrl;
    }
  }

  renderLevelControls(maxDepth) {
    const controls = document.createElement('div');
    controls.className = 'tag-topics-radar-controls';

    const label = document.createElement('span');
    label.className = 'tag-topics-radar-controls-label';
    label.textContent = 'Topic level';
    controls.appendChild(label);

    const group = document.createElement('div');
    group.className = 'tag-topics-radar-level-group';

    for (let level = 1; level <= maxDepth; level += 1) {
      const optionLabel = document.createElement('label');
      optionLabel.className = 'tag-topics-radar-level-option';

      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'tag-topics-radar-level';
      input.value = String(level);
      input.checked = level === this._selectedLevel;
      input.addEventListener('change', this.handleLevelChange);

      const text = document.createElement('span');
      text.textContent = `Level ${level}`;

      optionLabel.appendChild(input);
      optionLabel.appendChild(text);
      group.appendChild(optionLabel);
    }

    controls.appendChild(group);
    return controls;
  }

  renderTopicLinks(items) {
    const list = document.createElement('div');
    list.className = 'tag-topics-radar-links';

    items.forEach((topic) => {
      const link = document.createElement('a');
      link.className = 'tag-topics-radar-link';
      link.href = topic.snippetsUrl;
      link.textContent = topic.label;
      link.title = `Open saved path for level ${topic.level}: ${topic.label}`;
      link.addEventListener('click', (event) => {
        void this.navigateToTopic(topic, event);
      });

      const meta = document.createElement('span');
      meta.className = 'tag-topics-radar-link-meta';
      meta.textContent = `${topic.count} posts · ${topic.totalLength} chars · ${topic.postIds.length} articles`;

      const actions = document.createElement('div');
      actions.className = 'tag-topics-radar-link-actions';

      const snippetsLink = document.createElement('a');
      snippetsLink.className = 'tag-topics-radar-link-action';
      snippetsLink.href = topic.snippetsUrl;
      snippetsLink.textContent = 'Snippets';

      const compareLink = document.createElement('a');
      compareLink.className = 'tag-topics-radar-link-action';
      compareLink.href = topic.compareUrl;
      compareLink.textContent = 'Compare';

      actions.appendChild(snippetsLink);
      actions.appendChild(compareLink);

      const item = document.createElement('div');
      item.className = 'tag-topics-radar-link-item';
      item.appendChild(link);
      item.appendChild(meta);
      item.appendChild(actions);
      list.appendChild(item);
    });

    this._container.appendChild(list);
  }

  renderEmptyState(maxDepth) {
    this.destroyChart();
    this._container.innerHTML = '';
    if (maxDepth > 0) {
      this._container.appendChild(this.renderLevelControls(maxDepth));
    }
    this._container.insertAdjacentHTML(
      'beforeend',
      '<p class="tag-topics-radar-empty">No topics found for this level</p>'
    );
  }

  render() {
    const maxDepth = this.getMaxDepth(this._items);
    if (maxDepth === 0) {
      this.renderEmptyState(0);
      return;
    }

    const topics = this.aggregateItemsByLevel(this._items, this._selectedLevel).map((item) => {
      const topic = {
        ...item,
        filter: this.buildTopicFilter(item),
      };
      return {
        ...topic,
        snippetsUrl: this.buildSnippetsUrl(topic),
        compareUrl: this.buildCompareUrl(topic),
      };
    });

    if (!topics.length) {
      this.renderEmptyState(maxDepth);
      return;
    }

    const labels = topics.map((topic) => topic.label);
    const counts = topics.map((topic) => topic.count);
    const lengths = topics.map((topic) => topic.totalLength);

    this.renderChart(maxDepth, labels, counts, lengths, topics);
  }

  renderChart(maxDepth, labels, counts, lengths, topics) {
    this.destroyChart();
    this._container.innerHTML = '';
    this._container.appendChild(this.renderLevelControls(maxDepth));

    const wrapper = document.createElement('div');
    wrapper.className = 'tag-topics-radar-chart-wrapper';

    const canvas = document.createElement('canvas');
    wrapper.appendChild(canvas);
    this._container.appendChild(wrapper);
    this.renderTopicLinks(topics);

    const maxCount = Math.max(...counts, 1);
    const maxLength = Math.max(...lengths, 1);
    const normalizedLengths = lengths.map((value) => (value / maxLength) * maxCount);

    this._chart = new Chart(canvas.getContext('2d'), {
      type: 'radar',
      data: {
        labels,
        datasets: [
          {
            label: 'Frequency (posts)',
            data: counts,
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 2,
            pointBackgroundColor: 'rgba(54, 162, 235, 1)',
            pointHoverRadius: 6,
          },
          {
            label: 'Content volume (normalized)',
            data: normalizedLengths,
            backgroundColor: 'rgba(255, 99, 132, 0.2)',
            borderColor: 'rgba(255, 99, 132, 1)',
            borderWidth: 2,
            pointBackgroundColor: 'rgba(255, 99, 132, 1)',
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        scale: {
          ticks: {
            beginAtZero: true,
            display: false,
          },
          pointLabels: {
            fontSize: 13,
          },
        },
        legend: {
          position: 'top',
        },
        onClick: (event, elements) => {
          if (!elements || !elements.length) {
            return;
          }
          const index = elements[0]._index;
          void this.navigateToTopic(topics[index]);
        },
        tooltips: {
          callbacks: {
            title: (items) => labels[items[0].index],
            label: (item) => {
              const index = item.index;
              if (item.datasetIndex === 0) {
                return `posts: ${counts[index]}`;
              }
              return `content length: ${lengths[index]} chars`;
            },
          },
        },
      },
    });
  }

  bindEvents() {
    this.ES.bind(this.ES.TAGS_UPDATED, this.updateChart);
  }

  start() {
    this.bindEvents();
  }
}
