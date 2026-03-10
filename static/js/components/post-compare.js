import PostGroupedPage from './post-grouped.js';

export default class PostComparePage extends PostGroupedPage {
  constructor() {
    super();
    this.currentTopic = null;
    this.anchorRatio = 0.3;
  }

  init() {
    this.stripGlobalStyles();
    this.setupPostSections();
    this.indexSentences();
    this.isContentReady = true;
    this.buildTopicsList();
    this.buildPostsList();
    this.attachSentenceGroupHandlers();
    this.attachReadButtonHandlers();
    this.setInitialReadStatus();
    this.bindGlobalEvents();
    this.activateInitialTopic();
  }

  buildPostsList() {
    const postsList = document.getElementById('posts_list');
    const compareScroll = document.getElementById('compare_scroll');
    if (!postsList || !compareScroll || !window.posts || window.posts.length <= 1) {
      return;
    }

    window.posts.forEach((post) => {
      const el = document.createElement('div');
      el.className = 'topic-item';
      el.style.backgroundColor = '#4285f440';
      el.style.borderLeft = '4px solid #4285f4';
      el.innerHTML =
        '<span class="topic-name">Post ' +
        post.post_id +
        '</span>' +
        '<span class="topic-count">(' +
        (post.feed_title || 'Unknown') +
        ')</span>';
      el.onclick = () => {
        const column = document.querySelector(`[data-post-id="${post.post_id}"]`);
        if (!column) {
          return;
        }
        const scrollBounds = compareScroll.getBoundingClientRect();
        const columnBounds = column.getBoundingClientRect();
        const targetLeft =
          compareScroll.scrollLeft + (columnBounds.left - scrollBounds.left) - 24;
        compareScroll.scrollTo({
          left: Math.max(0, targetLeft),
          behavior: 'smooth',
        });
        column.classList.add('range-highlight', 'pulse');
        window.setTimeout(() => {
          column.classList.remove('range-highlight', 'pulse');
        }, 1500);
      };
      postsList.appendChild(el);
    });
  }

  handleTopicSelection(topicPath) {
    this.setActiveTopic(topicPath);
    const state = this.topicState[topicPath];
    if (state) {
      state.index = 0;
    }
    this.currentTopic = topicPath;
    this.syncTopicColumns(topicPath);
  }

  activateInitialTopic() {
    const currentTopic =
      typeof window.current_topic === 'string' && window.current_topic.trim()
        ? window.current_topic
        : null;
    const defaultTopic =
      currentTopic && this.topicState[currentTopic]
        ? currentTopic
        : Object.keys(this.topicState || {})[0] || null;

    if (!defaultTopic) {
      return;
    }

    this.handleTopicSelection(defaultTopic);
    const topicElement = this.topicElements.get(defaultTopic);
    if (topicElement) {
      topicElement.scrollIntoView({ block: 'nearest' });
    }
  }

  clearCompareState() {
    document.querySelectorAll('.compare-post-column').forEach((column) => {
      column.classList.remove('compare-post-column-no-match');
    });
    document.querySelectorAll('.compare-anchor-sentence').forEach((span) => {
      span.classList.remove('compare-anchor-sentence');
    });
  }

  syncTopicColumns(topicPath) {
    const topicState = this.topicState[topicPath];
    const sentenceNumbers = topicState ? topicState.sentences : [];
    const color = topicState ? topicState.color : '#4a6baf';

    this.clearCompareState();
    this.highlightSentences(sentenceNumbers, color, 0, false);

    const columns = document.querySelectorAll('.compare-post-column');
    columns.forEach((column) => {
      const body = column.querySelector('.compare-post-body');
      const emptyState = column.querySelector('.compare-no-match');
      if (!body || !emptyState) {
        return;
      }

      let anchorSentence = null;
      for (const sentenceNumber of sentenceNumbers) {
        const selector = `.sentence-group[data-sentence="${sentenceNumber}"]`;
        if (body.querySelector(selector)) {
          anchorSentence = sentenceNumber;
          break;
        }
      }

      if (anchorSentence === null) {
        column.classList.add('compare-post-column-no-match');
        emptyState.hidden = false;
        body.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }

      emptyState.hidden = true;
      const anchorSpans = body.querySelectorAll(
        `.sentence-group[data-sentence="${anchorSentence}"]`
      );
      anchorSpans.forEach((span) => {
        span.classList.add('compare-anchor-sentence');
      });

      const firstAnchor = anchorSpans[0];
      if (!firstAnchor) {
        return;
      }

      const bodyRect = body.getBoundingClientRect();
      const anchorRect = firstAnchor.getBoundingClientRect();
      const offsetTop = body.scrollTop + (anchorRect.top - bodyRect.top);
      const targetTop = offsetTop - body.clientHeight * this.anchorRatio;
      body.scrollTo({
        top: Math.max(0, targetTop),
        behavior: 'smooth',
      });
    });
  }
}
