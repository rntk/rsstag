'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class TopicsTextsStorage {
  constructor(tag, event_system) {
    this.ES = event_system;
    this._state = {
      tag: tag,
      texts: [],
      topics: [],
    };
    this.urls = {
      get_wordtree_texts: '/topics-texts',
    };
  }

  getState() {
    return Object.assign({}, this._state);
  }

  setState(state) {
    this._state = state;
    this.ES.trigger(this.ES.TOPICS_TEXTS_UPDATED, this.getState());
  }

  fetchWordTreeTexts(tag) {
    rsstag_utils
      .fetchJSON(this.urls.get_wordtree_texts + '/' + encodeURIComponent(tag), {
        method: 'GET',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      .then((data) => {
        if (data.data) {
          let state = this.getState();
          state.texts = data.data.texts;
          state.topics = data.data.topics;
          this.setState(state);
        } else {
          this.errorMessage('Error. Try later', data);
        }
      })
      .catch((err) => {
        this.errorMessage('Error. Try later', err);
      });
  }

  errorMessage(msg, data) {
    console.log(msg, data);
    this.ES.trigger(this.TAGS_ERROR_MESSAGE, msg);
  }

  start() {
    let state = this.getState();
    this.fetchWordTreeTexts(state.tag);
  }
}
