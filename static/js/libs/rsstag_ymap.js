class RssTagYMap {
    constructor(map_id, ES) {
        this.y_map = null;
        this.map_id = map_id;
        this.ES = ES;
        this.geo_cities = [];
        this.geo_countries = [];
        this.state = {};
    }

    updateMap(state) {
        this.state = state;
        if (state.show_cities) {

        } else {

        }
    }

    bindEvents() {}
        this.ES.bind(this.props.ES.MAP_UPDATED, this.updateMap.bind(this));
    }

    start() {
        this.y_map = new ymaps.Map(this.map_id, {
            center: [46.91252944, 7.98097972],
            zoom: 2
        });
        this.bindEvents();
    }

}