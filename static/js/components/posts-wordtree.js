'use strict';

export default class PostsWordTree {
    constructor(container_id, event_system) {
        this.ES = event_system;
        this._container = document.querySelector(container_id);

        this.updateWordTree = this.updateWordTree.bind(this);
    }

    updateWordTree(data) {
        if (data.group === "category") {
            return;
        }
        google.charts.load('current', {packages:['wordtree']});
        google.charts.setOnLoadCallback(() => {
            let tags = data.group_title.split(" ");
            let window = 10;
            for (let i = 0; i < tags.length; i++) {
                let tag = tags[i];
                let texts = [];
                let container = document.createElement("div");
                container.id = "wordtree" + i;
                this._container.appendChild(container);
                for (let item of data.posts) {
                    let post = item[1];
                    let words = post.post.lemmas.split(" ");
                    for (let j = 0; j < words.length; j++) {
                        if (tag !== words[j]) {
                            continue;
                        }
                        let start = j - window;
                        let end = j + window;
                        if (start < 0) {
                            start = 0;
                        }
                        if (end > words.length) {
                            end = words.length;
                        }
                        let text = words.slice(start, end).join(" ");
                        texts.push([text]);
                    }
                }
                let dt = google.visualization.arrayToDataTable(texts);
                let chart = new google.visualization.WordTree(container);
                let options = {
                    wordtree: {
                        format: 'implicit',
                        word: tag,
                        type: "double",
                        backgroundColor: "#d7d7af"
                    }
                };
                chart.draw(dt, options);
            }
        });
    }

    bindEvents() {
        this.ES.bind(this.ES.POSTS_UPDATED, this.updateWordTree);
    }

    start() {
        this.bindEvents();
    }
};