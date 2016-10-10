'use strict';
import React from 'react';

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
        //subscribe
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.POSTS_UPDATED, this.updatePosts);
        //unsubscribe
    }

    clickReadButton(id, readed, e) {
        this.props.ES.trigger(this.props.ES.CHANGE_POSTS_STATUS,{ids: [id], readed: !readed});
    }

    showPostLinks(id, e) {
        this.props.ES.trigger(this.props.ES.SHOW_POST_LINKS, id);
    }

    changePostsContentState(id, showed, e) {
        this.props.ES.trigger(this.props.ES.CHANGE_POSTS_CONTENT_STATE, {ids: [id], showed: !showed});
    }

    dangerHTML(post) {
        let html = {__html: ''};

        if (post.showed) {//add content clearing from scripts, iframes etc.
            html = {__html: post.post.content.content};
        }
        return(html);
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
                let read_button_class = (post.post.read)? 'read': 'unread',
                    links = '';

                if (post.links) {
                    let tags = post.links.tags.map(tag => {
                        return(
                            <a href={tag.url} key={tag.tag}>{tag.tag},&nbsp; </a>
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
                posts.push(
                    <div className="post" key={post.pos}><a name={'p' + post.pos}></a>
                        <h3 className="post_title">
                            <a className="post_title_link" href={post.post.url} target="_blank" dangerouslySetInnerHTML={{__html: post.post.content.title}}></a>
                        </h3>
                        <div className="post_meta">{post.category_title} | <b className="post_feed_title">{post.feed_title}</b> | {post.post.date}</div>
                        <div className={'post_content ' + post.showed? '': 'hide'} dangerouslySetInnerHTML={this.dangerHTML(post)}></div>
                        <div className="post_tools">
                            <span className="post_show_content" onClick={this.changePostsContentState.bind(this, post.pos, post.showed)}>{post.showed? 'Hide': 'Show'} post</span>
                            <span className="post_show_links" onClick={this.showPostLinks.bind(this, post.pos)}>Show links</span>
                            <span className={'read_button ' + read_button_class} onClick={this.clickReadButton.bind(this, post.pos, post.post.read)}>{read_button_class}</span>
                            <div className={'post_links_content ' + (post.links? '': 'hide')}>{links}</div>
                        </div>
                    </div>
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