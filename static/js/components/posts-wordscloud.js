'use strict';
import cloud from "../libs/cloud.min";
import {stopwords} from "../libs/stopwords.js";

export default class PostsWordsCloud {
    constructor(container_id, event_system) {
        this.ES = event_system;
        this._container = document.querySelector(container_id);
        this._renderred = false;

        this.updateWordsCloud = this.updateWordsCloud.bind(this);
    }

    updateWordsCloud(data) {
        if (this._renderred) {
            return;
        }
        if (!data.posts) {
            return;
        }
        this._renderred = true;
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
        let data_words = []
        for (let word in all_words) {
            data_words.push({
                text: word,
                size: all_words[word]
            })
        }

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
                .style("font-size", function(d) { return d.size + "px"; })
                .style("font-family", "Impact")
                .attr("text-anchor", "middle")
                .attr("transform", function(d) {
                    return "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")";
                })
                .text(function(d) { return d.text; });
        };
        setTimeout(() => {
            cld.size([1024, 1024]).fontSize(d => d.size).words(data_words).on("end", draw).start();
        }, 1000);
    }

    bindEvents() {
        this.ES.bind(this.ES.POSTS_UPDATED, this.updateWordsCloud);
    }

    start() {
        this.bindEvents();
    }
};