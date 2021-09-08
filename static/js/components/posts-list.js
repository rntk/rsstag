'use strict';
import React from 'react';
import PostItem from '../components/post-item.js';
import TagItem from '../components/tag-item.js';
import {stopwords} from "../libs/stopwords";

export class PostsList extends React.Component{
    constructor(props) {
        super(props);
        this.updatePosts = this.updatePosts.bind(this);
    }

    updatePosts(state) {
        this.setState(state);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.POSTS_UPDATED, this.updatePosts);
    }

    componentDidUpdate() {
        this.props.ES.trigger(this.props.ES.POSTS_RENDERED);
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.POSTS_UPDATED, this.updatePosts);
    }

    render() {
        return PostsListS(this.state, this.props.ES);
    }
};

export function PostsListS(state, ev_sys) {
    if (state) {
        let posts = [];
        for (let item of state.posts) {
            let post = item[1];
            posts.push(
                <PostItem post={post} tag={state.group_title} key={post.pos} ES={ev_sys} current={state.current_post} words={state.words} />
            );
        }

        return(
            <div className="posts_list">
                <div className="posts">
                    {posts.length? posts: <p>No posts</p>}
                </div>
            </div>
        );
    } else {
        return(<p>No posts</p>);
    }
}