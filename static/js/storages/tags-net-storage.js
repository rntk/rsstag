'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class TagsNetStorage {
    constructor(event_system, main_tag) {
        this.ES = event_system;
        this._state = {
            tags: new Map(),
            main_tag: main_tag,
            selected_tag: ''
        };
        this.urls = {
            get_tag_net: '/api/tag-net'
        }
        this.fetchTagsNet = this.fetchTagsNet.bind(this);
        this.selectTag = this.selectTag.bind(this);
        this.changeTagSettings = this.changeTagSettings.bind(this);
    }

    selectTag(tag_id) {
        let state = this.getState();

        if (state.tags.has(tag_id)) {
            state.selected_tag = tag_id;
            this.setState(state);
        }
    }

    needHideEdge(edges, root) {
        let need_hide = true;

        for (let edge of edges) {
            if (edge !== root) {
                let tag = this._state.tags.get(edge);

                if (!tag.hidden) {
                    need_hide = false;
                    break;
                }
            }
        }
        return need_hide;
    }

    changeTagSettings(tag) {
        let state = this.getState();

        if (state.tags.has(tag.tag)) {
            state.tags.set(tag.tag, tag);
            for (let edge of tag.edges) {
                let tmp_tag = state.tags.get(edge);
                if (!tag.hidden || this.needHideEdge(tmp_tag.edges, tag.tag)) {
                    tmp_tag.hidden = tag.hidden;
                    state.tags.set(edge, tmp_tag);
                }
            }
            this.setState(state);
        }
    }

    mergeTags(old_state, data, group) {
        let tags = new Map(old_state.tags);

        data.forEach(el => {
            let new_tag = Object.assign(el);

            if (tags.has(new_tag.tag)) {
                let old_tag = tags.get(new_tag.tag);
                new_tag.edges.forEach(edge => {
                    old_tag.edges.add(edge);
                });
                delete new_tag.edges;
                if (old_tag.tag === group) {
                    old_tag.group = group;
                }
                old_tag = Object.assign(old_tag, new_tag);
                tags.set(new_tag.tag, old_tag);
            } else {
                new_tag.group = group;
                new_tag.hidden = false;
                new_tag.edges = new Set(new_tag.edges);
                tags.set(new_tag.tag, new_tag);
            }
        })
        old_state.tags = tags;
        return old_state;
    }

    fetchTagsNet(tag) {
        if (tag) {
            rsstag_utils.fetchJSON(
                this.urls.get_tag_net + '/' + encodeURIComponent(tag),
                {
                    method: 'GET',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'}
                }
            ).then(data => {
                if (data.data) {
                    this.setState(this.mergeTags(this.getState(), data.data, tag));
                } else {
                    this.errorMessage('Error. Try later');
                }
            }).catch(err => {
                console.log(err);
                this.errorMessage('Error. Try later');
            });
        }
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
        this.ES.bind(this.ES.NET_TAG_SELECTED, this.selectTag);
        this.ES.bind(this.ES.NET_TAG_CHANGE, this.changeTagSettings);
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