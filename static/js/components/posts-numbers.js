'use strict';
import React from 'react';

export default class PostsNumbers extends React.Component{
    constructor(props) {
        super(props);
        this._default_state = {
            read: 0,
            unread: 0,
            all: 0
        };
        this.state = Object.assign({}, this._default_state);
        this.updateNumbers = this.updateNumbers.bind(this);
    }

    updateNumbers(posts_state) {
        let state = Object.assign({}, this._default_state);

        for (let item of posts_state.posts) {
            let post = item[1];
            if (post.post.read) {
                state.read++;
            } else {
                state.unread++;
            }
        }
        state.all = state.unread + state.read;
        this.setState(state);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.POSTS_UPDATED, this.updateNumbers);
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.POSTS_UPDATED, this.updateNumbers);
    }

    render() {
        if (this.state) {
            return (<p>{this.state.all} / {this.state.read}</p>)
        } else {
            return(<p>0/0</p>);
        }
    }
};