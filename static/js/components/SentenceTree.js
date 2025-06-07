'use strict';
import React from 'react';

class SentenceRow extends React.Component {
    render() {
        const { context } = this.props;
        return (
            <tr>
                <td className="left">{context.left}</td>
                <td className="mid">
                    {context.post_url ? (
                        <a href={context.post_url} target="_blank" rel="noopener noreferrer">{context.mid}</a>
                    ) : (
                        context.mid
                    )}
                </td>
                <td className="right">{context.right}</td>
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

        return (
            <div>
                <h4>
                    {cluster_link ? <a href={cluster_link}>Cluster {label}</a> : `Cluster ${label}`}
                    <button type="button" className="toggle-cluster-btn" onClick={this.toggleClusterContent}>
                        {isCollapsed ? "Expand" : "Collapse"}
                    </button>
                </h4>
                <div className="table-responsive" style={{ display: isCollapsed ? 'none' : '' }}>
                    <table className="s-tree-table">
                        <thead>
                            <tr>
                                <th>Left</th>
                                <th>Word</th>
                                <th>Right</th>
                            </tr>
                        </thead>
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