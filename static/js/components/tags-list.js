'use strict';
import React from 'react';

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

    changeSiblingsState(tag, e) {
        this.props.ES.trigger(this.props.ES.CHANGE_TAG_SIBLINGS_STATE, tag);
    }

    render() {
        if (this.state && this.state.tags.size) {
            let tags = [];

            for (let tag_item of this.state.tags) {
                let tag = tag_item[1],
                    siblings = [],
                    siblings_block = '';

                if (tag.siblings) {
                    siblings = tag.siblings.map(sibling => {
                        return(
                            <a className="cloud_item_title" key={'s_' + sibling.t} href={'/tag/' + encodeURIComponent(sibling.t)}>{sibling.t}({sibling.n}) </a>
                        );
                    });
                    if (siblings && siblings.length) {
                        siblings_block = (
                            <div className="tag_siblings">
                                {siblings}<br />
                                <span className="hide_tag_siblings" onClick={this.changeSiblingsState.bind(this, tag.tag)}>...</span>
                            </div>
                        );
                    }
                }
                tags.push(
                    <li className="cloud_item" key={tag.tag}>
                        <a href={tag.url} className="cloud_item_title">{tag.tag}</a> ({tag.count})<br />({tag.words.join(', ')})<br />
                        <span className="get_tag_siblings" onClick={this.changeSiblingsState.bind(this, tag.tag)}>...</span>
                        {siblings_block}
                    </li>
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