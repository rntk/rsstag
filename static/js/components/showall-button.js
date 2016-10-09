'use strict';
import React from 'react';

export default class ShowAllButton extends React.Component{
    constructor(props) {
        super(props);
        this.state = {
            ids: [],
            showed: false
        }
        this.changePostsContentState = this.changePostsContentState.bind(this);
        this.updatePosts = this.updatePosts.bind(this);
    }

    updatePosts(state) {
        let new_state = {
            ids: Array.from(state.posts.keys()),
            showed: state.showed
        };
        this.setState(new_state);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.POSTS_UPDATED, this.updatePosts);
        //subscribe
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.POSTS_UPDATED, this.updatePosts);
        //unsubscribe
    }

    changePostsContentState(e) {
        let data = {
            ids: this.state.ids.slice(0),
            showed: !this.state.showed
        };
        this.props.ES.trigger(this.props.ES.CHANGE_POSTS_CONTENT_STATE, data);
    }

    render() {
        return(
            <span onClick={this.changePostsContentState}>{this.state.showed? 'hide': 'show'} all</span>
        );
    }
};