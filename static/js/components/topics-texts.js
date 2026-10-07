'use strict';
import WordTree from './wordtree.js';

export default class TopicsTexts {
  /** @param {string} container_id @param {Object} event_system */
  constructor(container_id, event_system) {
    this.ES = event_system;
    this._container = document.querySelector(container_id);
    this.updateData = this.updateData.bind(this);
  }

  /** @param {{topics: string[], texts: string[]}} data @returns {void} */
  updateData(data) {
    if (!this._container) return;
    this._container.replaceChildren();
    for (const topic of data.topics) {
      this.renderWordtree(topic, data.texts);
    }
  }

  /** @param {string} topic @param {string[]} topic_texts @returns {void} */
  renderWordtree(topic, topic_texts) {
    if (!this._container) return;
    const container = document.createElement('div');
    this._container.appendChild(container);
    const tree = new WordTree(container, this.ES);
    tree.updateWordTree({ tag: topic, texts: topic_texts });
  }

  /** @returns {void} */
  bindEvents() {
    this.ES.bind(this.ES.TOPICS_TEXTS_UPDATED, this.updateData);
  }

  /** @returns {void} */
  start() {
    this.bindEvents();
  }
}
