'use strict';

export default class TagMentionsChart {
  constructor(container_id, event_system) {
    this.ES = event_system;
    this._container = document.querySelector(container_id);

    this.updateMentions = this.updateMentions.bind(this);
  }

  updateMentions(data) {
    if (!data.dates.length) {
      this.hideChart();
      return;
    }
    let mp = {};
    let current = 0;
    let aggr = 3600 * 24 * 1000;
    let k = '';
    let tag = data.tag;
    let dates = data.dates.slice();
    dates.sort();
    for (let u of dates) {
      u *= 1000;
      let d = new Date();
      if (current === 0 || current + aggr < u) {
        d.setTime(u);
        d.setMinutes(0);
        d.setMilliseconds(0);
        d.setSeconds(0);
        current = d.getTime();
        k = `${d.getFullYear()}-${this.prettyDate(d.getMonth())}-${this.prettyDate(d.getDate())}`;
      }
      if (!(k in mp)) {
        mp[k] = 0;
      }
      mp[k]++;
    }
    let labels = [];
    let values = [];
    for (let k in mp) {
      labels.push(k);
      values.push(mp[k]);
    }
    this.renderChart(tag, labels, values);
  }

  prettyDate(n) {
    if (n === 0) {
      n = 1;
    }
    let zero = '';
    if (n < 10) {
      zero = '0';
    }

    return zero + n;
  }

  renderChart(tag, labels, values) {
    let dtset = {
      labels: labels,
      datasets: [
        {
          label: tag,
          data: values,
        },
      ],
    };
    this._container.innerHTML = '';
    let ctx = document.createElement('canvas');
    this._container.appendChild(ctx);
    let ch = new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: dtset,
    });
  }

  hideChart() {
    this._container.innerHTML = '<p>No mentions</p>';
  }

  bindEvents() {
    this.ES.bind(this.ES.TAG_MENTIONS_UPDATED, this.updateMentions);
  }

  start() {
    this.bindEvents();
  }
}
