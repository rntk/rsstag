'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class ProgressBarStorage {
  constructor(event_system) {
    this.ES = event_system;
    this._state = {
      tasks: [],
      progress: 0,
    };
    this._interval = 0;
    this.startTask = this.startTask.bind(this);
    this.endTask = this.endTask.bind(this);
    this.hideProgressBar = this.hideProgressBar.bind(this);
  }

  getState() {
    return Object.assign({}, this._state);
  }

  setState(state) {
    this._state = state;
    this.ES.trigger(this.ES.CHANGE_PROGRESSBAR, this.getState());
  }

  startTask(task) {
    let state = this.getState();
    state.tasks.push(task);
    if (state.tasks.length === 1) {
      state.progress = rsstag_utils.randInt(5, 80);
    }
    this.setState(state);
  }

  endTask() {
    let state = this.getState();
    state.tasks.pop();
    if (state.tasks.length === 0) {
      state.progress = 100;
    }
    this.setState(state);
  }

  hideProgressBar() {
    let state = this.getState();
    state.progress = 0;
    this.setState(state);
  }

  start() {
    this.ES.bind(this.ES.START_TASK, this.startTask);
    this.ES.bind(this.ES.END_TASK, this.endTask);
    this.ES.bind(this.ES.PROGRESSBAR_ANIMATION_END, this.hideProgressBar);
  }
}
