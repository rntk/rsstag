export default class TagsNet {
    constructor(container_id, event_system) {
        this.ES = event_system;
        this._state = {
            tags: new Map(),
            main_tag: '',
            selected_tag: ''
        }
        this._container = document.getElementById(container_id);
        this._network = null;
        this._colors = new Map();
        this._positions = new Map();
        this.updateNet = this.updateNet.bind(this);
        this.loadTagNet = this.loadTagNet.bind(this);
        this.selectTag = this.selectTag.bind(this);
        this.moveTag = this.moveTag.bind(this);
    }

    getRandomColorHEX() {
        let symbols = '0123456789abcdef',
            inverted_symbols = 'fedcba9876543210',
            len = symbols.length - 1,
            color = '#',
            inverted_color = '#';

        for (let i = 0; i < 6; i++) {
            let indx = Math.random() * len;
            color += symbols.charAt(indx);
            inverted_color += inverted_symbols.charAt(indx);
        }

        return {color: color, inverted_color: inverted_color};
    }

    getRandomCoords(point) {
        let coords = {x: 0, y: 0},
            x_delta = 200,
            y_delta = 200;

        if (point !== undefined) {
            let from = point.x - x_delta,
                to = point.x + x_delta;

            coords.x = (Math.random() * (to - from)) + from;
            from = point.y - y_delta;
            to = point.y + y_delta;
            coords.y = (Math.random() * (to - from)) + from;
        } else {
            coords.x = Math.random() * 2000;
            coords.y = Math.random() * 2000;
        }
        return coords;
    }

    initCoords(state) {
        for (let tag_item of state.tags) {
            let tag = tag_item[1];

            if (!this._positions.has(tag.tag)) {
                let pos = this.getRandomCoords();

                this._positions.set(tag.tag, pos);
                for (let edge of tag.edges) {
                    if (!this._positions.has(edge)) {
                        this._positions.set(edge, this.getRandomCoords(pos));
                    }
                }
            }
        }
    }

    loadTagNet(event) {
        if (event && event.nodes && event.nodes.length) {
            this.ES.trigger(this.ES.LOAD_TAG_NET, event.nodes[0]);
        }
    }

    selectTag(event) {
        if (event.nodes[0] !== this._state.selected_tag) {
            this.ES.trigger(this.ES.NET_TAG_SELECTED, event.nodes[0]);
        }
    }

    moveTag(event) {
        let tag_id = event.nodes[0],
            pos = this._network.getPositions([tag_id]);

        this._positions.set(tag_id, pos[tag_id]);
        this.selectTag(event);
    }

    getNetData(state) {
        let nodes = [],
            edges = [];

        for (let tag_data of state.tags) {
            let tag = tag_data[1];
            if (!tag.hidden) {
                if (!this._colors.has(tag.tag)) {
                    this._colors.set(tag.tag, this.getRandomColorHEX());
                }
                let {color, inverted_color} = this._colors.get(tag.tag);
                let node = {
                    id: tag.tag,
                    label: tag.tag,
                    title: tag.tag,
                    physics: true,
                    group: tag.group,
                    shape: 'dot',
                    shadow: {
                        enabled: true,
                        size: 3
                    },
                    color: {
                        border: color,
                        background: color
                    },
                }
                if (!this._positions.has(tag.tag)) {
                    this._positions.set(tag.tag, this.getRandomCoords());
                }
                let pos = this._positions.get(tag.tag);

                node.x = pos.x;
                node.y = pos.y;
                nodes.push(node);
                for (let edge of tag.edges) {
                    if (!state.tags.get(edge).hidden) {
                        edges.push({
                            from: tag.tag,
                            to: edge,
                            color: {
                                color: color,
                                highlight: '#ff0000'
                            }
                        });
                    }
                }
            }
        }

        return {nodes: nodes, edges: edges};
    }

    updateNet(state) {
        if (this._state.selected_tag === state.selected_tag) {
            this.initCoords(state);
            let {nodes, edges} = this.getNetData(state);
            this.renderNet(nodes, edges);
        }
        this._state = state;
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
                    },
                    edges: {
                        selectionWidth: width => {return width * 4;}
                    }
                };
            if (this._network) {
                this._network.setData(data);
                this._network.redraw();
            } else {
                this._network = new vis.Network(this._container, data, options);
                this._network.on('doubleClick', this.loadTagNet);
                this._network.on('selectNode', this.selectTag);
                this._network.on('dragEnd', this.moveTag);
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