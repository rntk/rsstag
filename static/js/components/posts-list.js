'use strict';
import React from 'react';
import PostItem from '../components/post-item.js';
import TagItem from '../components/tag-item.js';
import {stopwords} from "../libs/stopwords";

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
            let bi_grams = {};
            let freq = {}
            for (let item of this.state.posts) {
                let post = item[1];

                posts.push(
                    <PostItem post={post} tag={this.state.group_title} key={post.pos} ES={this.props.ES} current={this.state.current_post} />
                );
                for (let tag of post.post.tags) {
                    if (!(tag in freq)) {
                        freq[tag] = 0;
                    }
                    freq[tag]++
                }
                for (let bi of post.post.bi_grams) {
                    if (!(bi in bi_grams)) {
                        bi_grams[bi] = 0;
                    }
                    bi_grams[bi]++;
                }
            }
            let bi_grams_l = [];

            let stopw = stopwords();
            for (let bi in bi_grams) {
                let tags = bi.split(" ");
                if (stopw.has(tags[0]) || stopw.has(tags[1])) {
                    continue;
                }
                let coef = bi_grams[bi] / freq[tags[0]] + freq[tags[1]];
                bi_grams_l.push([bi, bi_grams[bi], coef]);
            }
            bi_grams_l.sort((a, b) => {
                if (a[2] < b[2]) {
                    return 1;
                } else {
                    return -1;
                }
            })
            //bi_grams_l = bi_grams_l.slice(0, Number.parseInt(bi_grams_l.length / 2 + 1));
            let tags = [];
            for (let bi of bi_grams_l) {
                if (bi[1] < 2) {
                    continue;
                }
                let tag = {
                    tag: bi[0],
                    count: bi[1],
                    words: bi[0].split(" "),
                    url: "/bi-gram/" + encodeURIComponent(bi[0])
                }
                tags.push(
                    <TagItem key={bi[0]} tag={tag} tags={[]} tag_hash={bi[0]} uniq_id={bi[0]} is_bigram={true} />
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
                    <div className="posts">
                        <ol className="cloud">
                            {tags}
                        </ol>
                    </div>
                </div>
            );
        } else {
            return(<p>No posts</p>);
        }
    }
};