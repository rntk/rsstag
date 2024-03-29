'use strict';

export default class WordTree {
    constructor(container_id, event_system) {
        this.ES = event_system;
        this._container = document.querySelector(container_id);

        this.updateWordTree = this.updateWordTree.bind(this);
    }

    updateWordTree(data) {
        if (!data.texts.length) {
            this._container.innerHTML = "<p>No texts</p>";
            return;
        }
        this._container.innerHTML = "";
        let texts = [];
        for (let txt of data.texts) {
            texts.push([txt]);
        }
        let tags = data.tag.split(" ");
        let dt = google.visualization.arrayToDataTable(texts);
        for (const tag of tags) {
            let container = document.createElement("div");
            this._container.appendChild(container);
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
    }

    bindEvents() {
        this.ES.bind(this.ES.WORDTREE_TEXTS_UPDATED, this.updateWordTree);
    }

    start() {
        google.charts.load('current', {packages:['wordtree']});
        this.bindEvents();
    }
}