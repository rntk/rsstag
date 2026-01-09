/**
 * Shared utilities for River Charts
 */

/**
 * Calculates bins for a river chart based on sentence indices.
 */
export const calculateBins = (binCount, topics, startRange, endRange) => {
    const range = endRange - startRange;
    const binSize = Math.max(1, range / binCount);

    return Array.from({ length: binCount }, (_, i) => {
        const start = startRange + i * binSize;
        const end = startRange + (i + 1) * binSize;
        const binData = { x: i, rangeStart: start, rangeEnd: end };

        topics.forEach(topic => {
            const name = topic.name;
            // Count sentences of this topic in this bin
            const count = topic.sentences.filter(s => s >= start && s < end).length;
            binData[name] = count;
        });
        return binData;
    });
};

/**
 * Applies smoothing to binned data.
 */
export const smoothBins = (bins, topics) => {
    return bins.map((bin, i) => {
        const smoothedBin = { ...bin };

        topics.forEach(topic => {
            const name = topic.name;
            const currentVal = bin[name] || 0;

            if (currentVal === 0) {
                const prevVal = i > 0 ? (bins[i - 1][name] || 0) : 0;
                const nextVal = i < bins.length - 1 ? (bins[i + 1][name] || 0) : 0;

                if (prevVal > 0 && nextVal > 0) {
                    smoothedBin[name] = Math.min(prevVal, nextVal) * 0.3;
                } else if (prevVal > 0 || nextVal > 0) {
                    smoothedBin[name] = Math.max(prevVal, nextVal) * 0.1;
                } else {
                    smoothedBin[name] = 0;
                }
            } else {
                const prevVal = i > 0 ? (bins[i - 1][name] || 0) : currentVal;
                const nextVal = i < bins.length - 1 ? (bins[i + 1][name] || 0) : currentVal;
                smoothedBin[name] = currentVal * 0.6 + prevVal * 0.2 + nextVal * 0.2;
            }
        });
        return smoothedBin;
    });
};

/**
 * Converts sentence counts to estimated character counts.
 */
export const estimateCharacterCounts = (bins, topics) => {
    return bins.map(bin => {
        const charBin = { ...bin };

        topics.forEach(topic => {
            const name = topic.name;
            const sentenceCount = bin[name] || 0;
            const avgCharsPerSentence = topic.avgCharsPerSentence || 100;
            charBin[name] = sentenceCount * avgCharsPerSentence;
        });

        return charBin;
    });
};

/**
 * Common color scale for charts
 */
export const getRiverColorScale = (keys) => {
    if (typeof d3 === 'undefined') {
        console.error('D3 is not loaded');
        return (key) => '#ccc';
    }
    return d3.scaleOrdinal()
        .domain(keys)
        .range(d3.schemePastel1.concat(d3.schemeSet2).concat(d3.schemeTableau10));
};
