'use strict';

document.addEventListener('DOMContentLoaded', () => {
  const tree = JSON.parse(document.getElementById('tag-explorer-data').textContent);
  const container = document.getElementById('tag-explorer-tree');
  const filterTabs = document.getElementById('tag-explorer-filter-tabs');
  const status = document.getElementById('tag-explorer-status');
  const selectionLabel = document.getElementById('tag-explorer-selection-label');
  const selectionPath = document.getElementById('tag-explorer-selection');
  const readFilter = document.getElementById('tag-explorer-read-filter');
  const clearFilter = document.getElementById('tag-explorer-clear-filter');
  const panels = {
    sentences: document.getElementById('tag-explorer-sentences'),
    posts: document.getElementById('tag-explorer-posts'),
  };
  const tabs = {
    sentences: document.getElementById('tag-explorer-sentences-tab'),
    posts: document.getElementById('tag-explorer-posts-tab'),
  };
  let activeButton = null;
  let request = null;
  let currentTab = 'sentences';
  let currentSelection = { kind: 'root' };
  let currentPage = 1;
  let displayed = { sentences: [], posts: [] };
  let currentTotal = 0;
  let onlyUnread = readFilter.dataset.onlyUnread === 'true';
  let busy = false;
  const relatedLinks = new Map();
  const previousPage = document.getElementById('tag-explorer-previous');
  const nextPage = document.getElementById('tag-explorer-next');
  const pageLabel = document.getElementById('tag-explorer-page');
  const readPage = document.getElementById('tag-explorer-read-page');
  const unreadPage = document.getElementById('tag-explorer-unread-page');
  const readAll = document.getElementById('tag-explorer-read-all');
  const unreadAll = document.getElementById('tag-explorer-unread-all');

  function updateFilterSummary() {
    const { kind, chain } = currentSelection;
    selectionLabel.textContent = kind === 'context' ? 'Context chain' : kind === 'topic' ? 'Topic' : 'Branch';
    selectionPath.textContent = kind === 'context'
      ? `${[tree.name, ...chain].join(' → ')} (either side of the tag)`
      : kind === 'topic' ? `${chain.join(' → ')} (including subtopics)` : 'All branches';
    readFilter.textContent = onlyUnread ? 'Unread only' : 'Read and unread';
    clearFilter.hidden = kind === 'root';
  }

  function selectTab(name) {
    currentTab = name;
    for (const key of Object.keys(tabs)) {
      const selected = key === name;
      tabs[key].setAttribute('aria-selected', String(selected));
      panels[key].hidden = !selected;
    }
    updateReadTools();
  }

  function addressableItems(items, kind) {
    return kind === 'posts' ? items : items.filter(entry => Number.isInteger(entry.number));
  }

  function updateReadTools() {
    const available = addressableItems(displayed[currentTab], currentTab);
    readPage.disabled = busy || !available.some(entry => !entry.read);
    unreadPage.disabled = busy || !available.some(entry => entry.read);
    readAll.disabled = busy || !currentTotal;
    // With only_unread every listed item is unread, so there is nothing to unmark.
    unreadAll.disabled = busy || !currentTotal || onlyUnread;
    for (const button of document.querySelectorAll('.tag-explorer__read-button')) {
      button.disabled = busy || button.dataset.unavailable === 'true';
    }
  }

  function setBusy(value) {
    busy = value;
    updateReadTools();
  }

  async function changeReadState(items, kind, read) {
    if (busy) return;
    const addressable = addressableItems(items, kind);
    if (!addressable.length) {
      status.textContent = `No ${kind} to mark ${read ? 'read' : 'unread'}.`;
      return;
    }
    const endpoint = kind === 'posts' ? '/read/posts' : '/read/snippets';
    const body = kind === 'posts'
      ? { ids: [...new Set(addressable.map(entry => entry.pid))], readed: read }
      : { selections: addressable.map(entry => ({ post_id: entry.pid, sentence_indices: [entry.number] })), readed: read };
    setBusy(true);
    status.textContent = `Marking ${addressable.length} ${kind} ${read ? 'read' : 'unread'}…`;
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const result = await response.json();
      if (!response.ok || result.data !== 'ok') throw new Error(result.error || 'Could not update read status.');
      busy = false;
      await loadResults();
    } catch (error) {
      status.textContent = error.message || 'Could not update read status.';
      setBusy(false);
    }
  }

  function resultsUrl(scope) {
    const url = new URL(window.location.href);
    url.searchParams.set('format', 'json');
    url.searchParams.set('selection', JSON.stringify(currentSelection));
    url.searchParams.set('page', String(currentPage));
    url.searchParams.set('scope', scope);
    return url;
  }

  async function changeAllReadState(kind, read) {
    if (busy) return;
    setBusy(true);
    status.textContent = `Collecting ${kind} on all pages…`;
    try {
      const response = await fetch(resultsUrl('all'));
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not load results.');
      busy = false;
      await changeReadState(data[kind].filter(entry => entry.read !== read), kind, read);
    } catch (error) {
      status.textContent = error.message || 'Could not update read status.';
      setBusy(false);
    }
  }

  function navigationLink(label, href) {
    if (!href) return null;
    try {
      const url = new URL(href, window.location.origin);
      if (!['http:', 'https:'].includes(url.protocol)) return null;
      const link = document.createElement('a');
      link.href = url.href;
      link.textContent = label;
      return link;
    } catch {
      return null;
    }
  }

  function renderMetadata(item, kind) {
    const row = document.createElement('div');
    row.className = 'tag-explorer__metadata';
    const metadata = item.metadata || {};
    const values = [
      ['Source', metadata.source, metadata.source_url],
      ['Provider', metadata.provider],
      ['Category', metadata.category, metadata.category_url],
      ['Date', metadata.date],
      ['Status', item.read ? 'Read' : 'Unread'],
    ];
    if (kind === 'sentences' && Number.isInteger(item.number)) values.push(['Sentence', `#${item.number}`]);
    for (const [label, value, href] of values) {
      if (!value) continue;
      const entry = document.createElement('span');
      entry.title = label;
      entry.setAttribute('aria-label', `${label}: ${value}`);
      const link = navigationLink(value, href);
      if (link) entry.append(link);
      else entry.textContent = value;
      row.append(entry);
    }
    return row;
  }

  function appendLinkGroup(panel, label, entries) {
    const links = entries.map(([text, href]) => navigationLink(text, href)).filter(Boolean);
    if (!links.length) return;
    const group = document.createElement('nav');
    group.className = 'tag-explorer__link-group';
    group.setAttribute('aria-label', label);
    const heading = document.createElement('strong');
    heading.textContent = label;
    group.append(heading, ...links);
    panel.append(group);
  }

  async function loadRelatedLinks(item, panel) {
    panel.textContent = 'Loading related links…';
    const key = String(item.pid);
    try {
      if (!relatedLinks.has(key)) {
        relatedLinks.set(key, (async () => {
          const response = await fetch(`/post-links/${encodeURIComponent(key)}`);
          const result = await response.json();
          if (!response.ok || !result.data) throw new Error(result.error || 'Could not load related links.');
          return result.data;
        })());
      }
      const links = await relatedLinks.get(key);
      panel.replaceChildren();
      appendLinkGroup(panel, 'Navigate', [
        ['Open post', item.url], [links.f_title || 'Source', links.f_url],
        [links.c_title || 'Category', links.c_url], ['Original', links.p_url],
        ['With context', links.ctx_url], ['Cluster', links.clst_url],
      ]);
      appendLinkGroup(panel, 'Topics', (links.topics || []).flatMap(topic => [
        [topic.topic || topic.name, topic.url],
        [`${topic.name || topic.topic} snippets`, topic.snippets_url],
      ]));
      appendLinkGroup(panel, 'Tags', (links.tags || []).map(tag => [tag.tag, tag.url]));
      panel.dataset.loaded = 'true';
    } catch (error) {
      relatedLinks.delete(key);
      panel.textContent = error.message || 'Could not load related links.';
      appendLinkGroup(panel, 'Navigate', [
        ['Open post', item.url], ['Original', item.metadata?.original_url],
      ]);
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.textContent = 'Retry';
      retry.addEventListener('click', () => loadRelatedLinks(item, panel));
      panel.append(retry);
    }
  }

  function animateDisclosure(details, summary, body) {
    let closeTimer = null;
    function finishClosing() {
      clearTimeout(closeTimer);
      closeTimer = null;
      if (!details.classList.contains('is-expanded')) details.open = false;
    }
    summary.addEventListener('click', event => {
      event.preventDefault();
      clearTimeout(closeTimer);
      closeTimer = null;
      const expanding = !details.classList.contains('is-expanded');
      if (expanding) {
        details.open = true;
        // Establish the collapsed layout before starting the CSS transition.
        body.getBoundingClientRect();
        details.classList.add('is-expanded');
        body.inert = false;
      } else {
        details.classList.remove('is-expanded');
        body.inert = true;
        if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) finishClosing();
        else closeTimer = setTimeout(finishClosing, 200);
      }
    });
    body.addEventListener('transitionend', event => {
      if (event.target === body && event.propertyName === 'grid-template-rows' && closeTimer !== null) finishClosing();
    });
    details.addEventListener('toggle', () => {
      if (closeTimer === null) {
        details.classList.toggle('is-expanded', details.open);
        body.inert = !details.open;
      }
    });
  }

  function renderItems(panel, items, kind) {
    panel.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'tag-explorer__empty';
      empty.textContent = kind === 'sentences' ? 'No sentences containing this tag match the current selection.' : 'No posts match this branch.';
      panel.append(empty);
      return;
    }
    for (const item of items) {
      const card = document.createElement('article');
      card.className = 'tag-explorer__card';
      const link = document.createElement('a');
      link.href = item.url;
      link.textContent = item.title;
      link.className = 'tag-explorer__title';
      const excerpt = document.createElement('p');
      excerpt.textContent = kind === 'sentences' ? item.text : item.excerpt;
      card.classList.toggle('is-read', item.read);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'tag-explorer__read-button';
      button.textContent = item.read ? 'Mark Unread' : 'Mark Read';
      button.setAttribute('aria-label', `${button.textContent}: ${item.title}${kind === 'sentences' ? `, sentence ${item.number ?? 'excerpt'}` : ''}`);
      if (kind === 'sentences' && !Number.isInteger(item.number)) {
        button.disabled = true;
        button.dataset.unavailable = 'true';
        button.title = 'Sentence read status is unavailable for this post';
      } else {
        button.addEventListener('click', () => changeReadState([item], kind, !item.read));
      }
      const details = document.createElement('details');
      details.className = 'tag-explorer__item-tools';
      const summary = document.createElement('summary');
      summary.textContent = 'Links & actions';
      const links = document.createElement('div');
      links.className = 'tag-explorer__related-links';
      links.setAttribute('aria-live', 'polite');
      const body = document.createElement('div');
      body.className = 'tag-explorer__item-tools-body';
      const content = document.createElement('div');
      content.className = 'tag-explorer__item-tools-content';
      const scroll = document.createElement('div');
      scroll.className = 'tag-explorer__item-tools-scroll';
      scroll.tabIndex = 0;
      scroll.setAttribute('role', 'region');
      scroll.setAttribute('aria-label', 'Post links and actions');
      scroll.append(button, links);
      content.append(scroll);
      body.append(content);
      details.append(summary, body);
      animateDisclosure(details, summary, body);
      details.addEventListener('toggle', () => {
        if (details.open && !links.dataset.requested) {
          links.dataset.requested = 'true';
          loadRelatedLinks(item, links);
        }
      });
      card.append(link, renderMetadata(item, kind), excerpt, details);
      panel.append(card);
    }
  }

  async function loadResults() {
    if (request) request.abort();
    request = new AbortController();
    const signal = request.signal;
    status.textContent = 'Loading results…';
    previousPage.disabled = true;
    nextPage.disabled = true;
    panels.sentences.replaceChildren();
    panels.posts.replaceChildren();
    displayed = { sentences: [], posts: [] };
    currentTotal = 0;
    updateReadTools();
    try {
      const response = await fetch(resultsUrl('page'), { signal });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not load results.');
      if (!data.posts.length && currentPage > 1) {
        // Marking read under only_unread can shrink the list below this page.
        currentPage = Math.max(1, Math.ceil(data.total / data.page_size));
        return loadResults();
      }
      currentTotal = data.total;
      onlyUnread = Boolean(data.only_unread);
      updateFilterSummary();
      displayed = { sentences: data.sentences, posts: data.posts };
      renderItems(panels.sentences, data.sentences, 'sentences');
      renderItems(panels.posts, data.posts, 'posts');
      status.textContent = data.posts.length ? '' : 'No posts on this page.';
      previousPage.disabled = currentPage === 1;
      nextPage.disabled = !data.has_more;
      const start = (currentPage - 1) * data.page_size + 1;
      const end = start + data.posts.length - 1;
      pageLabel.textContent = data.posts.length ? `Showing posts ${start}–${end} of ${data.total}` : `Page ${currentPage}`;
      updateReadTools();
    } catch (error) {
      if (error.name !== 'AbortError') status.textContent = error.message || 'Could not load results.';
    }
  }

  async function select(button, selection) {
    if (activeButton) activeButton.classList.remove('is-active');
    activeButton = button;
    button.classList.add('is-active');
    currentSelection = selection;
    currentPage = 1;
    updateFilterSummary();
    await loadResults();
  }

  function item(label, countValue, selection, parent, children, parentCount) {
    const wrapper = document.createElement('div');
    const row = document.createElement('div');
    row.className = 'tag-explorer__node';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tag-explorer__node-label';
    button.textContent = label;
    button.addEventListener('click', () => select(button, selection));
    if (children && children.length) {
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'tag-explorer__toggle';
      toggle.setAttribute('aria-label', `Expand ${label}`);
      toggle.setAttribute('aria-expanded', 'false');
      const nested = document.createElement('div');
      nested.className = 'tag-explorer__nested';
      nested.hidden = true;
      let populated = false;
      toggle.addEventListener('click', () => {
        if (!populated) {
          for (const child of children) nested.append(child());
          populated = true;
        }
        nested.hidden = !nested.hidden;
        toggle.setAttribute('aria-expanded', String(!nested.hidden));
      });
      row.append(toggle);
      wrapper.append(row, nested);
    } else {
      const spacer = document.createElement('span');
      spacer.className = 'tag-explorer__spacer';
      row.append(spacer);
    }
    row.append(button);
    if (countValue !== undefined) {
      const countLabel = document.createElement('span');
      countLabel.className = 'tag-explorer__node-count';
      countLabel.textContent = `${countValue} posts`;
      if (parentCount) {
        const share = document.createElement('progress');
        share.className = 'tag-explorer__node-share';
        share.max = parentCount;
        share.value = countValue;
        share.setAttribute('aria-label', `${countValue} of ${parentCount} parent posts`);
        countLabel.title = `${Math.round(countValue / parentCount * 100)}% of parent posts`;
        countLabel.prepend(share);
      }
      row.append(countLabel);
    }
    if (!children || !children.length) wrapper.append(row);
    parent.append(wrapper);
    return button;
  }

  function contextNode(node, chain, parentCount) {
    const next = [...chain, node.name];
    const label = node.name;
    const fragment = document.createDocumentFragment();
    const children = (node.children || []).map(child => () => contextNode(child, next, node.count));
    const button = item(label, node.count, { kind: 'context', chain: next }, fragment, children, parentCount);
    button.title = `${node.occurrences} occurrences in ${node.count} posts`;
    return fragment;
  }

  function topicNode(node, chain, parentCount) {
    const next = [...chain, node.name];
    const fragment = document.createDocumentFragment();
    const children = (node.children || []).map(child => () => topicNode(child, next, node.count));
    item(node.name, node.count, { kind: 'topic', chain: next }, fragment, children, parentCount);
    return fragment;
  }

  function selectFilterTab(tab) {
    for (const filterTab of filterTabs.querySelectorAll('[role="tab"]')) {
      const selected = filterTab === tab;
      filterTab.setAttribute('aria-selected', String(selected));
      filterTab.tabIndex = selected ? 0 : -1;
      document.getElementById(filterTab.getAttribute('aria-controls')).hidden = !selected;
    }
  }

  function navigateFilterTabs(event, tab) {
    const buttons = [...filterTabs.querySelectorAll('[role="tab"]')];
    const index = buttons.indexOf(tab);
    const offsets = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: buttons.length - 1 - index };
    if (!Object.hasOwn(offsets, event.key)) return;
    event.preventDefault();
    const next = buttons[(index + offsets[event.key] + buttons.length) % buttons.length];
    next.focus();
    next.click();
  }

  function section(name, label, nodes, description, renderNode) {
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.id = `tag-explorer-filter-${name}-tab`;
    tab.textContent = label;
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', `tag-explorer-filter-${name}`);
    tab.setAttribute('aria-selected', String(name === 'context'));
    tab.tabIndex = name === 'context' ? 0 : -1;
    filterTabs.append(tab);
    const body = document.createElement('div');
    body.className = 'tag-explorer__section-body';
    body.id = `tag-explorer-filter-${name}`;
    body.setAttribute('role', 'tabpanel');
    body.setAttribute('aria-labelledby', tab.id);
    body.tabIndex = 0;
    const note = document.createElement('p');
    note.className = 'tag-explorer__context-note';
    note.textContent = description;
    body.append(note);
    if (!nodes.length) {
      const empty = document.createElement('p');
      empty.className = 'tag-explorer__empty';
      empty.textContent = name === 'topics' ? 'No grouped topics contain sentences mentioning this tag.' : 'No context chains available';
      body.append(empty);
    } else {
      for (const node of nodes) body.append(renderNode(node));
    }
    body.hidden = name !== 'context';
    tab.addEventListener('click', () => selectFilterTab(tab));
    tab.addEventListener('keydown', event => navigateFilterTabs(event, tab));
    container.append(body);
  }

  for (const name of Object.keys(tabs)) tabs[name].addEventListener('click', () => selectTab(name));
  readPage.addEventListener('click', () => changeReadState(displayed[currentTab].filter(entry => !entry.read), currentTab, true));
  unreadPage.addEventListener('click', () => changeReadState(displayed[currentTab].filter(entry => entry.read), currentTab, false));
  readAll.addEventListener('click', () => changeAllReadState(currentTab, true));
  unreadAll.addEventListener('click', () => changeAllReadState(currentTab, false));
  previousPage.addEventListener('click', () => { if (currentPage > 1) { currentPage -= 1; loadResults(); } });
  nextPage.addEventListener('click', () => { if (!nextPage.disabled) { currentPage += 1; loadResults(); } });
  const rootButton = item(tree.name, tree.count, { kind: 'root' }, document.getElementById('tag-explorer-root'));
  clearFilter.addEventListener('click', () => {
    rootButton.focus();
    select(rootButton, { kind: 'root' });
  });
  section('context', 'Context chain', tree.context,
    'All posts · up to 5 neighboring words. Select a word to narrow the posts. Bars show the share of parent posts.',
    node => contextNode(node, [], tree.count));
  section('topics', 'Topics', tree.topics || [],
    'Topics include only sentences mentioning this tag. Select a topic to show its posts and matching sentences. Parent topics include all subtopics. Bars show the share of parent posts.',
    node => topicNode(node, [], tree.count));
  select(rootButton, { kind: 'root' });
}, { once: true });
