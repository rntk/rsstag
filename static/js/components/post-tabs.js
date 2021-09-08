'use strict';
import React from 'react';
import {PostsListS} from "./posts-list.js";
import WordTree from './wordtree.js';
import PostsWordsCloud from "./posts-wordscloud.js";
import {PostsBigrams} from "./post-bigrams.js";

const TAB_POSTS = "posts";
const TAB_WORDSTREE = "wordstree";
const TAB_BIGRAMS = "bigrams";
const TAB_WORDSCLOUD = "wordscloud";

export class PostTabs extends React.Component {
    constructor(props) {
        super(props);
        this.tabs = new Map();
        this.tabs.set(TAB_POSTS, "Posts");
        this.tabs.set(TAB_WORDSTREE, "Wordtree");
        this.tabs.set(TAB_BIGRAMS, "Bi-grams");
        this.tabs.set(TAB_WORDSCLOUD, "Wordcloud");
        this.state = {
            current: TAB_POSTS
        };
        const container_id = "#posts_page1";
        this._container = document.querySelector(container_id);
        this.wordtree = new WordTree(container_id, this.props.ES);
        this.wordtree.start();
        this.wordscloud = new PostsWordsCloud(container_id);

        this.onTabClick = this.onTabClick.bind(this);
        this.updatePosts = this.updatePosts.bind(this);
    }

    onTabClick(ev) {
        let tab = ev.target.getAttribute("data-tab");
        this.changeTab(tab);
    }

    render() {
        let tabs = [];
        for (let [name, title] of this.tabs) {
            let act = "";
            if (name === this.state.current) {
                act = " post_tab_active";
            }
            tabs.push(
                <li key={"tab_" + name} data-tab={name} onClick={this.onTabClick} className={"post_tab" + act}>
                    {title}
                </li>
            );
        }
        if (!this.state.posts) {
            return <ul>{tabs}</ul>;
        }
        let words = this.state.posts.words.join(', ');
        if (words) {
            words = `(${words})`;
        }
        let el = null;
        if (this.state.current === TAB_POSTS) {
            el = PostsListS(this.state.posts, this.props.ES);
        }
        if (this.state.current === TAB_BIGRAMS) {
            el = PostsBigrams(this.state.posts);
        }
        let res_el = (<div>
            <ul className="post_tabs_list">{tabs}</ul>
            <div className="group_title">
                <h3>{this.state.posts.group_title}&nbsp;</h3>
                {words? words: ''}
            </div>
            {el}
        </div>);
        this._container.innerHTML = "";
        if (this.state.current === TAB_WORDSTREE) {
            let dt = {texts: [], tag: this.state.posts.group_title};
            for (let [_, post] of this.state.posts.posts) {
                dt.texts.push(post.post.lemmas);
            }
            this.wordtree.updateWordTree(dt);
        }
        if (this.state.current === TAB_WORDSCLOUD) {
            this.wordscloud.updateWordsCloud(this.state.posts);
        }

        return res_el;
    }
    componentDidMount() {
        this.props.ES.bind(this.props.ES.POSTS_UPDATED, this.updatePosts);
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.POSTS_UPDATED, this.updatePosts);
    }

    updatePosts(data) {
        this.setState({posts: data});
    }

    changeTab(tab) {
        this.setState({current: tab});
    }
}