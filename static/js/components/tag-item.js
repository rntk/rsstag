'use strict';
import React from 'react';

export default class TagItem extends React.Component{
    constructor(props) {
        super(props);
        this.state = {tag: props.tag};
    }

    render() {
        let style= {
                display: 'inline-block'
            },
            sentiment = '';

        if (this.state.tag.sentiment && this.state.tag.sentiment.length) {
            sentiment = this.state.tag.sentiment[0].replace('/', '_');
        }
        let hide_tag_info_link = false;
        if (this.props.is_bigram) {
            hide_tag_info_link = true;
        } else if (this.props.is_entity) {
            hide_tag_info_link = this.state.tag.tag.search(/\s/) !== -1;
        }

        return (
            <div style={style}>
                <a name={this.state.tag.tag}></a>
                <li className={'cloud_item ' + sentiment}>
                    <a href={this.state.tag.url} className="cloud_item_title">
                        {this.state.tag.tag}
                    </a> ({this.state.tag.count})<br />
                    ({this.state.tag.words.join(', ')})<br />
                    {(hide_tag_info_link)? '': <a href={'/tag-info/' + this.state.tag.tag} className="get_tag_siblings">...</a>}
                </li>
            </div>
        )
    }
};
