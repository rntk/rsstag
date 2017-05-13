'use strict';
import React from 'react';

export default class SettingsMenuButton extends React.Component{
    constructor(props) {
        super(props);
        this.changeMenuState = this.changeMenuState.bind(this);
    }

    changeMenuState(e) {
        let rect = e.target.getBoundingClientRect(),
            offset;

        offset = {
            top: rect.top + rect.height,
            right: document.body.offsetWidth - rect.left
        };
        this.props.ES.trigger(this.props.ES.CHANGE_SETTINGS_WINDOW_STATE, offset);
    }

    render() {
        return(
            <span className="main_menu_button" onClick={this.changeMenuState}>
                &equiv;
            </span>
        );
    }
};