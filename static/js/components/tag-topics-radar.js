'use strict';

import PathManager from './path-manager.js';

export default class TagTopicsRadar {
  constructor(container_id, event_system) {
    this.ES = event_system;
    this._container = document.querySelector(container_id);
    this._chart = null;

    this.updateChart = this.updateChart.bind(this);
    this.navigateToTopic = this.navigateToTopic.bind(this);
  }

  updateChart(state) {
    const tags = state.tags;
    if (!tags || tags.size === 0) {
      this._container.innerHTML = '<p>No topics data</p>';
      return;
    }

    const items = Array.from(tags.values());
    items.sort((a, b) => b.count - a.count);
    const top = items.slice(0, 15);

    const labels = top.map((t) => t.tag);
    const counts = top.map((t) => t.count);
    const lengths = top.map((t) => t.total_length || 0);
    const urls = top.map((t) => t.url || null);

    this.renderChart(labels, counts, lengths, urls);
  }

  getCurrentTag() {
    return window.initial_tag && window.initial_tag.tag ? window.initial_tag.tag : '';
  }

  async navigateToTopic(topic, url, event = null) {
    if (event) {
      event.preventDefault();
    }

    const tag = this.getCurrentTag();
    if (window.pathManager && tag) {
      const filterset = PathManager.makeFilterset({ tags: [tag], topics: [topic] });
      await window.pathManager.createAndNavigate('sentences', filterset);
      return;
    }

    if (url) {
      window.location.href = url;
    }
  }

  renderTopicLinks(labels, counts, lengths, urls) {
    const tag = this.getCurrentTag();
    const list = document.createElement('div');
    list.className = 'tag-topics-radar-links';

    labels.forEach((topic, index) => {
      const link = document.createElement('a');
      link.className = 'tag-topics-radar-link';
      link.href = urls[index] || '#';
      link.textContent = topic;
      link.title = tag ? `Open path for ${tag} + ${topic}` : topic;
      link.addEventListener('click', (event) => {
        void this.navigateToTopic(topic, urls[index], event);
      });

      const meta = document.createElement('span');
      meta.className = 'tag-topics-radar-link-meta';
      meta.textContent = `${counts[index]} posts · ${lengths[index]} chars`;

      const item = document.createElement('div');
      item.className = 'tag-topics-radar-link-item';
      item.appendChild(link);
      item.appendChild(meta);
      list.appendChild(item);
    });

    this._container.appendChild(list);
  }

  renderChart(labels, counts, lengths, urls) {
    if (this._chart) {
      this._chart.destroy();
      this._chart = null;
    }
    this._container.innerHTML = '';

    const wrapper = document.createElement('div');
    wrapper.style.cssText =
      'position:relative;width:100%;max-width:900px;height:700px;margin:0 auto;';

    const canvas = document.createElement('canvas');
    wrapper.appendChild(canvas);
    this._container.appendChild(wrapper);
    this.renderTopicLinks(labels, counts, lengths, urls);

    // Normalize lengths to the same scale as counts for visual comparison
    const maxCount = Math.max(...counts, 1);
    const maxLength = Math.max(...lengths, 1);
    const normalizedLengths = lengths.map((l) => (l / maxLength) * maxCount);

    this._chart = new Chart(canvas.getContext('2d'), {
      type: 'radar',
      data: {
        labels: labels,
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
        onClick: (evt, elements) => {
          if (!elements || !elements.length) return;
          const idx = elements[0]._index;
          const topic = labels[idx];
          void this.navigateToTopic(topic, urls[idx]);
        },
        tooltips: {
          callbacks: {
            title: (items) => labels[items[0].index],
            label: (item) => {
              const idx = item.index;
              if (item.datasetIndex === 0) {
                return 'posts: ' + counts[idx];
              } else {
                return 'content length: ' + lengths[idx] + ' chars';
              }
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
