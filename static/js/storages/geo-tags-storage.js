'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class GeoTagsStorage {
    constructor(event_system) {
        this.ES = event_system;
        this.state = {
            countries: new Map(),
            cities: new Map(),
            show_countries: false,
            show_cities: false
        }
    }

    normalizedTags(tags) {
        let tags_m = new Map();

        tags.forEach(tag => {
            tag.root = true;
            tags_m.set(tag.tag, tag);
        });

        return(tags_m);
    }

    fetchGeoTags() {
        let state = this.getState();

        if (window.initial_countries_list || window.initial_cities_list) {
            state.countries = this.normalizedTags(window.initial_countries_list);
            state.cities = this.normalizedTags(window.initial_cities_list);
            this.setState(state);
        }
    }

    getState() {
        return(Object.assign({}, this._state));
    }

    setState(state) {
        this._state = state;
        this.ES.trigger(this.ES.MAP_UPDATED, this.getState());
    }

    bindEvents() {
        this.ES.bind(this.ES.CHANGE_MAP_OBJECTS_VISIBILITY, this.changeVisibilityState.bind(this));
    }

    changeVisibilityState(visibility_state) {
        let state = this.getState(),
            changed = false;

        if (visibility_state) {
            if (visibility_state.show_cities !==  state.show_cities) {
                state.show_cities = visibility_state.show_cities
                changed = true;
            }
            if (visibility_state.show_countries !==  state.show_countries) {
                state.show_countries = visibility_state.show_countries
                changed = true;
            }
        }
        if (changed) {
            this.setState(state);
        }
    }

    errorMessage(msg) {
        console.log(msg);
        this.ES.trigger(this.TAGS_ERROR_MESSAGE, msg);
    }

    start() {
        this.bindEvents();
        this.fetchGeoTags();
    }
}