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
        };
        let sentiment = '';

        if (this.state.tag.sentiment && this.state.tag.sentiment.length) {
            sentiment = this.state.tag.sentiment[0].replace('/', '_');
        }
        let hide_tag_info_link = false;
        if (this.props.is_bigram) {
            hide_tag_info_link = true;
        } else if (this.props.is_entity) {
            hide_tag_info_link = this.state.tag.tag.search(/\s/) !== -1;
        }
        let sub_tags = [];
        if (hide_tag_info_link) {
            let subs = this.state.tag.tag.split(" ");
            for (let i = 0; i < subs.length; i++) {
                const tag = subs[i];
                sub_tags.push(
                    <a href={'/tag-info/' + encodeURIComponent(tag)} key={`st_${this.state.tag.tag}_${tag}_${i}`} title={tag} className="cloud_sub_item_title">
                        ...
                    </a>
                )
            }
        }
        let sents_link = <a href={"/sentences/with/tags/" + encodeURIComponent(this.state.tag.tag)} className="tag_sentences_link">sents</a>;
        let ctx_link = <a href={"/context-tags/" + encodeURIComponent(this.state.tag.tag)} className="context_tags_link">ctx</a>;

        return (
            <div style={style}>
                <a name={this.state.tag.tag}></a>
                <li className={'cloud_item ' + sentiment}>
                    <a href={this.state.tag.url} className="cloud_item_title">
                        {this.state.tag.tag}
                    </a> ({this.state.tag.count})<br />
                    {sub_tags}
                    {(sub_tags.length)? sents_link: ""}
                    {(sub_tags.length)? ctx_link: ""}
                    {(sub_tags.length)? <br />: ""}
                    ({this.state.tag.words.join(', ')})<br />
                    {(hide_tag_info_link)? "": <a href={'/tag-info/' + this.state.tag.tag} className="get_tag_siblings">...</a>}
                    {(hide_tag_info_link)? "": sents_link}
                </li>
            </div>
        )
    }
};
