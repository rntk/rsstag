'use strict';
import React from 'react';
import PostItem from '../components/post-item.js';

export default class PostsList extends React.Component{
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
        if (this.state) {
            /*let words = this.state.words.map(word => {
                return(<span key={word}>{word}, </span>);
            });*/
            let words = this.state.words.join(', ');
            if (words) {
                words = `(${words})`;
            }
            let posts = [];
            for (let item of this.state.posts) {
                let post = item[1];

                posts.push(
                    <PostItem post={post} key={post.pos} ES={this.props.ES} current={this.state.current_post} />
                );
            }

            return(
                <div className="posts_list">
                    <div className="group_title">
                        <h3>{this.state.group_title}&nbsp;</h3>
                        {words? words: ''}
                    </div>
                    <div className="posts">
                        {posts.length? posts: <p>No posts</p>}
                    </div>
                </div>
            );
        } else {
            return(<p>No posts</p>);
        }
    }
};