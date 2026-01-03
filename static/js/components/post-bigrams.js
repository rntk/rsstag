'use strict';
import React from 'react';
import TagItem from '../components/tag-item.js';
import { stopwords } from '../libs/stopwords';

export function PostsBigrams(state) {
  if (!state || !state.posts) {
    return <p>No posts</p>;
  }
  let bi_grams = {};
  let freq = {};
  for (let item of state.posts) {
    let post = item[1];
    for (let tag of post.post.tags) {
      if (!(tag in freq)) {
        freq[tag] = 0;
      }
      freq[tag]++;
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
    let tags = bi.split(' ');
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
  });
  //bi_grams_l = bi_grams_l.slice(0, Number.parseInt(bi_grams_l.length / 2 + 1));
  let tags = [];
  let i = 0;
  for (let bi of bi_grams_l) {
    if (bi[1] < 2) {
      continue;
    }
    let tag = {
      tag: bi[0],
      count: bi[1],
      words: bi[0].split(' '),
      url: '/bi-gram/' + encodeURIComponent(bi[0]),
    };
    tags.push(
      <TagItem
        key={bi[0] + bi[1]}
        tag={tag}
        tags={[]}
        tag_hash={bi[0]}
        uniq_id={bi[0]}
        is_bigram={true}
      />
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
