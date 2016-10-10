'use strict';
import React from 'react';

export default class PostsItem extends React.Component{
    constructor(props) {
        super(props);
        this.state = {
            post: props.post
        };
        this.clickReadButton = this.clickReadButton.bind(this);
        this.showPostLinks = this.showPostLinks.bind(this);
        this.changePostsContentState = this.changePostsContentState.bind(this);
    }

    clickReadButton() {
        this.props.ES.trigger(this.props.ES.CHANGE_POSTS_STATUS,{ids: [this.state.post.pos], readed: !this.state.post.post.read});
    }

    showPostLinks() {
        this.props.ES.trigger(this.props.ES.SHOW_POST_LINKS, this.state.post.pos);
    }

    changePostsContentState() {
        this.props.ES.trigger(this.props.ES.CHANGE_POSTS_CONTENT_STATE, {ids: [this.state.post.pos], showed: !this.state.post.showed});
    }

    dangerHTML(post) {
        let html = {__html: ''};

        if (post.showed) {//TODO: add content clearing from scripts, iframes etc.
            html = {__html: post.post.content.content};
        }
        return(html);
    }

    render() {
        if (this.state) {
            let links = '',
                post = this.state.post,
                read_button_class = (post.post.read)? 'read': 'unread';
            if (post.links) {
                let tags = post.links.tags.map(tag => {
                    return(
                        <a href={tag.url} key={tag.tag} style={{margin: '0 0.2em'}}> {tag.tag}</a>
                    );
                });
                links = (
                    <div>
                        <a href={post.links.c_url}>{post.links.c_title}</a>&nbsp;| &nbsp;
                        <a href={post.links.f_url}>{post.links.f_title}</a>&nbsp;| &nbsp;
                        <a href={post.links.p_url}>To site</a><br />{tags}
                    </div>
                );
            }

            return(
                <div className="post" key={post.pos}><a name={'p' + post.pos}></a>
                    <h3 className="post_title">
                        <a className="post_title_link" href={post.post.url} target="_blank" dangerouslySetInnerHTML={{__html: post.post.content.title}}></a>
                    </h3>
                    <div className="post_meta">{post.category_title} | <b className="post_feed_title">{post.feed_title}</b> | {post.post.date}</div>
                    <div className={'post_content ' + post.showed? '': 'hide'} dangerouslySetInnerHTML={this.dangerHTML(post)}></div>
                    <div className="post_tools">
                        <span className="post_show_content" onClick={this.changePostsContentState}>{post.showed? 'Hide': 'Show'} post</span>
                        <span className="post_show_links" onClick={this.showPostLinks}>Show links</span>
                        <span className={'read_button ' + read_button_class} onClick={this.clickReadButton}>{read_button_class}</span>
                        <div className={'post_links_content ' + (post.links? '': 'hide')}>{links}</div>
                    </div>
                </div>
            );
        } else {
            return(<p>No posts</p>);
        }
    }
};