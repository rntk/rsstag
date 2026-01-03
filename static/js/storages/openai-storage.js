'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class OpenAIStorage {
  constructor(current_tag, event_system) {
    this.ES = event_system;
    this._state = {
      user: '',
      response: '',
      tag: current_tag,
    };
  }

  getState() {
    return Object.assign({}, this._state);
  }

  setState(state) {
    this._state = state;
    this.ES.trigger(this.ES.OPENAI_GOT_RESPONSE, this.getState());
  }

  bindEvents() {
    this.ES.bind(this.ES.OPENAI_GET_RESPONSE, this.getResponse.bind(this));
  }

  getResponse(data) {
    const state = this.getState();
    state.user = data.user;
    state.response = 'LOADING...';
    this.setState(state);
    const req_data = {
      user: data.user,
      tag: state.tag,
    };
    rsstag_utils
      .fetchJSON('/openai', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req_data),
      })
      .then((data) => {
        let state = this.getState();
        if (data.data) {
          state.response = data.data;
        } else {
          state.response = data.error;
          this.errorMessage('Error. Try later');
        }
        this.setState(state);
      })
      .catch((err) => {
        this.errorMessage('Error. Try later');
      });
  }

  errorMessage(msg) {
    console.log(msg);
  }

  start() {
    this.bindEvents();
  }
}
