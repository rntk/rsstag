'use strict';
import React from 'react';

/**
 * BigramsTable - A visualization component that displays bigrams in a table format
 * similar to the "Year in Sports" calendar visualization.
 * 
 * - Rows represent the first word of each bigram
 * - Columns represent the second word of each bigram
 * - Cells show circles with size proportional to bigram frequency
 * - Most frequent bigrams are positioned in the top-left corner
 */
export default class BigramsTable extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            tags: new Map(),
            tag_hash: ''
        };
        this.updateTags = this.updateTags.bind(this);
    }

    updateTags(state) {
        this.setState(state);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.TAGS_UPDATED, this.updateTags);
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.TAGS_UPDATED, this.updateTags);
    }

    /**
     * Process bigrams into a matrix structure for table display
     * Sorts by frequency so most frequent appear in top-left
     * Uses iterative refinement to minimize sparsity
     * @returns {Object} { firstWords: [], secondWords: [], matrix: {}, maxCount: number }
     */
    processBigrams() {
        const { tags } = this.state;
        if (!tags || !tags.size) {
            return { firstWords: [], secondWords: [], matrix: {}, maxCount: 0 };
        }

        const firstWordCounts = {};  // Total count for each first word
        const secondWordCounts = {}; // Total count for each second word
        const matrix = {};
        let maxCount = 0;

        // Track which second words each first word connects to
        const firstWordConnections = {};
        const secondWordConnections = {};

        // Process each bigram
        tags.forEach((tagData, tagKey) => {
            const bigramParts = tagData.tag.split(' ');
            if (bigramParts.length >= 2) {
                const firstWord = bigramParts[0];
                const secondWord = bigramParts[1];
                const count = tagData.count || 1;

                // Accumulate counts for sorting
                firstWordCounts[firstWord] = (firstWordCounts[firstWord] || 0) + count;
                secondWordCounts[secondWord] = (secondWordCounts[secondWord] || 0) + count;

                // Track connections
                if (!firstWordConnections[firstWord]) {
                    firstWordConnections[firstWord] = new Set();
                }
                firstWordConnections[firstWord].add(secondWord);

                if (!secondWordConnections[secondWord]) {
                    secondWordConnections[secondWord] = new Set();
                }
                secondWordConnections[secondWord].add(firstWord);

                if (!matrix[firstWord]) {
                    matrix[firstWord] = {};
                }
                matrix[firstWord][secondWord] = {
                    count: count,
                    tag: tagData.tag,
                    url: tagData.url
                };

                if (count > maxCount) {
                    maxCount = count;
                }
            }
        });

        // Sort words by total frequency first
        let firstWords = Object.keys(firstWordCounts).sort((a, b) => 
            firstWordCounts[b] - firstWordCounts[a]
        );
        let secondWords = Object.keys(secondWordCounts).sort((a, b) => 
            secondWordCounts[b] - secondWordCounts[a]
        );

        // Iterative refinement: re-sort to minimize sparsity in top-left corner
        // Score each word by how many connections it has with top-ranked words from the other axis
        const iterations = 3;
        for (let iter = 0; iter < iterations; iter++) {
            // Re-score first words based on connections to top second words
            const topSecondWords = new Set(secondWords.slice(0, Math.min(20, secondWords.length)));
            firstWords = firstWords.sort((a, b) => {
                const aTopConnections = [...(firstWordConnections[a] || [])].filter(w => topSecondWords.has(w)).length;
                const bTopConnections = [...(firstWordConnections[b] || [])].filter(w => topSecondWords.has(w)).length;
                // Primary: connections to top columns, Secondary: total frequency
                if (bTopConnections !== aTopConnections) {
                    return bTopConnections - aTopConnections;
                }
                return firstWordCounts[b] - firstWordCounts[a];
            });

            // Re-score second words based on connections to top first words
            const topFirstWords = new Set(firstWords.slice(0, Math.min(20, firstWords.length)));
            secondWords = secondWords.sort((a, b) => {
                const aTopConnections = [...(secondWordConnections[a] || [])].filter(w => topFirstWords.has(w)).length;
                const bTopConnections = [...(secondWordConnections[b] || [])].filter(w => topFirstWords.has(w)).length;
                // Primary: connections to top rows, Secondary: total frequency
                if (bTopConnections !== aTopConnections) {
                    return bTopConnections - aTopConnections;
                }
                return secondWordCounts[b] - secondWordCounts[a];
            });
        }

        return { firstWords, secondWords, matrix, maxCount };
    }

    /**
     * Calculate circle size based on frequency
     * @param {number} count - Bigram frequency
     * @param {number} maxCount - Maximum frequency in dataset
     * @returns {number} Circle radius in pixels
     */
    getCircleSize(count, maxCount) {
        const minSize = 6;
        const maxSize = 28;
        if (maxCount === 0) return minSize;
        
        // Use square root scale for better visual distribution
        const normalized = Math.sqrt(count / maxCount);
        return minSize + (maxSize - minSize) * normalized;
    }

    /**
     * Get circle color based on frequency tier
     * @param {number} count - Bigram frequency
     * @param {number} maxCount - Maximum frequency
     * @returns {string} CSS color
     */
    getCircleColor(count, maxCount) {
        const ratio = count / maxCount;
        if (ratio > 0.7) {
            return '#3498db'; // Blue for high frequency
        } else if (ratio > 0.4) {
            return '#e67e22'; // Orange for medium
        } else if (ratio > 0.2) {
            return '#f1c40f'; // Yellow for low-medium
        } else {
            return '#e74c3c'; // Red for low
        }
    }

    renderCircle(cellData, maxCount) {
        if (!cellData) return null;
        
        const circleSize = this.getCircleSize(cellData.count, maxCount);
        const circleColor = this.getCircleColor(cellData.count, maxCount);
        const showInner = cellData.count > maxCount * 0.3;
        const showCenter = cellData.count > maxCount * 0.6;

        return (
            <a href={cellData.url} className="bigram-cell-link" title={`${cellData.tag}: ${cellData.count}`}>
                <svg width={circleSize + 4} height={circleSize + 4} className="bigram-circle-svg">
                    <circle
                        cx={(circleSize + 4) / 2}
                        cy={(circleSize + 4) / 2}
                        r={circleSize / 2}
                        fill="none"
                        stroke={circleColor}
                        strokeWidth="2"
                        className="bigram-circle"
                    />
                    {showInner && (
                        <circle
                            cx={(circleSize + 4) / 2}
                            cy={(circleSize + 4) / 2}
                            r={circleSize / 4}
                            fill="none"
                            stroke={circleColor}
                            strokeWidth="1.5"
                            className="bigram-circle-inner"
                        />
                    )}
                    {showCenter && (
                        <circle
                            cx={(circleSize + 4) / 2}
                            cy={(circleSize + 4) / 2}
                            r={2}
                            fill={circleColor}
                            className="bigram-circle-center"
                        />
                    )}
                </svg>
            </a>
        );
    }

    render() {
        const { firstWords, secondWords, matrix, maxCount } = this.processBigrams();

        if (firstWords.length === 0 || secondWords.length === 0) {
            return <p>No bigrams data available</p>;
        }

        return (
            <div className="bigrams-table-container">
                <div className="bigrams-table-legend">
                    <h4>Frequency Legend</h4>
                    <div className="legend-items">
                        <span className="legend-item">
                            <span className="legend-circle" style={{ backgroundColor: '#3498db', width: 20, height: 20 }}></span>
                            High
                        </span>
                        <span className="legend-item">
                            <span className="legend-circle" style={{ backgroundColor: '#e67e22', width: 15, height: 15 }}></span>
                            Medium
                        </span>
                        <span className="legend-item">
                            <span className="legend-circle" style={{ backgroundColor: '#f1c40f', width: 10, height: 10 }}></span>
                            Low-Medium
                        </span>
                        <span className="legend-item">
                            <span className="legend-circle" style={{ backgroundColor: '#e74c3c', width: 6, height: 6 }}></span>
                            Low
                        </span>
                    </div>
                </div>
                
                <div className="bigrams-table-scroll">
                    <table className="bigrams-table">
                        <thead>
                            <tr>
                                <th className="bigrams-corner-cell"></th>
                                {secondWords.map((word) => (
                                    <th key={`col-${word}`} className="bigrams-col-header">
                                        <a href={`/tag-info/${encodeURIComponent(word)}`}>{word}</a>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {firstWords.map((firstWord) => (
                                <tr key={`row-${firstWord}`}>
                                    <th className="bigrams-row-header">
                                        <a href={`/tag-info/${encodeURIComponent(firstWord)}`}>{firstWord}</a>
                                    </th>
                                    {secondWords.map((secondWord) => {
                                        const cellData = matrix[firstWord]?.[secondWord];
                                        return (
                                            <td key={`cell-${firstWord}-${secondWord}`} className="bigrams-cell">
                                                {this.renderCircle(cellData, maxCount)}
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    }
}
