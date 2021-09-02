'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class TagsClustersStorage {
    constructor(event_system) {
        this.ES = event_system;
        let tag_hash = decodeURIComponent(document.location.hash);
        this._state = {
            clusters: {}
        };
        this.urls = {
            get_tag_siblings: "/tag-clusters"
        }
    }

    getState() {
        return(Object.assign({}, this._state));
    }

    setState(state) {
        this._state = state;
        this.ES.trigger(this.ES.TAGS_CLUSTERS_UPDATED, this.getState());
    }

    bindEvents() {
        this.ES.bind(this.ES.CHANGE_TAGS_LOAD_BUTTON_STATE, this.changeTagClustersState.bind(this));
    }

    changeTagClustersState(event_data) {
        if (event_data.hide_list) {
            let state = this.getState()
            state.clusters = new Map();
            this.setState(state);
            return;
        }
        this.fetchTagClusters(event_data.tag);
    }

    fetchTagClusters(tag) {
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
                    state.clusters = data.data;
                    this.setState(state);
                } else {
                    this.errorMessage('Error: No data. Try later');
                }
            }).catch(err => {
                this.errorMessage('Error. Try later. ' + err);
            })
        }
    }

    errorMessage(msg) {
        console.log(msg);
        this.ES.trigger(this.TAGS_ERROR_MESSAGE, msg);
    }

    start() {
        this.bindEvents();
    }
}