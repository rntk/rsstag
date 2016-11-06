'use strict';
import React from 'react';

export default class TagNetTools extends React.Component{
    constructor(props) {
        super(props);
        this.changeTagSettings = this.changeTagSettings.bind(this);
        this.renderTools = this.renderTools.bind(this);
    }

    changeTagSettings(e) {
        if (this.state.tags.has(this.state.selected_tag)) {
            let tag = this.state.tags.get(this.state.selected_tag);

            tag.hidden = e.target.checked;
            this.props.ES.trigger(this.props.ES.NET_TAG_CHANGE, tag);
        }
    }

    renderTools(state) {
        this.setState(state);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.TAGS_NET_UPDATED, this.renderTools);
        //subscribe
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.TAGS_NET_UPDATED, this.renderTools);
        //unsubscribe
    }

    render() {
        let tools = <span></span>;
        if (this.state && this.state.tags.has(this.state.selected_tag)) {
            let tag = this.state.tags.get(this.state.selected_tag);

            tools = (<div>
                <span>Tag: {tag.tag}</span>
                <label htmlFor="hidden">
                    <input type="checkbox" checked={tag.hidden} id="hidden" onChange={this.changeTagSettings} />
                    Hide tag
                </label>
            </div>);
        }

        return(tools);
    }
};