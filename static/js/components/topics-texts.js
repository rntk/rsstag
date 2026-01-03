'use strict';

export default class TopicsTexts {
  constructor(container_id, event_system) {
    this.ES = event_system;
    this._container = document.querySelector(container_id);

    this.updateData = this.updateData.bind(this);
  }

  updateData(data) {
    const window = 5;
    for (let topic of data.topics) {
      let texts = [];
      for (let txt of data.texts) {
        let words = txt.split(' ');
        for (let i = 0; i < words.length; i++) {
          let word = words[i];
          if (word === topic) {
            let st_pos = Math.max(i - window, 0);
            let end_pos = i + window;
            if (end_pos > words.length) {
              end_pos = words.length;
            }
            texts.push(words.slice(st_pos, end_pos).join(' '));
          }
        }
      }
      this.renderWordtree(topic, texts);
    }
  }

  renderWordtree(topic, topic_texts) {
    let div = document.createElement('div');
    this._container.appendChild(div);
    google.charts.load('current', { packages: ['wordtree'] });
    google.charts.setOnLoadCallback(() => {
      let texts = [];
      for (let txt of topic_texts) {
        texts.push([txt]);
      }
      let dt = google.visualization.arrayToDataTable(texts);
      let chart = new google.visualization.WordTree(div);
      let options = {
        wordtree: {
          format: 'implicit',
          word: topic,
          type: 'double',
          backgroundColor: '#d7d7af',
        },
      };
      chart.draw(dt, options);
    });
  }

  bindEvents() {
    this.ES.bind(this.ES.TOPICS_TEXTS_UPDATED, this.updateData);
  }

  start() {
    this.bindEvents();
  }
}
