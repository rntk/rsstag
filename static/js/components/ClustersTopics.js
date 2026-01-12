import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import rsstag_utils from '../libs/rsstag_utils.js';

const URLS = {
    fetch_sentences: '/clusters-topics-dyn-sentences',
    read_snippets: '/read/snippets',
};

const ClustersTopics = () => {
    const [state, setState] = useState({
        clusters: {},
        currentClusterId: null,
        ranges: [],
        isLoading: false,
    });

    const abortControllerRef = useRef(null);
    const latestClusterIdRef = useRef(null);

    useEffect(() => {
        if (window.cluster_data) {
            setState((prev) => ({ ...prev, clusters: window.cluster_data }));
        }
    }, []);

    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);

    const buildRangeKey = useCallback((postId, sentenceIndices) => {
        const base = String(postId);
        if (!sentenceIndices || !sentenceIndices.length) {
            return base;
        }
        return base + '_' + sentenceIndices.join('_');
    }, []);

    const fetchSentences = useCallback((clusterId) => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        latestClusterIdRef.current = clusterId;

        setState((prev) => {
            const cluster = prev.clusters[String(clusterId)];
            if (!cluster || !cluster.ranges) {
                return {
                    ...prev,
                    currentClusterId: clusterId,
                    ranges: [],
                    isLoading: false,
                };
            }

            abortControllerRef.current = new AbortController();

            rsstag_utils
                .fetchJSON(URLS.fetch_sentences, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        ranges: cluster.ranges,
                    }),
                    signal: abortControllerRef.current.signal,
                })
                .then((payload) => {
                    if (latestClusterIdRef.current !== clusterId) {
                        return;
                    }

                    const ranges = payload && payload.ranges ? payload.ranges : [];
                    setState((prev) => ({
                        ...prev,
                        ranges: ranges,
                        isLoading: false,
                    }));
                })
                .catch((err) => {
                    if (err.name === 'AbortError') {
                        return;
                    }

                    if (latestClusterIdRef.current !== clusterId) {
                        return;
                    }

                    console.error('Failed to fetch sentences:', err);
                    setState((prev) => ({
                        ...prev,
                        ranges: [],
                        isLoading: false,
                    }));
                });

            return {
                ...prev,
                currentClusterId: clusterId,
                isLoading: true,
            };
        });
    }, []);

    const changeSnippetsStatus = useCallback((selections, readed) => {
        if (!selections || !selections.length) {
            return;
        }

        const payloadSelections = selections.map((selection) => ({
            post_id: selection.postId,
            sentence_indices: selection.sentenceIndices,
        }));

        rsstag_utils
            .fetchJSON(URLS.read_snippets, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    selections: payloadSelections,
                    readed: readed,
                }),
            })
            .then((payload) => {
                if (payload && payload.data === 'ok') {
                    const rangeKeys = selections.map((s) => s.rangeKey);

                    setState((prev) => ({
                        ...prev,
                        ranges: prev.ranges.map((range) => {
                            const rangeKey = buildRangeKey(range.post_id, range.sentence_indices);
                            if (rangeKeys.includes(rangeKey)) {
                                return { ...range, read: readed };
                            }
                            return range;
                        }),
                    }));
                } else {
                    alert('Failed to update snippet status');
                }
            })
            .catch((err) => {
                console.error('Failed to update snippet status:', err);
                alert('Failed to update snippet status');
            });
    }, [buildRangeKey]);

    const handleClusterClick = (clusterId) => {
        fetchSentences(clusterId);
    };

    const handleToggleRead = (range, nextRead) => {
        const rangeKey = buildRangeKey(range.post_id, range.sentence_indices);
        changeSnippetsStatus(
            [
                {
                    postId: range.post_id,
                    sentenceIndices: range.sentence_indices,
                    rangeKey: rangeKey,
                },
            ],
            nextRead
        );
    };

    const handleReadAll = (readed) => {
        const selections = state.ranges.map((range) => ({
            postId: range.post_id,
            sentenceIndices: range.sentence_indices,
            rangeKey: buildRangeKey(range.post_id, range.sentence_indices),
        }));

        if (selections.length > 0) {
            changeSnippetsStatus(selections, readed);
        }
    };

    const { clusters, currentClusterId, ranges, isLoading } = state;
    const clusterIds = Object.keys(clusters).sort((a, b) => clusters[b].count - clusters[a].count);

    if (clusterIds.length === 0) {
        return (
            <div className="clusters-topics-page">
                <p>No clusters</p>
            </div>
        );
    }

    const currentCluster = currentClusterId ? clusters[String(currentClusterId)] : null;

    return (
        <div className="clusters-topics-page">
            <div className="clusters-topics-list">
                {clusterIds.map((id) => (
                    <button
                        key={id}
                        className={`clusters-topic-item ${String(currentClusterId) === String(id) ? 'is-active' : ''}`}
                        onClick={() => handleClusterClick(id)}
                        type="button"
                    >
                        <span
                            className="clusters-topic-title"
                            dangerouslySetInnerHTML={{ __html: clusters[id].title }}
                        ></span>
                        <span className="clusters-topic-count">{clusters[id].count}</span>
                    </button>
                ))}
            </div>
            <div
                className={`clusters-topic-sentences ${isLoading ? 'is-loading' : ''}`}
                id="clusters-topic-sentences"
            >
                {!currentClusterId ? (
                    <div className="clusters-topic-placeholder">Select a cluster to load sentences.</div>
                ) : (
                    <>
                        <div
                            className="clusters-topic-header"
                            dangerouslySetInnerHTML={{ __html: currentCluster ? currentCluster.title : 'Cluster' }}
                        ></div>
                        {isLoading ? (
                            <div className="clusters-topic-placeholder">Loading...</div>
                        ) : ranges.length === 0 ? (
                            <div className="clusters-topic-placeholder">No ranges found.</div>
                        ) : (
                            <>
                                <div className="clusters-topic-toolbar">
                                    <button
                                        className="clusters-read-btn"
                                        onClick={() => handleReadAll(true)}
                                        type="button"
                                    >
                                        Read all
                                    </button>
                                    <button
                                        className="clusters-read-btn"
                                        onClick={() => handleReadAll(false)}
                                        type="button"
                                    >
                                        Unread all
                                    </button>
                                </div>
                                <div className="clusters-topic-sentences-list">
                                    {ranges.map((range, idx) => {
                                        const rangeKey = buildRangeKey(range.post_id, range.sentence_indices);
                                        const isRead = !!range.read;

                                        return (
                                            <div
                                                key={`${rangeKey}_${idx}`}
                                                className={`clusters-topic-sentence ${isRead ? 'is-read' : 'is-unread'}`}
                                            >
                                                <div className="clusters-topic-sentence-meta">
                                                    Post {range.post_id}
                                                    {range.topic_title && (
                                                        <>
                                                            {' '}
                                                            | <span dangerouslySetInnerHTML={{ __html: range.topic_title }}></span>
                                                        </>
                                                    )}
                                                </div>
                                                <div
                                                    className="clusters-topic-sentence-text"
                                                    dangerouslySetInnerHTML={{ __html: range.text }}
                                                ></div>
                                                <div className="clusters-topic-sentence-actions">
                                                    <button
                                                        className="clusters-topic-toggle-read"
                                                        onClick={() => handleToggleRead(range, !isRead)}
                                                        type="button"
                                                        title={isRead ? 'Mark as unread' : 'Mark as read'}
                                                    >
                                                        {isRead ? 'Mark Unread' : 'Mark Read'}
                                                    </button>
                                                    {range.post_id !== undefined && (
                                                        <a
                                                            className="clusters-topic-sentence-link"
                                                            href={`/posts/${encodeURIComponent(range.post_id)}`}
                                                        >
                                                            Open post
                                                        </a>
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
};

export default ClustersTopics;
