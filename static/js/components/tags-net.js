export default class TagsNet {
    constructor(container_id, event_system) {
        this.ES = event_system;
        this._state = {
            tags: new Map(),
        }
        this._container = document.getElementById(container_id);
        this._network = null;
        this.updateNet = this.updateNet.bind(this);
        this.loadTagNet = this.loadTagNet.bind(this);
    }

    loadTagNet(event) {
    console.log(event);
        if (event && event.nodes && event.nodes.length) {
            this.ES.trigger(this.ES.LOAD_TAG_NET, event.nodes[0]);
        }
    }

    getNetData(state) {
        let nodes = [],
            edges = [];

        for (let tag_data of state.tags) {
            let tag = tag_data[1];
            nodes.push({
                id: tag.tag,
                label: tag.tag
            });
            for (let edge of tag.edges) {
                edges.push({
                    from: tag.tag,
                    to: edge
                });
            }
        }

        return {nodes: nodes, edges: edges};
    }

    updateNet(state) {
        this._state = state;
        let {nodes, edges} = this.getNetData(this._state);
        this.renderNet(nodes, edges);
    }

    renderNet(nodes, edges) {
        if (nodes && nodes.length) {
            let data = {
                    nodes: nodes,
                    edges: edges
                },
                options = {
                    physics: {
                        enabled: false
                    },
                    layout: {
                        improvedLayout: false
                    }
                };
            if (this._network) {
                this._network.setData(data);
                this._network.redraw();
            } else {
                this._network = new vis.Network(this._container, data, options);
                this._network.on('doubleClick', this.loadTagNet);
            }
        } else {
            alert('Not data');
        }
    }

    bindEvents() {
        this.ES.bind(this.ES.TAGS_NET_UPDATED, this.updateNet);
    }

    start() {
        this.bindEvents();
    }
}