'use strict';
import React from 'react';

export default class TagItem extends React.Component{
    constructor(props) {
        super(props);
        this.state = {tag: props.tag};
        this.changeSiblingsState = this.changeSiblingsState.bind(this, this.state.tag.tag);
    }

    changeSiblingsState(tag) {
        this.props.ES.trigger(this.props.ES.CHANGE_TAG_SIBLINGS_STATE, tag);
    }

    isRenderedInChain(uniq_id, tag) {
        return (uniq_id.search(`.*_${tag}_.*`) !== -1);
    }

    render() {
        let siblings_button = '',
            siblings = [],
            style= {
                display: 'inline-block'
            },
            div_class_name = '';


        if (this.state.tag.siblings) {
            div_class_name = 'cloud_item_group';
            this.state.tag.siblings.forEach(sibling => {
                let tag = this.props.tags.get(sibling),
                    key = this.props.uniq_id + '_' + tag.tag;

                if (('parent' in tag) && !this.isRenderedInChain(this.props.uniq_id, tag.tag)) {
                    siblings.push(
                        <TagItem key={key} tag={tag} tags={this.props.tags} ES={this.props.ES} uniq_id={key} />
                    );
                }
            });
        } else {
            siblings_button = (<div><span className="get_tag_siblings" onClick={this.changeSiblingsState}>...</span></div>);
        }
        return (
            <div style={style} className={div_class_name}>
                <li className="cloud_item">
                    <a href={this.state.tag.url} className="cloud_item_title">
                        {this.state.tag.tag}
                    </a> ({this.state.tag.count})<br />
                    ({this.state.tag.words.join(', ')})<br />
                    {siblings_button}
                </li>
                {siblings}
            </div>
        )
    }
};
