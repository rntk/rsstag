'use strict';
import React from 'react';

export default class GeoMap extends React.Component{
    constructor(props) {
        super(props);
        this.state = {
            cities: new Map(),
            countries: new Map(),
            show_countries: false,
            show_cities: false
        };
        this.updateTools = this.updateTools.bind(this);
        this.changeVisibilityState = this.changeVisibilityState.bind(this);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.MAP_UPDATED, this.updateTools);
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.MAP_UPDATED, this.updateTools);
    }

    updateTools(state) {
        this.setState(state);
    }

    changeVisibilityState(e) {
        let el = e.target,
            visibility_state = Object.assign({}, this.state),
            changed = false;

        if (el.id === 'countries_checkbox') {
            visibility_state.show_countries = !this.state.show_countries;
            changed = true;
        } else if (el.id === 'cities_checkbox') {
            visibility_state.show_cities = !this.state.show_cities;
            changed = true;
        }

        if (changed) {
            this.props.ES.trigger(this.props.ES.CHANGE_MAP_OBJECTS_VISIBILITY, visibility_state);
        }

    }

    render() {
        return (
            <div>
                <label htmlFor="countries_checkbox">
                    <input type="checkbox" checked={this.state.show_countries} id="countries_checkbox" onChange={this.changeVisibilityState} />
                    Show countries ({this.state.countries.size})
                </label>
                <label htmlFor="cities_checkbox">
                    <input type="checkbox" checked={this.state.show_cities} id="cities_checkbox" onChange={this.changeVisibilityState} />
                    Show cities ({this.state.cities.size})
                </label>
            </div>
        );
    }
};