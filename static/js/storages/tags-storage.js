'use strict';
export default class TagsStorage {
    constructor(event_system) {
        this.ES = event_system;
        this._state = {
            tags: new Map(),
        };
        this.urls = {
            get_tag_siblings: '/tag-siblings'
        }
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
        this.ES.bind(this.ES.CHANGE_TAG_SIBLINGS_STATE, this.changeTagSiblingsState.bind(this));
    }

    changeTagSiblingsState(tag) {
        if (this._state.tags.has(tag)) {
            this.fetchTagSiblings(tag);
        }
    }

    fetchTagSiblings(tag) {
        if (tag) {
            fetch(
                this.urls.get_tag_siblings + '/' + encodeURIComponent(tag),
                {
                    method: 'GET',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'}
                }
            ).then(response => {
                response.json().then(data => {
                    if (data.data) {
                        let state = this.getState();

                        if (state.tags.has(tag)) {
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
                });
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