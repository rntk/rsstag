'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class WordTreeStorage {
  constructor(tag, event_system) {
    this.ES = event_system;
    this._state = {
      tag: tag,
      texts: [],
    };
    this.urls = {
      get_wordtree_texts: '/wordtree-texts',
    };
    this.changeState = this.changeState.bind(this);
  }

  getState() {
    return Object.assign({}, this._state);
  }

  changeState(event_data) {
    if (event_data.hide_list) {
      let state = this.getState();
      state.texts = [];
      this.setState(state);
      return;
    }
    this.fetchWordTreeTexts(event_data.tag);
  }

  setState(state) {
    this._state = state;
    this.ES.trigger(this.ES.WORDTREE_TEXTS_UPDATED, this.getState());
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
          state.texts = data.data;
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

  bindEvents() {
    this.ES.bind(this.ES.CHANGE_TAGS_LOAD_BUTTON_STATE, this.changeState);
  }

  start() {
    this.bindEvents();
  }
}
