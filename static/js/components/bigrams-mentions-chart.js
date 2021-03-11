'use strict';

export default class BiGramsMentionsChart {
    constructor(container_id, event_system) {
        this.ES = event_system;
        this._container = document.querySelector(container_id);

        this.updateMentions = this.updateMentions.bind(this);
    }

    updateMentions(data) {
        let dates = new Set();
        let bigrams = {};
        for (let bi in data.bigrams) {
            if (!(bi in bigrams)) {
                bigrams[bi] = {};
            }
            for (let d in data.bigrams[bi]) {
                bigrams[bi][d] = data.bigrams[bi][d];
                dates.add(d);
            }
        }
        dates = Array.from(dates);
        dates.sort();
        let values = [];
        for (let bi in bigrams) {
            let v = [];
            let sm = 0;
            for (let d of dates) {
                if (!(d in bigrams[bi])) {
                    bigrams[bi][d] = 0;
                }
                v.push(bigrams[bi][d]);
                sm += bigrams[bi][d];
            }
            if (sm < 5) {
                continue;
            }
            values.push({
                label: bi,
                data: v
            });
        }

        this.renderChart(dates, values);
    }

    renderChart(labels, values) {
        let margin = ({top: 0, right: 20, bottom: 30, left: 20});
        let height = 500;
        let width = 1200;
        let xAxis = g => {
            g.attr("transform", `translate(0,${height - margin.bottom})`)
                .call(d3.axisBottom(x).ticks(width / 80).tickSizeOuter(0))
                .call(g => {return g.select(".domain").remove();});
        };
        let bigrams = [];
        for (let bi of values) {
            bigrams.push(bi.label);
        }
        let series_data = [];
        for (let i = 0; i < labels.length; i++) {
            let itm = {rsstag_date: Number.parseInt(labels[i])};
            for (let bi of values) {
                itm[bi.label] = bi.data[i];
            }
            series_data.push(itm);
        }
        let series = d3.stack()
            .keys(bigrams)
            .offset(d3.stackOffsetWiggle)
            .order(d3.stackOrderInsideOut)
            (series_data);
        console.log(series_data);
        let color = d3.scaleOrdinal()
            .domain(bigrams)
            .range(d3.schemeCategory10);

        let y = d3.scaleLinear()
            .domain([d3.min(series, d => d3.min(d, d => d[0])), d3.max(series, d => d3.max(d, d => d[1]))])
            .range([height - margin.bottom, margin.top]);
        let x = d3.scaleUtc()
            .domain(d3.extent(series_data, d => d.rsstag_date))
            .range([margin.left, width - margin.right]);
        let area = d3.area()
            .x(d => x(d.data.rsstag_date))
            .y0(d => y(d[0]))
            .y1(d => y(d[1]));
        const svg = d3.create("svg").attr("viewBox", [0, 0, width, height]);

        svg.append("g")
            .selectAll("path")
            .data(series)
            .join("path")
            .attr("fill", ({key}) => color(key))
            .attr("d", area)
            .append("title")
            .text(({key}) => key);

        svg.append("g").call(xAxis);

        let chart = svg.node();
        this._container.appendChild(chart);
    }

    bindEvents() {
        this.ES.bind(this.ES.BIGRAMS_MENTIONS_UPDATED, this.updateMentions);
    }

    start() {
        this.bindEvents();
    }
};