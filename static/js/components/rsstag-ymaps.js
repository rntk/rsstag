export default class RssTagYMap {
    constructor(map_id, ES) {
        this.y_map = null;
        this.map_id = map_id;
        this.ES = ES;
        this.geo_cities = null;
        this.geo_countries = null;
        this.state = {};
    }

    updateMap(state) {
        this.processCitiesState(state);
        this.processCountriesState(state);
    }

    processCitiesState(state) {
        if (state.show_cities) {
            if ((this.geo_cities === null) || (this.geo_cities.getLength() === 0)) {
                this.geo_cities = new ymaps.GeoObjectCollection();
                for (let tag of state.cities) {
                    this.geo_cities.add(new ymaps.Placemark([tag[1].city.co[1], tag[1].city.co[0]], {
                        hintContent: tag[1].tag
                    }));
                }
            }
            this.y_map.geoObjects.add(this.geo_cities);
        } else {
            if (this.geo_cities !== null) {
                this.geo_cities.removeAll();
            }
        }
    }

    processCountriesState(state) {
        if (state.show_countries) {
            if ((this.geo_countries === null) || (this.geo_countries.getLength() === 0)) {
                this.geo_countries = new ymaps.GeoObjectCollection();
                for (let tag of state.countries) {
                    this.geo_countries.add(new ymaps.Placemark([tag[1].country.co[1], tag[1].country.co[0]], {
                        hintContent: tag[1].tag
                    }));
                }
            }
            this.y_map.geoObjects.add(this.geo_countries);
        } else {
            if (this.geo_countries !== null) {
                this.geo_countries.removeAll();
            }
        }
    }

    bindEvents() {
        this.ES.bind(this.ES.MAP_UPDATED, this.updateMap.bind(this));
    }

    isReadyToStart() {
        return (ymaps && ymaps.Map);
    }

    start() {
        this.y_map = new window.ymaps.Map(this.map_id, {
            center: [46.91252944, 7.98097972],
            zoom: 2
        });
        this.bindEvents();
    }

}