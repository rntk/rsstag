'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class BiGramsStorage {
    constructor(event_system) {
        this.ES = event_system;
        let tag_hash = decodeURIComponent(document.location.hash);
        this._state = {
            tags: new Map(),
            tag_hash: (tag_hash)? tag_hash.substr(1): ''
        };
        this.urls = {
            get_tag_siblings: '/bi-grams-siblings'
        };
    }

    normalizedTags(tags) {
        let tags_m = new Map();

        tags.forEach(tag => {
            tag.root = true;
            tags_m.set(tag.tag, tag);
        });

        return(tags_m);
    }

    fetchTags() {
        let state = this.getState();

        if (window.initial_tags_list) {
            state.tags = this.normalizedTags(window.initial_tags_list);
            this.setState(state);
        }
    }

    getState() {
        return(Object.assign({}, this._state));
    }

    setState(state) {
        this._state = state;
        this.ES.trigger(this.ES.TAGS_UPDATED, this.getState());
    }

    bindEvents() {
        this.ES.bind(this.ES.CHANGE_TAGS_LOAD_BUTTON_STATE, this.changeTagBigramsState.bind(this));
    }

    changeTagBigramsState(event_data) {
        if (event_data.hide_list) {
            let state = this.getState();
            state.tags = new Map();
            this.setState(state);
            return;
        }
        if (this._state.tags.has(event_data.tag)) {
            this.fetchTagBigrams(event_data.tag);
        }
    }

    fetchTagBigrams(tag) {
        if (tag) {
            rsstag_utils.fetchJSON(
                this.urls.get_tag_siblings + '/' + encodeURIComponent(tag),
                {
                    method: 'GET',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'}
                }
            ).then(data => {
                if (data.data) {
                    let state = this.getState();

                    if (state.tags.has(tag)) {
                        data.data.sort((a, b) => {
                            if (a.count > b.count) {
                                return -1;
                            } else {
                                return 1;
                            }
                        });
                        let tag_data = state.tags.get(tag);
                        tag_data.siblings = [];
                        for (let i = 0; i < data.data.length; i++) {
                            let sibling = data.data[i];
                            sibling.parent = tag;
                            sibling.root = state.tags.has(tag);
                            tag_data.siblings.push(sibling.tag);
                            state.tags.set(sibling.tag, sibling);
                        }
                        state.tags.set(tag, tag_data);
                        this.setState(state);
                    }
                } else {
                    this.errorMessage('Error. Try later');
                }
            }).catch(err => {
                this.errorMessage('Error. Try later');
            });
        }
    }

    errorMessage(msg) {
        console.log(msg);
        this.ES.trigger(this.TAGS_ERROR_MESSAGE, msg);
    }

    start() {
        this.bindEvents();
        this.fetchTags();
    }
}