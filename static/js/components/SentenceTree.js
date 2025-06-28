'use strict';
import React from 'react';

const MAX_LEN = 150; // Number of symbols to show before truncation

class SentenceRow extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            leftExpanded: false,
            rightExpanded: false
        };
    }

    toggleLeft = () => {
        this.setState(prev => ({ leftExpanded: !prev.leftExpanded }));
    }

    toggleRight = () => {
        this.setState(prev => ({ rightExpanded: !prev.rightExpanded }));
    }

    renderLeftTruncated(text, expanded) {
        if (!text || text.length <= MAX_LEN) {
            return text;
        }
        if (expanded) {
            return text;
        } else {
            return <>...{text.slice(-MAX_LEN)}</>;
        }
    }

    renderTruncated(text, expanded) {
        // For right side only (show beginning)
        if (!text || text.length <= MAX_LEN) {
            return text;
        }
        if (expanded) {
            return text;
        } else {
            return <>{text.slice(0, MAX_LEN)}...</>;
        }
    }

    render() {
        const { context } = this.props;
        const { leftExpanded, rightExpanded } = this.state;
        const leftTruncatable = context.left && context.left.length > MAX_LEN;
        const rightTruncatable = context.right && context.right.length > MAX_LEN;

        return (
            <tr className="sentence-row">
                <td className="left sentence-cell">
                    <div className="sentence-cell-inner">
                        {this.renderLeftTruncated(context.left, leftExpanded)}
                    </div>
                    {leftTruncatable && (
                        <div className="show-more-less-block">
                            <button className="show-more-btn" onClick={this.toggleLeft}>
                                {leftExpanded ? 'show less' : 'show more'}
                            </button>
                        </div>
                    )}
                </td>
                <td className="mid sentence-cell">
                    <div className="sentence-cell-inner">
                        {context.post_url ? (
                            <a href={context.post_url} target="_blank" rel="noopener noreferrer">{context.mid}</a>
                        ) : (
                            context.mid
                        )}
                    </div>
                </td>
                <td className="right sentence-cell">
                    <div className="sentence-cell-inner">
                        {this.renderTruncated(context.right, rightExpanded)}
                    </div>
                    {rightTruncatable && (
                        <div className="show-more-less-block">
                            <button className="show-more-btn" onClick={this.toggleRight}>
                                {rightExpanded ? 'show less' : 'show more'}
                            </button>
                        </div>
                    )}
                </td>
            </tr>
        );
    }
}

class Cluster extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            isCollapsed: false // Default to expanded
        };
        this.toggleClusterContent = this.toggleClusterContent.bind(this);
    }

    toggleClusterContent() {
        this.setState(prevState => ({
            isCollapsed: !prevState.isCollapsed
        }));
    }

    render() {
        const { label, ctxs, cluster_link } = this.props;
        const { isCollapsed } = this.state;
        let posts_count = 0;
        if (cluster_link) {
            posts_count = 1; // If a link exists, there is at least one post.
            const pids_match = cluster_link.match(/posts?\/([\d_]+)/);
            if (pids_match) {
                const pids_str = pids_match[1];
                const underscore_count = (pids_str.match(/_/g) || []).length;
                posts_count = underscore_count + 1;
            }
        }

        return (
            <div>
                <h4>
                    {cluster_link ? <a href={cluster_link}>Cluster {label}</a> : `Cluster ${label}`} ({posts_count}/{ctxs.length})
                    <button type="button" className="toggle-cluster-btn" onClick={this.toggleClusterContent}>
                        {isCollapsed ? "Expand" : "Collapse"}
                    </button>
                </h4>
                <div className="table-responsive" style={{ display: isCollapsed ? 'none' : '' }}>
                    <table className="s-tree-table">
                        <tbody>
                            {ctxs.map((c, index) => (
                                <SentenceRow key={index} context={c} />
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    }
}

export default class SentenceTree extends React.Component {
    constructor(props) {
        super(props);
        // Initialize state robustly from props or global window object
        const source = props.s_tree_data || window.s_tree_data || {};
        this.state = {
            tag: source.tag || '',
            words: Array.isArray(source.words) ? source.words : [],
            clusters: (source.clusters && typeof source.clusters === 'object') ? source.clusters : {},
            cluster_links: (source.cluster_links && typeof source.cluster_links === 'object') ? source.cluster_links : {}
        };
    }

    componentDidMount() {
        // If data is not passed via props and window.s_tree_data might have been populated
        // after construction (e.g., async loading, though less likely with script tags).
        if (!this.props.s_tree_data && window.s_tree_data) {
            const source = window.s_tree_data || {};
            // Check if an update is genuinely needed to avoid redundant re-renders if constructor already set it.
            // This is a simplified check; for deep objects, a deep comparison might be needed.
            // For now, we'll update if the source object itself has changed or critical parts differ.
            if (this.state.tag !== (source.tag || '') || 
                JSON.stringify(this.state.words) !== JSON.stringify(Array.isArray(source.words) ? source.words : []) ||
                JSON.stringify(this.state.clusters) !== JSON.stringify((source.clusters && typeof source.clusters === 'object') ? source.clusters : {})) {
                this.setState({
                    tag: source.tag || '',
                    words: Array.isArray(source.words) ? source.words : [],
                    clusters: (source.clusters && typeof source.clusters === 'object') ? source.clusters : {},
                    cluster_links: (source.cluster_links && typeof source.cluster_links === 'object') ? source.cluster_links : {}
                });
            }
        }
    }

    render() {
        const { tag, words, clusters, cluster_links } = this.state;

        if (!clusters || Object.keys(clusters).length === 0) {
            return (
                <div className="page">
                    <div className="group_title">
                        <h3>Sentence Tree: {tag}</h3>
                        <div>Words: {Array.isArray(words) ? words.join(', ') : ''}</div>
                    </div>
                    <p>No sentences found.</p>
                </div>
            );
        }

        return (
            <div className="page">
                <div className="group_title">
                    <h3>Sentence Tree: {tag}</h3>
                    <div>Words: {Array.isArray(words) ? words.join(', ') : ''}</div>
                </div>
                {Object.entries(clusters).map(([label, ctxs]) => (
                    <Cluster 
                        key={label} 
                        label={label} 
                        ctxs={Array.isArray(ctxs) ? ctxs : []} // Ensure ctxs is always an array
                        cluster_link={cluster_links[label]} 
                    />
                ))}
            </div>
        );
    }
}