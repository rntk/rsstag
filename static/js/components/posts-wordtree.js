'use strict';
import WordTree from './wordtree.js';

export default class PostsWordTree {
  /** @param {string} container_id @param {Object} event_system */
  constructor(container_id, event_system) {
    this.ES = event_system;
    this.wordtree = new WordTree(container_id, event_system);
    this.updateWordTree = this.updateWordTree.bind(this);
  }

  /** @param {{group: string, group_title: string, posts: Map<number, Object>}} data @returns {void} */
  updateWordTree(data) {
    if (data.group === 'category' || data.group === 'feed' || !data.posts) return;
    const texts = Array.from(data.posts, ([, post]) => post.post.lemmas);
    this.wordtree.updateWordTree({ tag: data.group_title, texts });
  }

  /** @returns {void} */
  bindEvents() {
    this.ES.bind(this.ES.POSTS_UPDATED, this.updateWordTree);
  }

  /** @returns {void} */
  start() {
    this.bindEvents();
  }
}
