'use strict';
import React from 'react';
import TagItem from '../components/tag-item.js';

export default class TagsList extends React.Component{
    constructor(props) {
        super(props);
        this.updateTags = this.updateTags.bind(this);
    }

    updateTags(state) {
        this.setState(state);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.TAGS_UPDATED, this.updateTags);
        //subscribe
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.TAGS_UPDATED, this.updateTags);
        //unsubscribe
    }

    render() {
        if (this.state && this.state.tags.size) {
            let tags = [];

            for (let tag_item of this.state.tags) {
                let tag = tag_item[1];

                tags.push(
                    <TagItem key={tag.tag} tag={tag} tags={this.state.tags} tag_hash={this.state.tag_hash} ES={this.props.ES} uniq_id={tag.tag} is_bigram={this.props.is_bigram} />
                );
            }
            return(
                <ol className="cloud">
                    {tags}
                </ol>
            );
        } else {
            return(<p>No tags</p>);
        }
    }
};