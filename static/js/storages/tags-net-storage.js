'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class TagsNetStorage {
    constructor(event_system, main_tag) {
        this.ES = event_system;
        this._state = {
            tags: new Map(),
            main_tag: main_tag
        };
        this.urls = {
            get_tag_net: '/api/tag-net'
        }
        this.fetchTagsNet = this.fetchTagsNet.bind(this);
    }

    mergeTags(old_state, data) {
        let tags = new Map(old_state.tags);

        data.forEach(el => {
            let new_tag = Object.assign(el);

            if (tags.has(new_tag.tag)) {
                let old_tag = tags.get(new_tag.tag);
                new_tag.edges.forEach(edge => {
                    old_tag.edges.add(edge);
                });
                delete new_tag.edges;
                old_tag = Object.assign(old_tag, new_tag);
                tags.set(new_tag.tag, old_tag);
            } else {
                new_tag.edges = new Set(new_tag.edges);
                tags.set(new_tag.tag, new_tag);
            }
        })
        old_state.tags = tags;
        return old_state;
    }

    fetchTagsNet(tag) {
        rsstag_utils.fetchJSON(
            this.urls.get_tag_net + '/' + encodeURIComponent(tag),
            {
                method: 'GET',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'}
            }
        ).then(data => {
            if (data.data) {
                this.setState(this.mergeTags(this.getState(), data.data));
            } else {
                this.errorMessage('Error. Try later');
            }
        }).catch(err => {
            console.log(err);
            this.errorMessage('Error. Try later');
        })
    }

    getState() {
        return(Object.assign({}, this._state));
    }

    setState(state) {
        this._state = state;
        this.ES.trigger(this.ES.TAGS_NET_UPDATED, this.getState());
    }

    bindEvents() {
        this.ES.bind(this.ES.LOAD_TAG_NET, this.fetchTagsNet);
    }

    errorMessage(msg) {
        console.log(msg);
        this.ES.trigger(this.ES.TAGS_ERROR_MESSAGE, msg);
    }

    start() {
        this.bindEvents();
        this.fetchTagsNet(this._state.main_tag);
    }
}