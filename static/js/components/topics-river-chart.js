import { calculateBins, smoothBins, estimateCharacterCounts, getRiverColorScale } from '../libs/chart-utils.js';
import RiverLegend from './river-legend.js';

/**
 * TopicsRiverChart component (Vanilla JS version)
 */
export default class TopicsRiverChart {
    constructor(containerSelector, options = {}) {
        this.container = typeof containerSelector === 'string' ? document.querySelector(containerSelector) : containerSelector;
        this.topics = options.topics || [];
        this.articleLength = options.articleLength || 0;
        this.activeTopic = null;
        this.legend = null;
        this.svg = null;

        // Internal state
        this.effectiveLength = this._calculateEffectiveLength();
        this.keys = this.topics.map(t => t.name);
        this.colorScale = getRiverColorScale(this.keys);

        this.init();
    }

    _calculateEffectiveLength() {
        if (!this.topics || this.topics.length === 0) return 0;
        let maxSentenceIndex = 0;
        this.topics.forEach(topic => {
            if (topic.sentences && topic.sentences.length > 0) {
                const max = Math.max(...topic.sentences);
                if (max > maxSentenceIndex) maxSentenceIndex = max;
            }
        });
        const validArticleLength = (typeof this.articleLength === 'number' && this.articleLength > 0) ? this.articleLength : Infinity;
        return Math.min(maxSentenceIndex + 5, validArticleLength);
    }

    init() {
        if (!this.container) return;
        if (typeof d3 === 'undefined') {
            this.container.innerHTML = '<div style="color: red; padding: 20px;">Error: D3.js is not loaded.</div>';
            return;
        }
        this.container.innerHTML = '';
        Object.assign(this.container.style, {
            width: '100%',
            backgroundColor: '#fafafa',
            borderRadius: '8px',
            padding: '10px',
            boxSizing: 'border-box',
            display: 'flex',
            flexDirection: 'column'
        });

        const chartWrapper = document.createElement('div');
        chartWrapper.style.height = '520px';
        chartWrapper.style.width = '100%';
        this.container.appendChild(chartWrapper);

        const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svgEl.style.display = 'block';
        svgEl.style.width = '100%';
        svgEl.style.height = '100%';
        chartWrapper.appendChild(svgEl);
        this.svg = d3.select(svgEl);

        const legendContainer = document.createElement('div');
        this.container.appendChild(legendContainer);

        this.legend = new RiverLegend(legendContainer, {
            items: this.topics,
            colorScale: this.colorScale,
            onActivate: (name) => this.setActiveTopic(name)
        });

        this.render();
        window.addEventListener('resize', () => this.render());
    }

    setActiveTopic(name) {
        this.activeTopic = name;
        this._updateStyles();
        if (this.legend) this.legend.update(name);
    }

    _updateStyles() {
        if (!this.svg) return;

        const paths = this.svg.selectAll(".stream-layer");
        const tooltips = d3.select("body").selectAll(".river-tooltip");

        if (this.activeTopic) {
            paths.transition().duration(200)
                .style("opacity", d => d.key === this.activeTopic ? 1 : 0.2)
                .style("stroke", d => d.key === this.activeTopic ? "#333" : "none")
                .style("stroke-width", d => d.key === this.activeTopic ? "1px" : "0px");
        } else {
            paths.transition().duration(200)
                .style("opacity", 0.85)
                .style("stroke", "none");
            tooltips.style("opacity", 0);
        }
    }

