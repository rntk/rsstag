'use strict';
import React from 'react';
import PostItem from '../components/post-item.js';
import { LoadPosts } from '../components/load-posts.js';

export class PostsList extends React.Component {
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
}

export function PostsListS(state, ev_sys) {
  if (state) {
    let posts = [];
    let posts_n = 0;
    for (let item of state.posts) {
      let post = item[1];
      posts.push(
        <PostItem
          post={post}
          tag={state.group_title}
          key={post.pos}
          ES={ev_sys}
          current={state.current_post}
          words={state.words}
        />
      );
      posts_n++;
      if (posts_n >= state.posts_per_page * state.current_page) {
        break;
      }
    }
    let load_page = null;
    if (
      state.posts.size > state.posts_per_page &&
      state.current_page < Math.ceil(state.posts.size / state.posts_per_page)
    ) {
      load_page = <LoadPosts ES={ev_sys} />;
    }

    return (
      <div className="posts_list">
        <div className="posts">
          {posts.length ? posts : <p>No posts</p>}
          {load_page}
        </div>
      </div>
    );
  } else {
    return <p>No posts</p>;
  }
}
