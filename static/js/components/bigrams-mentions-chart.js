'use strict';

import {stopwords} from "../libs/stopwords";

export default class BiGramsMentionsChart {
    constructor(container_id, event_system) {
        this.ES = event_system;
        this._container = document.querySelector(container_id);

        this.updateMentions = this.updateMentions.bind(this);
    }

    getDates(data, skip) {
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
        let sum_pos = Math.max(sums.length - 5);
        if (!skip) {
            sum_pos = 0;
        }
        let min_n = sums[sum_pos];
        if (min_n === 1) {
            min_n++;
        }
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

        return [dates, skip_bi];
    }

    updateMentions(data) {
        if (!data.bigrams) {
            this._container.innerHTML = "<p>No mentions</p>";
            return;
        }
        this._container.innerHTML = "";
        let [dates, skip_bi] = this.getDates(data, true);
        if (dates.size === 0) {
            [dates, skip_bi] = this.getDates(data, false);
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
        let labels = [];
        let bi_points = {};
        for (let p of series_data) {
            let d = p.rsstag_date;
            let l = `${d.getFullYear()}-${this.prettyDate(d.getMonth())}-${this.prettyDate(d.getDate())}`;
            labels.push(l);
            for (let bi in p) {
                if (bi === "rsstag_date") {
                    continue;
                }
                if (!(bi in bi_points)) {
                    bi_points[bi] = [];
                }
                bi_points[bi].push(p[bi]);
            }
        }
        let datasets = [];
        for (let bi in bi_points) {
            let sum = bi_points[bi].reduce((acc, v) => acc + v);
            datasets.push({
                label: `${bi} (${sum})`,
                backgroundColor: d3.interpolateCubehelixDefault(Math.random()),
                data: bi_points[bi]
            });
        }
        let dtset = {
            labels: labels,
            datasets: datasets
        };
        let ctx = document.createElement("canvas");
        this._container.appendChild(ctx);
        let ch = new Chart(ctx.getContext("2d"), {
            type: "bar",
            data: dtset,
            options: {
                tooltips: {
                    mode: 'index',
                    intersect: false
                },
                responsive: true,
                scales: {
                    xAxes: [{
                        stacked: true,
                    }],
                    yAxes: [{
                        stacked: true
                    }]
                }
            }
        });
    }

    prettyDate(n) {
        if (n === 0) {
            n = 1;
        }
        let zero = "";
        if (n < 10) {
            zero = "0";
        }

        return zero + n;
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
}