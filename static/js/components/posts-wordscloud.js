'use strict';
import cloud from "../libs/cloud.min";
import {stopwords} from "../libs/stopwords.js";

export default class PostsWordsCloud {
    constructor(container_id, event_system) {
        this.ES = event_system;
        this._container = document.querySelector(container_id);

        this.updateWordsCloud = this.updateWordsCloud.bind(this);
    }

    updateWordsCloud(data) {
        if (!data.posts) {
            return;
        }
        let all_words = {};
        let stopw = stopwords();
        for (let item of data.posts) {
            let words = item[1].post.lemmas.split(" ");
            for (let word of words) {
                if (stopw.has(word)) {
                    continue;
                }
                if (!(word in all_words)) {
                    all_words[word] = 0;
                }
                all_words[word]++;
            }
        }
        let data_words = [];
        let mn = 9999999;
        let mx = 0;
        for (let word in all_words) {
            let fr = all_words[word];
            if (fr > mx) {
                mx = fr;
            }
            if (fr < mn) {
                mn = fr;
            }
            data_words.push({
                text: word,
                size: fr
            });
        }
        const min_f = 8;
        const max_f = 130;
        data_words = data_words.map(el => {
            el.size = min_f + (((el.size - mn) * (max_f - min_f)) / (mx - mn));
            return el;
        });

        let cld = cloud();

        //.canvas(() => {return this._container.querySelector("canvas");})
        let draw = (words) => {
            let layout = cld;
            d3.select("#" + this._container.id).append("svg")
                .attr("width", layout.size()[0])
                .attr("height", layout.size()[1])
                .append("g")
                .attr("transform", "translate(" + layout.size()[0] / 2 + "," + layout.size()[1] / 2 + ")")
                .selectAll("text")
                .data(words)
                .enter().append("text")
                .style("font-size", (d) => {
                    return d.size;
                })
                .style("font-family", "Impact")
                .attr("text-anchor", "middle")
                .attr("transform", (d) => {
                    return "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")";
                })
                .text((d) => { return d.text; });
        };
        cld.size([1024, 1024]).fontSize(d => d.size).words(data_words).on("end", draw).start();
    }

    bindEvents() {
        this.ES.bind(this.ES.POSTS_UPDATED, this.updateWordsCloud);
    }

    start() {
        this.bindEvents();
    }
};