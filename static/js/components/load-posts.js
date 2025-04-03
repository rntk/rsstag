'use strict';
import React from 'react';

export class LoadPosts extends React.Component{
    constructor(props) {
        super(props);
        this.loadMore = this.loadMore.bind(this);
    }

    loadMore() {
        this.props.ES.trigger(this.props.ES.LOAD_MORE_POSTS);
    }

    render() {
        return (
            <div className="load_more_posts">
                <button onClick={this.loadMore}>Load more</button>
            </div>
        );
    }
}
