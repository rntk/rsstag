'use strict';
import React from 'react';

export default class ClustersTopics extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            clusters: {},
            currentClusterId: null,
            ranges: [],
            isLoading: false,
        };
        this.handleUpdate = this.handleUpdate.bind(this);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.CLUSTERS_TOPICS_UPDATED, this.handleUpdate);
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.CLUSTERS_TOPICS_UPDATED, this.handleUpdate);
    }

    handleUpdate(state) {
        this.setState(state);
    }

    handleClusterClick(clusterId) {
        this.props.ES.trigger(this.props.ES.FETCH_CLUSTERS_TOPICS_SENTENCES, clusterId);
    }

    handleToggleRead(range, nextRead) {
        const rangeKey = this.buildRangeKey(range.post_id, range.sentence_indices);
        this.props.ES.trigger(this.props.ES.CLUSTERS_TOPICS_CHANGE_STATUS, {
            selections: [{
                postId: range.post_id,
                sentenceIndices: range.sentence_indices,
                rangeKey: rangeKey
            }],
            readed: nextRead
        });
    }

    handleReadAll(readed) {
        const selections = this.state.ranges.map(range => ({
            postId: range.post_id,
            sentenceIndices: range.sentence_indices,
            rangeKey: this.buildRangeKey(range.post_id, range.sentence_indices)
        }));

        if (selections.length > 0) {
            this.props.ES.trigger(this.props.ES.CLUSTERS_TOPICS_CHANGE_STATUS, {
                selections: selections,
                readed: readed
            });
        }
    }

    buildRangeKey(postId, sentenceIndices) {
        const base = String(postId);
        if (!sentenceIndices || !sentenceIndices.length) {
            return base;
        }
        return base + "_" + sentenceIndices.join("_");
    }

    render() {
        const { clusters, currentClusterId, ranges, isLoading } = this.state;
        const clusterIds = Object.keys(clusters).sort((a, b) => clusters[b].count - clusters[a].count);

        if (clusterIds.length === 0) {
            return <div className="clusters-topics-page"><p>No clusters</p></div>;
        }

        const currentCluster = currentClusterId ? clusters[String(currentClusterId)] : null;

        return (
            <div className="clusters-topics-page">
                <div className="clusters-topics-list">
                    {clusterIds.map(id => (
                        <button
                            key={id}
                            className={`clusters-topic-item ${String(currentClusterId) === String(id) ? 'is-active' : ''}`}
                            onClick={() => this.handleClusterClick(id)}
                            type="button"
                        >
                            <span className="clusters-topic-title" dangerouslySetInnerHTML={{ __html: clusters[id].title }}></span>
                            <span className="clusters-topic-count">{clusters[id].count}</span>
                        </button>
                    ))}
                </div>
                <div className={`clusters-topic-sentences ${isLoading ? 'is-loading' : ''}`} id="clusters-topic-sentences">
                    {!currentClusterId ? (
                        <div className="clusters-topic-placeholder">Select a cluster to load sentences.</div>
                    ) : (
                        <>
                            <div className="clusters-topic-header" dangerouslySetInnerHTML={{ __html: currentCluster ? currentCluster.title : 'Cluster' }}></div>
                            {isLoading ? (
                                <div className="clusters-topic-placeholder">Loading...</div>
                            ) : ranges.length === 0 ? (
                                <div className="clusters-topic-placeholder">No ranges found.</div>
                            ) : (
                                <>
                                    <div className="clusters-topic-toolbar">
                                        <button
                                            className="clusters-read-btn"
                                            onClick={() => this.handleReadAll(true)}
                                            type="button"
                                        >Read all</button>
                                        <button
                                            className="clusters-read-btn"
                                            onClick={() => this.handleReadAll(false)}
                                            type="button"
                                        >Unread all</button>
                                    </div>
                                    <div className="clusters-topic-sentences-list">
                                        {ranges.map((range, idx) => {
                                            const rangeKey = this.buildRangeKey(range.post_id, range.sentence_indices);
                                            const isRead = !!range.read;

                                            return (
                                                <div key={`${rangeKey}_${idx}`} className={`clusters-topic-sentence ${isRead ? 'is-read' : 'is-unread'}`}>
                                                    <div className="clusters-topic-sentence-meta">
                                                        Post {range.post_id}
                                                        {range.topic_title && (
                                                            <> | <span dangerouslySetInnerHTML={{ __html: range.topic_title }}></span></>
                                                        )}
                                                    </div>
                                                    <div className="clusters-topic-sentence-text" dangerouslySetInnerHTML={{ __html: range.text }}></div>
                                                    <div className="clusters-topic-sentence-actions">
                                                        <button
                                                            className="clusters-topic-toggle-read"
                                                            onClick={() => this.handleToggleRead(range, !isRead)}
                                                            type="button"
                                                            title={isRead ? 'Mark as unread' : 'Mark as read'}
                                                        >
                                                            {isRead ? 'Mark Unread' : 'Mark Read'}
                                                        </button>
                                                        {range.post_id !== undefined && (
                                                            <a className="clusters-topic-sentence-link" href={`/posts/${encodeURIComponent(range.post_id)}`}>Open post</a>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </>
                            )}
                        </>
                    )}
                </div>
            </div>
        );
    }
}