    render() {
        if (!this.effectiveLength || !this.topics || this.topics.length === 0 || !this.svg) return;

        const containerWidth = this.container.clientWidth || 800;
        const binCount = Math.max(15, Math.min(60, Math.floor(containerWidth / 40)));

        let data = calculateBins(binCount, this.topics, 0, this.effectiveLength);
        data = smoothBins(data, this.topics);
        data = estimateCharacterCounts(data, this.topics);

        if (!data.length) return;

        this.svg.selectAll("*").remove();

        const width = Math.max(containerWidth, 600);
        const height = 500;
        const margin = { top: 30, right: 30, bottom: 50, left: 60 };
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        this.svg
            .attr("width", width)
            .attr("height", height)
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("preserveAspectRatio", "xMidYMid meet");

        const g = this.svg.append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        const totalSentencesPerTopic = {};
        this.topics.forEach(topic => {
            totalSentencesPerTopic[topic.name] = topic.sentences ? topic.sentences.length : 0;
        });

        const stackedData = d3.stack()
            .offset(d3.stackOffsetWiggle)
            .order(d3.stackOrderInsideOut)
            .keys(this.keys)
            (data);

        const maxVal = d3.max(stackedData, layer => d3.max(layer, d => d[1]));
        const minVal = d3.min(stackedData, layer => d3.min(layer, d => d[0]));

        const x = d3.scaleLinear().domain([0, this.effectiveLength]).range([0, innerWidth]);
        const y = d3.scaleLinear().domain([minVal, maxVal]).range([innerHeight, 0]);

        const area = d3.area()
            .curve(d3.curveBasis)
            .x(d => x((d.data.rangeStart + d.data.rangeEnd) / 2))
            .y0(d => y(d[0]))
            .y1(d => y(d[1]));

        const tooltip = d3.select("body").selectAll(".river-tooltip").data([0])
            .join("div")
            .attr("class", "river-tooltip")
            .style("position", "absolute")
            .style("background", "rgba(255, 255, 255, 0.95)")
            .style("border", "1px solid #ccc")
            .style("border-radius", "4px")
            .style("padding", "8px 12px")
            .style("font-size", "12px")
            .style("pointer-events", "none")
            .style("opacity", 0)
            .style("box-shadow", "0 2px 4px rgba(0,0,0,0.1)")
            .style("z-index", "1000");

        const self = this;
        g.selectAll(".stream-layer")
            .data(stackedData)
            .enter()
            .append("path")
            .attr("class", "stream-layer")
            .style("fill", d => this.colorScale(d.key))
            .attr("d", area)
            .style("opacity", 0.85)
            .on("mouseover", function (event, d) {
                self.setActiveTopic(d.key);
                const totalSentences = totalSentencesPerTopic[d.key];
                tooltip.style("opacity", 1)
                    .html(`<strong>${d.key}</strong><br/>Total: ${totalSentences} sentences`)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mousemove", function (event) {
                tooltip.style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", function (event, d) {
                self.setActiveTopic(null);
                tooltip.style("opacity", 0);
            });

        const xAxisScale = d3.scaleLinear().domain([0, this.effectiveLength]).range([0, innerWidth]);
        g.append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${innerHeight})`)
            .call(d3.axisBottom(xAxisScale)
                .ticks(Math.min(10, Math.floor(innerWidth / 80)))
                .tickFormat(d => `${Math.round(d)}`));

        g.append("text")
            .attr("class", "x-axis-label")
            .attr("x", innerWidth / 2)
            .attr("y", innerHeight + 40)
            .style("text-anchor", "middle")
            .style("font-size", "12px")
            .style("fill", "#666")
            .text("Number of Sentences");

        const yAxisScale = d3.scaleLinear().domain([minVal, maxVal]).range([innerHeight, 0]);
        g.append("g")
            .attr("class", "y-axis")
            .call(d3.axisLeft(yAxisScale)
                .ticks(5)
                .tickFormat(d => {
                    const absVal = Math.abs(d);
                    return absVal >= 1000 ? d3.format(".1s")(absVal) : d3.format(".0f")(absVal);
                }));

        g.append("text")
            .attr("class", "y-axis-label")
            .attr("transform", "rotate(-90)")
            .attr("x", -innerHeight / 2)
            .attr("y", -45)
            .style("text-anchor", "middle")
            .style("font-size", "12px")
            .style("fill", "#666")
            .text("Number of Characters (Estimated)");

        // Stream labels
        const labelData = stackedData.map(series => {
            let maxThickness = 0, maxIndex = 0;
            series.forEach((point, i) => {
                const thickness = point[1] - point[0];
                if (thickness > maxThickness) {
                    maxThickness = thickness;
                    maxIndex = i;
                }
            });
            if (series.length === 0 || maxThickness < 0.1) return null;
            return {
                key: series.key,
                x: x(data[maxIndex].x),
                y: y((series[maxIndex][0] + series[maxIndex][1]) / 2),
                thickness: maxThickness
            };
        }).filter(d => d !== null);

        labelData.sort((a, b) => b.thickness - a.thickness);
        const topLabels = labelData.slice(0, Math.min(8, labelData.length));

        g.selectAll(".stream-label")
            .data(topLabels)
            .enter()
            .append("text")
            .attr("class", "stream-label")
            .attr("x", d => d.x)
            .attr("y", d => d.y)
            .text(d => d.key)
            .style("text-anchor", "middle")
            .style("alignment-baseline", "middle")
            .style("font-size", "11px")
            .style("font-weight", "600")
            .style("fill", "#333")
            .style("pointer-events", "none")
            .style("text-shadow", "1px 1px 0px white, -1px -1px 0px white, 1px -1px 0px white, -1px 1px 0px white");

        this.svg.append("text")
            .attr("x", width / 2)
            .attr("y", 18)
            .style("text-anchor", "middle")
            .style("font-size", "14px")
            .style("font-weight", "bold")
            .style("fill", "#333")
            .text("Topic Distribution Across Article");

        this.legend.render();
    }
}
