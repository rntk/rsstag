'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class TagsStorage {
    constructor(event_system, url) {
        this.ES = event_system;
        let tag_hash = decodeURIComponent(document.location.hash);
        this._state = {
            tags: new Map(),
            tag_hash: (tag_hash)? tag_hash.substr(1): ''
        };
        this.urls = {
            get_tag_siblings: url
        }
    }

    normalizedTags(tags) {
        let tags_m = new Map();

        tags.forEach(tag => {
            tag.root = true;
            tags_m.set(tag.tag, tag);
        });

        return tags_m;
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
        this.ES.bind(this.ES.CHANGE_TAG_SIBLINGS_STATE, this.changeTagSiblingsState.bind(this));
    }

    changeTagSiblingsState(tag) {
        //if (this._state.tags.has(tag)) {
        this.fetchTagSiblings(tag);
        //}
    }

    fetchTagSiblings(tag) {
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

                    data.data.sort((a, b) => {
                        if (a.count > b.count) {
                            return -1;
                        } else {
                            return 1;
                        }
                    });
                    for (let i = 0; i < data.data.length; i++) {
                        state.tags.set(data.data[i].tag, data.data[i]);
                    }
                    this.setState(state);
                } else {
                    this.errorMessage('Error. Try later');
                }
            }).catch(err => {
                this.errorMessage('Error. Try later');
            })
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