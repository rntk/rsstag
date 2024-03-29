'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class TagMetionsStorage {
    constructor(tag, event_system) {
        this.ES = event_system;
        this._state = {
            tag: tag,
            dates: []
        };
        this.urls = {
            get_tag_dates: '/tag-dates'
        };
        this.changeMentionsState = this.changeMentionsState.bind(this);
    }

    getState() {
        return (Object.assign({}, this._state));
    }

    setState(state) {
        this._state = state;
        this.ES.trigger(this.ES.TAG_MENTIONS_UPDATED, this.getState());
    }

    changeMentionsState(event_data) {
        if (event_data.hide_list) {
            let state = this.getState();
            state.dates = [];
            this.setState(state);
            return;
        }
        this.fetchTagDates(event_data.tag);
    }

    fetchTagDates(tag) {
        rsstag_utils.fetchJSON(
            this.urls.get_tag_dates + '/' + encodeURIComponent(tag),
            {
                method: 'GET',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'}
            }
        ).then(data => {
            if (data.data) {
                let state = this.getState();
                state.dates = data.data;
                this.setState(state);
            } else {
                this.errorMessage('Error. Try later', data);
            }
        }).catch(err => {
            this.errorMessage('Error. Try later', err);
        });
    }

    errorMessage(msg, data) {
        console.log(msg, data);
        this.ES.trigger(this.TAGS_ERROR_MESSAGE, msg);
    }

    bindEvents() {
        this.ES.bind(this.ES.CHANGE_TAGS_LOAD_BUTTON_STATE, this.changeMentionsState);
    }

    start() {
        this.bindEvents();
    }
}