'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class ClustersTopicsStorage {
    constructor(event_system) {
        this.ES = event_system;
        this._state = {
            clusters: {},
            currentClusterId: null,
            ranges: [],
            isLoading: false,
        };
        this.urls = {
            fetch_sentences: '/clusters-topics-dyn-sentences',
            read_snippets: '/read/snippets',
        };
    }

    getState() {
        return Object.assign({}, this._state);
    }

    setState(state) {
        this._state = state;
        this.ES.trigger(this.ES.CLUSTERS_TOPICS_UPDATED, this.getState());
    }

    bindEvents() {
        this.ES.bind(this.ES.FETCH_CLUSTERS_TOPICS_SENTENCES, this.fetchSentences.bind(this));
        this.ES.bind(this.ES.CLUSTERS_TOPICS_CHANGE_STATUS, this.changeSnippetsStatus.bind(this));
    }

    fetchSentences(clusterId) {
        const cluster = this._state.clusters[String(clusterId)];
        if (!cluster || !cluster.ranges) {
            this.setState(Object.assign({}, this._state, {
                currentClusterId: clusterId,
                ranges: [],
                isLoading: false
            }));
            return;
        }

        this.setState(Object.assign({}, this._state, {
            currentClusterId: clusterId,
            isLoading: true
        }));

        rsstag_utils.fetchJSON(this.urls.fetch_sentences, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                ranges: cluster.ranges
            })
        }).then((payload) => {
            const ranges = payload && payload.ranges ? payload.ranges : [];
            this.setState(Object.assign({}, this._state, {
                ranges: ranges,
                isLoading: false
            }));
        }).catch((err) => {
            console.error('Failed to fetch sentences:', err);
            this.setState(Object.assign({}, this._state, {
                ranges: [],
                isLoading: false
            }));
        });
    }

    changeSnippetsStatus(data) {
        const { selections, readed } = data;
        if (!selections || !selections.length) {
            return;
        }

        const payloadSelections = selections.map(selection => ({
            post_id: selection.postId,
            sentence_indices: selection.sentenceIndices
        }));

        rsstag_utils.fetchJSON(this.urls.read_snippets, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                selections: payloadSelections,
                readed: readed
            })
        }).then((payload) => {
            if (payload && payload.data === 'ok') {
                const state = this.getState();
                const rangeKeys = selections.map(s => s.rangeKey);

                state.ranges = state.ranges.map(range => {
                    const rangeKey = this.buildRangeKey(range.post_id, range.sentence_indices);
                    if (rangeKeys.includes(rangeKey)) {
                        return Object.assign({}, range, { read: readed });
                    }
                    return range;
                });

                this.setState(state);
            } else {
                alert('Failed to update snippet status');
            }
        }).catch((err) => {
            console.error('Failed to update snippet status:', err);
            alert('Failed to update snippet status');
        });
    }

    buildRangeKey(postId, sentenceIndices) {
        const base = String(postId);
        if (!sentenceIndices || !sentenceIndices.length) {
            return base;
        }
        return base + "_" + sentenceIndices.join("_");
    }

    start() {
        this.bindEvents();
        if (window.cluster_data) {
            this.setState(Object.assign({}, this._state, {
                clusters: window.cluster_data
            }));
        }
    }
}
