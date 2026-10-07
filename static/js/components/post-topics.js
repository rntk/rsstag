/* global AbortController, console, fetch */
import React, { useEffect, useRef, useState } from 'react';
import { FeedHierarchy } from './feed-hierarchy.js';

export const POSTS_TOPICS_ENDPOINT = '/api/posts-topics';

/**
 * Fetch the topic hierarchy of the given posts, narrowed to a tag when set.
 * @param {Array<string|number>} postIds
 * @param {string|null} tag
 * @param {AbortSignal} signal
 * @returns {Promise<{topics: object[], tag_words: string[], only_unread: boolean}>}
 */
export async function fetchPostsTopics(postIds, tag, signal) {
  const response = await fetch(POSTS_TOPICS_ENDPOINT, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ post_ids: postIds, tag: tag || '' }),
    signal,
  });
  if (!response.ok) throw new Error(`Topics request failed (${response.status})`);
  const payload = await response.json();
  if (!payload || !payload.data) throw new Error('Topics response is missing its data');
  return payload.data;
}

/**
 * Topics tab: the /hierarchy tree for the posts of the current page.
 * @param {{postIds: Array<string|number>, tag?: string|null}} props
 * @returns {React.ReactElement}
 */
export default function PostTopics({ postIds, tag = null }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const levelsRef = useRef(null);
  const treeRef = useRef(null);
  const idsKey = postIds.join(',');

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(false);
    fetchPostsTopics(postIds, tag, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.error('Unable to load topics', err);
        setError(true);
      });
    return () => controller.abort();
  }, [idsKey, tag, attempt]);

  useEffect(() => {
    if (!data || !treeRef.current) return undefined;
    const hierarchy = new FeedHierarchy({
      embedded: true,
      topics: data.topics,
      onlyUnread: data.only_unread,
      tagWords: data.tag_words,
      levelsEl: levelsRef.current,
      treeEl: treeRef.current,
    });
    hierarchy.init();
    return () => hierarchy.destroy();
  }, [data]);

  if (error) {
    return React.createElement(
      'div',
      { role: 'alert' },
      'Unable to load topics. ',
      React.createElement(
        'button',
        { type: 'button', onClick: () => setAttempt(attempt + 1) },
        'Retry'
      )
    );
  }
  if (data === null) {
    return React.createElement('p', { role: 'status' }, 'Loading topics…');
  }
  return React.createElement(
    'section',
    { className: 'post-topics', 'aria-label': 'Topics' },
    React.createElement('div', {
      ref: levelsRef,
      className: 'feed-hierarchy__levels',
      'aria-label': 'Hierarchy depth',
    }),
    React.createElement(
      'div',
      { className: 'post-topics__scroller' },
      React.createElement('div', {
        ref: treeRef,
        className: 'feed-hierarchy__tree',
        'aria-label': tag ? `Topics mentioning ${tag}` : 'Topics hierarchy',
      })
    )
  );
}
