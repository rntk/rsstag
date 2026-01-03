'use strict';
import React from 'react';
import TagItem from '../components/tag-item.js';
import { stopwords } from '../libs/stopwords';

export function PostsTags(state) {
  if (!state || !state.posts) {
    return <p>No posts</p>;
  }
  let freq = {};
  let tags_l = [];
  for (let item of state.posts) {
    let post = item[1];
    for (let tag of post.post.tags) {
      if (!(tag in freq)) {
        freq[tag] = 0;
        tags_l.push(tag);
      }
      freq[tag]++;
    }
  }
  tags_l.sort((a, b) => {
    if (freq[a] < freq[b]) {
      return 1;
    } else {
      return -1;
    }
  });
  let tags = [];
  for (let tg of tags_l) {
    let tag = {
      tag: tg,
      count: freq[tg],
      words: [tg],
      url: '/tag/' + encodeURIComponent(tg),
    };
    tags.push(
      <TagItem key={tg} tag={tag} tags={[]} tag_hash={tg} uniq_id={tg} is_bigram={false} />
    );
  }

  return (
    <div className="posts_list">
      <div className="posts">
        <ol className="cloud">{tags}</ol>
      </div>
    </div>
  );
}
