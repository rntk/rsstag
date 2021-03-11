'use strict';

import {stopwords} from "../libs/stopwords";

export default class BiGramsMentionsChart {
    constructor(container_id, event_system) {
        this.ES = event_system;
        this._container = document.querySelector(container_id);

        this.updateMentions = this.updateMentions.bind(this);
    }

    updateMentions(data) {
        let skip_bi = new Set();
        let sums = new Set();
        for (let bi in data.bigrams) {
            let sum = 0;
            for (let d in data.bigrams[bi]) {
                sum += Number.parseInt(data.bigrams[bi][d]);
            }
            sums.add(sum);
        }
        sums = Array.from(sums);
        sums.sort();
        let stopw = stopwords();
        let sum_pos = Math.max(sums.length - 20, 0);
        let min_n = sums[sum_pos];
        for (let bi in data.bigrams) {
            let bis = bi.split(" ");
            if (stopw.has(bis[0]) || stopw.has(bis[1])) {
                skip_bi.add(bi);
                continue;
            }
            let sum = 0;
            for (let d in data.bigrams[bi]) {
                sum += data.bigrams[bi][d];
            }
            if (sum < min_n) {
                skip_bi.add(bi);
            }
        }
        let dates = new Set();
        for (let bi in data.bigrams) {
            if (skip_bi.has(bi)) {
                continue;
            }
            for (let d in data.bigrams[bi]) {
                dates.add(d);
            }
        }
        dates = Array.from(dates);
        dates.sort();
        let dates_aggr = {};
        let current = 0;
        let aggr = 3600 * 24 * 1000;
        for (let u of dates) {
            u *= 1000;
            let d = new Date();
            if ((current === 0) || ((current + aggr) < u)) {
                d.setTime(u);
                d.setMinutes(0);
                d.setMilliseconds(0);
                d.setSeconds(0);
                current = Number.parseInt(d.getTime() / 1000);
            }
            if (!(current in dates_aggr)) {
                dates_aggr[current] = new Set();
            }
            dates_aggr[current].add(Number.parseInt(u / 1000));
        }
        let series = [];
        for (let d in dates_aggr) {
            let itm = {};
            for (let bi in data.bigrams) {
                if (skip_bi.has(bi)) {
                    continue;
                }
                if (!(bi in itm)) {
                    itm[bi] = 0;
                }
                for (let dd of dates_aggr[d]) {
                    let v = 0;
                    if (dd in data.bigrams[bi]) {
                        v = Number.parseInt(data.bigrams[bi][dd]);
                    }
                    itm[bi] += v;
                }
            }
            let td = new Date();
            td.setTime(d * 1000);
            itm.rsstag_date = td;
            series.push(itm);
        }
        this.renderChart(series);
    }

    renderChart(series_data) {
        let margin = ({top: 0, right: 20, bottom: 30, left: 20});
        let height = 900;
        let width = 1200;
        let xAxis = g => {
            g.attr("transform", `translate(0,${height - margin.bottom})`)
                .call(d3.axisBottom(x).ticks(width / 80).tickSizeOuter(0))
                .call(g => {return g.select(".domain").remove();});
        };
        let bigrams = [];
        for (let d in series_data[0]) {
            if (d === "rsstag_date") {
                continue;
            }
            bigrams.push(d);
        }
        let series = d3.stack()
            .keys(bigrams)
            .offset(d3.stackOffsetWiggle)
            .order(d3.stackOrderInsideOut)
            (series_data);
        let color = d3.scaleOrdinal()
            .domain(bigrams)
            .range(bigrams.map(() => d3.interpolateCubehelixDefault(Math.random())));

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
        let legend = document.createElement("div");
        legend.innerHTML = this.renderLegend(color);
        this._container.appendChild(legend);
        this._container.appendChild(chart);
    }

    renderLegend(color) {
        let html = "";
        for (let bi of color.domain()) {
            html += `
                <div style="margin: 0 0.5em; display: inline-block; vertical-align: middle;">
                <div style="margin: 0 0.3em; display: inline-block; height: 1em; width: 1em; vertical-align: middle; background-color: ${color(bi)};"></div>${bi}</div>`;
        }

        return html;
    }


    bindEvents() {
        this.ES.bind(this.ES.BIGRAMS_MENTIONS_UPDATED, this.updateMentions);
    }

    start() {
        this.bindEvents();
    }
};