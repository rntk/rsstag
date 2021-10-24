'use strict';
import React from 'react';

export default class ReadAllButton extends React.Component{
    constructor(props) {
        super(props);
        this.state = {
            ids: [],
            readed: false
        };
        this.changePostsStatus = this.changePostsStatus.bind(this);
        this.updatePosts = this.updatePosts.bind(this);
    }

    updatePosts(state) {
        let new_state = {
            ids: Array.from(state.posts.keys()),
            readed: state.readed
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

    changePostsStatus(e) {
        let data = {
            ids: this.state.ids.slice(0),
            readed: !this.state.readed
        };
        this.props.ES.trigger(this.props.ES.CHANGE_POSTS_STATUS, data);
    }

    render() {
        return(
            <span onClick={this.changePostsStatus}>{this.state.readed? 'unread': 'read'} all</span>
        );
    }
};