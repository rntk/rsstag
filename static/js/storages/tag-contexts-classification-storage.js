'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class TagContextsClassificationStorage {
    constructor(event_system) {
        this.ES = event_system;
        this._state = {
            tags: new Map()
        };
        this.urls = {
            get_contexts: '/tag-contexts-classification'
        };
    }

    getState() {
        return(Object.assign({}, this._state));
    }

    setState(state) {
        this._state = state;
        this.ES.trigger(this.ES.TAGS_UPDATED, this.getState());
    }

    bindEvents() {
        this.ES.bind(this.ES.CHANGE_TAGS_LOAD_BUTTON_STATE, this.changeLoadButtonState.bind(this));
    }

    changeLoadButtonState(event_data) {
        if (event_data.hide_list) {
            let state = this.getState();
            state.tags = new Map();
            this.setState(state);
            return;
        }
        this.fetchContexts(event_data.tag);
    }

    fetchContexts(tag) {
        if (tag) {
            this.ES.trigger(this.ES.START_TASK, 'ajax');
            rsstag_utils.fetchJSON(
                this.urls.get_contexts + '/' + encodeURIComponent(tag),
                {
                    method: 'GET',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'}
                }
            ).then(data => {
                this.ES.trigger(this.ES.END_TASK, 'ajax');
                if (data) {
                    let state = this.getState();
                    state.tags = new Map();
                    for (let i = 0; i < data.length; i++) {
                        state.tags.set(data[i].tag, data[i]);
                    }
                    this.setState(state);
                }
            }).catch(err => {
                this.ES.trigger(this.ES.END_TASK, 'ajax');
                console.error('Error fetching contexts:', err);
            });
        }
    }

    start() {
        this.bindEvents();
    }
}
