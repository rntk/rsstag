import React, { useEffect, useState } from 'react';

/** @param {HTMLElement} snippet @returns {HTMLElement} */
function createPostGroup(snippet) {
  const doc = snippet.ownerDocument;
  const group = doc.createElement('article');
  group.className = 'post-snippets__post';
  group.dataset.postId = snippet.dataset.postId || '';
  const header = doc.createElement('header');
  header.className = 'post-snippets__post-header';
  const title = doc.createElement('h3');
  title.className = 'post-snippets__post-title';
  title.textContent =
    snippet.querySelector('.snippet-source-info')?.textContent.trim() || 'Untitled post';
  const links = doc.createElement('div');
  links.className = 'post-snippets__post-links';
  snippet.querySelectorAll('.snippet-tag-context, .snippet-tag-original').forEach((link) => {
    const copy = link.cloneNode(true);
    if (copy.target === '_blank') copy.rel = 'noopener noreferrer';
    links.appendChild(copy);
  });
  const count = doc.createElement('span');
  count.className = 'post-snippets__post-count';
  header.append(title, count, links);
  group.appendChild(header);
  return group;
}

/** @param {HTMLElement} snippet @param {string} topic @param {number} number @returns {void} */
function prepareExcerpt(snippet, topic, number) {
  snippet
    .querySelectorAll('.snippet-tag-context, .snippet-tag-original')
    .forEach((link) => link.remove());
  snippet.querySelectorAll('span.toggle-read-btn, span.show-snippet-tags-btn').forEach((action) => {
    const button = snippet.ownerDocument.createElement('button');
    Array.from(action.attributes).forEach((attribute) =>
      button.setAttribute(attribute.name, attribute.value)
    );
    button.type = 'button';
    button.classList.add('source-tag-button');
    button.textContent = action.textContent;
    action.replaceWith(button);
  });
  const meta = snippet.querySelector('.snippet-primary-meta');
  if (!meta) return;
  meta.textContent = '';
  const label = snippet.ownerDocument.createElement('span');
  label.className = 'post-snippets__excerpt-label';
  label.textContent = `Excerpt ${number}`;
  meta.appendChild(label);
  if (topic) {
    const badge = snippet.ownerDocument.createElement('span');
    badge.className = 'post-snippets__topic';
    badge.textContent = topic;
    meta.appendChild(badge);
  }
}

/**
 * Group across topics by post ID, keeping posts and excerpts in first-seen order.
 * @param {HTMLElement} container
 * @returns {{html: string, posts: number, snippets: number}}
 */
function groupSnippets(container) {
  const items = Array.from(container.querySelectorAll('.snippet-item'));
  if (!items.length) return { html: container.outerHTML, posts: 0, snippets: 0 };
  /** @type {Map<string | HTMLElement, HTMLElement>} */
  const groups = new Map();
  items.forEach((snippet) => {
    const key = snippet.dataset.postId || snippet;
    const topic =
      snippet.closest('.topic-card')?.querySelector('.topic-title')?.textContent.trim() || '';
    if (!groups.has(key)) groups.set(key, createPostGroup(snippet));
    const group = groups.get(key);
    const number = group.childElementCount;
    prepareExcerpt(snippet, topic, number);
    group.appendChild(snippet);
    group.querySelector('.post-snippets__post-count').textContent =
      `${number} ${number === 1 ? 'snippet' : 'snippets'}`;
  });
  container.replaceChildren(...groups.values());
  return { html: container.outerHTML, posts: groups.size, snippets: items.length };
}

/** @param {{url: string}} props @returns {React.ReactElement} */
export default function PostSnippets({ url }) {
  const [content, setContent] = useState(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setContent(null);
    setError(false);

    /** @returns {Promise<void>} */
    async function load() {
      try {
        const response = await fetch(url, {
          credentials: 'same-origin',
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`Snippets request failed (${response.status})`);
        const html = await response.text();
        if (controller.signal.aborted) return;
        const page = new DOMParser().parseFromString(html, 'text/html');
        const snippets = page.getElementById('snippets_container');
        if (!snippets) throw new Error('Snippets response is missing its content');
        window.TAG_WORDS = JSON.parse(snippets.dataset.tagWords || '[]');
        setContent(groupSnippets(snippets));
      } catch (err) {
        if (controller.signal.aborted) return;
        console.error('Unable to load snippets', err);
        setError(true);
      }
    }

    load();
    return () => controller.abort();
  }, [url, attempt]);

  if (error) {
    return React.createElement(
      'div',
      { role: 'alert' },
      'Unable to load snippets. ',
      React.createElement(
        'button',
        { type: 'button', onClick: () => setAttempt(attempt + 1) },
        'Retry'
      )
    );
  }
  if (content === null) {
    return React.createElement('p', { role: 'status' }, 'Loading snippets…');
  }
  return React.createElement(
    'section',
    { className: 'post-grouped-snippets-page post-snippets', 'aria-label': 'Snippets' },
    React.createElement(
      'div',
      { className: 'post-snippets__toolbar' },
      React.createElement(
        'div',
        { className: 'post-snippets__summary' },
        React.createElement('h2', null, 'Snippets'),
        content.snippets > 0
          ? React.createElement(
              'p',
              null,
              `${content.snippets} snippets from ${content.posts} ${content.posts === 1 ? 'post' : 'posts'}`
            )
          : null
      ),
      React.createElement(
        'button',
        { type: 'button', className: 'batch-read-btn', 'data-action': 'read-all' },
        'Read all snippets'
      ),
      React.createElement(
        'button',
        { type: 'button', className: 'batch-read-btn', 'data-action': 'unread-all' },
        'Unread all snippets'
      ),
      React.createElement(
        'a',
        { href: url, target: '_blank', rel: 'noopener noreferrer' },
        'Open in new page ↗'
      )
    ),
    React.createElement('div', { dangerouslySetInnerHTML: { __html: content.html } })
  );
}
