'use strict';
import React from 'react';

export default class TagTool extends React.Component {
    constructor(props) {
        super(props);
        this.state = {};
        this.loadData = this.loadData.bind(this);
    }

    loadData() {
        this.props.ES.trigger(this.props.ES.CHANGE_TAG_SIBLINGS_STATE, this.props.tag.tag);
    }

    render() {
        return (<button onClick={this.loadData}>{this.props.title}</button>);
    }
};
