'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class BiGramsMetionsStorage {
    constructor(tag, event_system) {
        this.ES = event_system;
        this._state = {
            tag: tag,
            bigrams: {}
        };
        this.urls = {
            get_tag_dates: '/bigrams-dates'
        }
    }

    getState() {
        return (Object.assign({}, this._state));
    }

    setState(state) {
        this._state = state;
        this.ES.trigger(this.ES.BIGRAMS_MENTIONS_UPDATED, this.getState());
    }

    fetchDates(tag) {
        rsstag_utils.fetchJSON(
            this.urls.get_tag_dates + '/' + encodeURIComponent(tag),
            {
                method: 'GET',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'}
            }
        ).then(data => {
            if (data.data) {
                let state = this.getState()
                state.bigrams = data.data;
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

    start() {
        let state = this.getState();
        this.fetchDates(state.tag);
    }
};