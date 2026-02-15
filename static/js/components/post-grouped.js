import TopicFlow from './topic-flow.js';
import TopicsRiverChart from './topics-river-chart.js';

export default class PostGroupedPage {
    constructor() {
        this.topicState = {};
        this.topicToSentences = {};
        this.topicElements = new Map();
        this.isContentReady = false;
        this.chartInitialized = false;
        this.topicFlowChart = null;
        this.riverCharts = {};
        this.sentencesByGlobalNumber = new Map();
    }

    init() {
        this.stripGlobalStyles();
        this.setupPostSections();
        this.indexSentences();
        this.addPostHoverEffects();
        this.isContentReady = true;
        this.buildTopicsList();
        this.buildPostsList();
        this.attachSentenceGroupHandlers();
        this.attachReadButtonHandlers();
        this.initTabs();
        this.initZoomControls();
        this.handleHighlightSentenceFromUrl();
        this.setInitialReadStatus();
        this.bindGlobalEvents();
    }

    stripGlobalStyles() {
        document.querySelectorAll('.post-text').forEach((container) => {
            container.querySelectorAll('style').forEach((styleNode) => {
                styleNode.remove();
            });
            container.querySelectorAll('link[rel="stylesheet"]').forEach((linkNode) => {
                linkNode.remove();
            });
        });
    }

    bindGlobalEvents() {
        if (window.EVSYS) {
            window.EVSYS.bind(window.EVSYS.POSTS_UPDATED, (state) => {
                state.posts.forEach((item, pos) => {
                    const btn = document.querySelector(`.post-read-status[data-post-id="${pos}"]`);
                    if (btn) {
                        const isRead = item.post.read;
                        if (isRead) {
                            btn.classList.remove('unread');
                            btn.classList.add('read');
                            btn.textContent = 'read';
                        } else {
                            btn.classList.remove('read');
                            btn.classList.add('unread');
                            btn.textContent = 'unread';
                        }
                        
                        const section = btn.closest('.post-section');
                        if (section) {
                            section.style.opacity = isRead ? '0.6' : '1.0';
                        }
                    }
                });
            });
        }
    }

    setInitialReadStatus() {
        document.querySelectorAll('.post-read-status.read').forEach(btn => {
            const section = btn.closest('.post-section');
            if (section) {
                section.style.opacity = '0.6';
            }
        });
    }

    attachReadButtonHandlers() {
        document.querySelectorAll('.post-read-status').forEach(btn => {
            btn.addEventListener('click', (ev) => {
                ev.stopPropagation();
                const postId = btn.getAttribute('data-post-id');
                const isRead = btn.classList.contains('read');
                this.changePostStatus(postId, !isRead, btn);
            });
        });
    }

    changePostStatus(postId, newStatus, btn) {
        fetch('/read/posts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                ids: [postId],
                readed: newStatus
            })
        })
        .then(response => {
            if (response.ok) {
                if (newStatus) {
                    btn.classList.remove('unread');
                    btn.classList.add('read');
                    btn.textContent = 'read';
                    
                    const section = btn.closest('.post-section');
                    if (section) {
                        section.style.opacity = '0.6';
                    }
                } else {
                    btn.classList.remove('read');
                    btn.classList.add('unread');
                    btn.textContent = 'unread';
                    
                    const section = btn.closest('.post-section');
                    if (section) {
                        section.style.opacity = '1.0';
                    }
                }
            }
        })
        .catch(err => console.error('Failed to update post status', err));
    }

    setupPostSections() {
        document.querySelectorAll('#grouped_posts .post-section').forEach((section) => {
            const postId = section.getAttribute('data-post-id');
            if (postId) {
                section.setAttribute('data-post-index', window.post_to_index_map[postId]);
            }
        });
    }

    addPostHoverEffects() {
        document.querySelectorAll('#grouped_posts .post-section').forEach((section) => {
            section.addEventListener('mouseenter', () => {
                section.style.boxShadow = '0 2px 8px rgba(66, 133, 244, 0.2)';
            });
            section.addEventListener('mouseleave', () => {
                section.style.boxShadow = 'none';
            });
        });
    }

    indexSentences() {
        this.sentencesByGlobalNumber.clear();
        (window.sentences || []).forEach((sentence) => {
            const globalNumber = Number(sentence.number);
            if (!Number.isFinite(globalNumber)) {
                return;
            }
            this.sentencesByGlobalNumber.set(globalNumber, {
                postId: sentence.post_id,
                postSentenceNumber: Number(sentence.post_sentence_number),
                read: Boolean(sentence.read)
            });
        });
    }

    splitTopicPath(topicName) {
        if (!topicName || typeof topicName !== 'string') {
            return [];
        }
        return topicName
            .split('>')
            .map((part) => part.trim())
            .filter(Boolean);
    }

    colorFromString(value) {
        if (!value) {
            return '#4a6baf';
        }
        let hash = 0;
        for (let i = 0; i < value.length; i++) {
            hash = ((hash << 5) - hash) + value.charCodeAt(i);
            hash |= 0;
        }
        const hue = Math.abs(hash) % 360;
        return `hsl(${hue}, 60%, 60%)`;
    }

    getTopicColor(topicPath) {
        if (window.group_colors && window.group_colors[topicPath]) {
            return window.group_colors[topicPath];
        }
        return this.colorFromString(topicPath);
    }

    buildTopicsTree() {
        const groups = window.groups || {};
        const roots = [];
        const nodeByPath = new Map();

        Object.keys(groups).forEach((groupName) => {
            const sentenceIndices = (groups[groupName] || [])
                .map((num) => Number(num))
                .filter((num) => Number.isFinite(num));
            const parts = this.splitTopicPath(groupName);
            if (!parts.length) {
                return;
            }

            let currentChildren = roots;
            let pathParts = [];
            parts.forEach((part) => {
                pathParts.push(part);
                const path = pathParts.join(' > ');
                let node = nodeByPath.get(path);
                if (!node) {
                    node = {
                        name: part,
                        path: path,
                        color: this.getTopicColor(path),
                        sentenceSet: new Set(),
                        children: []
                    };
                    nodeByPath.set(path, node);
                    currentChildren.push(node);
                }
                sentenceIndices.forEach((sentenceNumber) => node.sentenceSet.add(sentenceNumber));
                currentChildren = node.children;
            });
        });

        const sortTree = (nodes) => {
            nodes.sort((a, b) => {
                if (b.sentenceSet.size !== a.sentenceSet.size) {
                    return b.sentenceSet.size - a.sentenceSet.size;
                }
                return a.name.localeCompare(b.name);
            });
            nodes.forEach((node) => sortTree(node.children));
        };
        sortTree(roots);
        return roots;
    }

    setActiveTopic(topicPath) {
        document.querySelectorAll('.topic-tree-node.active').forEach((node) => {
            node.classList.remove('active');
        });
        const topicElement = this.topicElements.get(topicPath);
        if (topicElement) {
            topicElement.classList.add('active');
        }
    }

    renderTopicNode(node, topicsList, depth = 0) {
        const topicPath = node.path;
        const sentenceIndices = Array.from(node.sentenceSet).sort((a, b) => a - b);
        this.topicToSentences[topicPath] = sentenceIndices;
        this.topicState[topicPath] = {
            sentences: sentenceIndices,
            index: 0,
            color: node.color
        };

        const rootEl = document.createElement('div');
        rootEl.className = `topic-tree-node depth-${Math.min(depth, 5)}`;
        rootEl.style.setProperty('--topic-accent', node.color);

        const line = document.createElement('div');
        line.className = 'topic-line';

        const titleWrap = document.createElement('div');
        titleWrap.className = 'topic-title-wrap';
        const nameSpan = document.createElement('span');
        nameSpan.className = 'topic-name';
        nameSpan.textContent = node.name;
        const countSpan = document.createElement('span');
        countSpan.className = 'topic-count';
        countSpan.textContent = `(${sentenceIndices.length})`;
        titleWrap.appendChild(nameSpan);
        titleWrap.appendChild(countSpan);

        const linksWrap = document.createElement('div');
        linksWrap.className = 'topic-links';
        const topicParam = encodeURIComponent(topicPath);

        const groupedLink = document.createElement('a');
        groupedLink.className = 'topic-link topic-link-grouped';
        groupedLink.href = `/post-grouped/${window.post_id}?topic=${topicParam}`;
        groupedLink.textContent = 'Sentences';

        const snippetsLink = document.createElement('a');
        snippetsLink.className = 'topic-link topic-link-snippets';
        snippetsLink.href = `/post-grouped-snippets/${window.post_id}?topic=${topicParam}`;
        snippetsLink.textContent = 'Snippets';

        linksWrap.appendChild(groupedLink);
        linksWrap.appendChild(snippetsLink);
        titleWrap.appendChild(linksWrap);

        const controls = document.createElement('div');
        controls.className = 'topic-controls';
        const prevBtn = document.createElement('button');
        prevBtn.className = 'topic-btn topic-btn-prev';
        prevBtn.title = 'Previous sentence';
        prevBtn.textContent = 'Prev';

        const nextBtn = document.createElement('button');
        nextBtn.className = 'topic-btn topic-btn-next';
        nextBtn.title = 'Next sentence';
        nextBtn.textContent = 'Next';

        const toggleReadBtn = document.createElement('button');
        toggleReadBtn.className = 'topic-btn topic-btn-read-toggle';
        toggleReadBtn.dataset.topicName = topicPath;
        this.updateTopicReadButton(toggleReadBtn, this.isTopicFullyRead(topicPath));
        controls.appendChild(prevBtn);
        controls.appendChild(nextBtn);
        controls.appendChild(toggleReadBtn);

        line.appendChild(titleWrap);
        line.appendChild(controls);

        rootEl.appendChild(line);
        topicsList.appendChild(rootEl);
        this.topicElements.set(topicPath, rootEl);

        line.addEventListener('click', (ev) => {
            const clickable = ev.target.closest('a,button');
            if (clickable) {
                return;
            }
            if (!this.isContentReady) {
                return;
            }
            this.setActiveTopic(topicPath);
            const state = this.topicState[topicPath];
            if (state) {
                state.index = 0;
            }
        });

        prevBtn.addEventListener('click', (ev) => {
            ev.stopPropagation();
            ev.preventDefault();
            if (!this.isContentReady) {
                return;
            }
            this.setActiveTopic(topicPath);
            this.moveTopicPointer(topicPath, -1);
        });

        nextBtn.addEventListener('click', (ev) => {
            ev.stopPropagation();
            ev.preventDefault();
            if (!this.isContentReady) {
                return;
            }
            this.setActiveTopic(topicPath);
            this.moveTopicPointer(topicPath, 1);
        });

        toggleReadBtn.addEventListener('click', (ev) => {
            ev.stopPropagation();
            ev.preventDefault();
            if (!this.isContentReady) {
                return;
            }
            this.toggleTopicReadStatus(topicPath, toggleReadBtn);
        });

        if (node.children && node.children.length) {
            const childrenWrap = document.createElement('div');
            childrenWrap.className = 'topic-children';
            node.children.forEach((child) => {
                this.renderTopicNode(child, childrenWrap, depth + 1);
            });
            rootEl.appendChild(childrenWrap);
        }
    }

    buildTopicsList() {
        const topicsList = document.getElementById('topics_list');
        if (!topicsList) {
            return;
        }
        this.topicState = {};
        this.topicToSentences = {};
        this.topicElements = new Map();
        const groupKeys = Object.keys(window.groups || {});

        if (groupKeys.length === 0) {
            topicsList.innerHTML = '<p style="color: #666; font-style: italic;">No topics available</p>';
            return;
        }
        const topicTree = this.buildTopicsTree();
        topicTree.forEach((node) => this.renderTopicNode(node, topicsList, 0));
    }

    updateTopicReadButton(button, isFullyRead) {
        button.textContent = isFullyRead ? 'Mark Unread' : 'Mark Read';
        button.title = isFullyRead
            ? 'Mark all topic sentences on this page as unread'
            : 'Mark all topic sentences on this page as read';
        button.dataset.read = isFullyRead ? '1' : '0';
        button.classList.toggle('snippet-tag-read', isFullyRead);
        button.classList.toggle('snippet-tag-unread', !isFullyRead);
    }

    getSelectionsForTopic(topicName) {
        const groupedSelections = new Map();
        const sentenceNumbers = this.topicToSentences[topicName] || [];

        sentenceNumbers.forEach((globalSentenceNumber) => {
            const sentenceMeta = this.sentencesByGlobalNumber.get(Number(globalSentenceNumber));
            if (!sentenceMeta || !sentenceMeta.postId || !Number.isFinite(sentenceMeta.postSentenceNumber)) {
                return;
            }
            const postId = String(sentenceMeta.postId);
            if (!groupedSelections.has(postId)) {
                groupedSelections.set(postId, new Set());
            }
            groupedSelections.get(postId).add(sentenceMeta.postSentenceNumber);
        });

        return Array.from(groupedSelections.entries()).map(([postId, sentenceSet]) => ({
            post_id: postId,
            sentence_indices: Array.from(sentenceSet).sort((a, b) => a - b)
        }));
    }

    isTopicFullyRead(topicName) {
        const sentenceNumbers = this.topicToSentences[topicName] || [];
        let hasAnySentence = false;

        for (const globalSentenceNumber of sentenceNumbers) {
            const sentenceMeta = this.sentencesByGlobalNumber.get(Number(globalSentenceNumber));
            if (!sentenceMeta) {
                continue;
            }
            hasAnySentence = true;
            if (!sentenceMeta.read) {
                return false;
            }
        }

        return hasAnySentence;
    }

    setReadStateForSelections(selections, readed) {
        const globalNumbersToUpdate = new Set();

        selections.forEach((selection) => {
            const postId = String(selection.post_id);
            const sentenceIndices = selection.sentence_indices || [];

            (window.sentences || []).forEach((sentence) => {
                if (String(sentence.post_id) !== postId) {
                    return;
                }
                const localNumber = Number(sentence.post_sentence_number);
                if (sentenceIndices.includes(localNumber)) {
                    const globalNumber = Number(sentence.number);
                    if (Number.isFinite(globalNumber)) {
                        sentence.read = readed;
                        globalNumbersToUpdate.add(globalNumber);
                    }
                }
            });
        });

        globalNumbersToUpdate.forEach((globalNumber) => {
            const sentenceMeta = this.sentencesByGlobalNumber.get(globalNumber);
            if (sentenceMeta) {
                sentenceMeta.read = readed;
            }
            document
                .querySelectorAll(`.sentence-group[data-sentence="${globalNumber}"]`)
                .forEach((sentenceEl) => {
                    sentenceEl.classList.toggle('sentence-read', readed);
                });
        });
    }

    refreshTopicReadButtons() {
        document.querySelectorAll('.topic-btn-read-toggle').forEach((button) => {
            const topicName = button.dataset.topicName;
            if (!topicName) {
                return;
            }
            this.updateTopicReadButton(button, this.isTopicFullyRead(topicName));
        });
    }

    changeSnippetsStatus(selections, readed) {
        if (!selections || !selections.length) {
            return Promise.resolve(null);
        }

        return fetch('/read/snippets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                selections: selections,
                readed: readed
            })
        }).then((response) => response.json());
    }

    toggleTopicReadStatus(topicName, button) {
        const selections = this.getSelectionsForTopic(topicName);
        if (!selections.length) {
            return;
        }

        const currentlyRead = button.dataset.read === '1';
        const nextRead = !currentlyRead;
        button.disabled = true;

        this.changeSnippetsStatus(selections, nextRead)
            .then((payload) => {
                if (payload && payload.data === 'ok') {
                    this.setReadStateForSelections(selections, nextRead);
                    this.refreshTopicReadButtons();
                } else {
                    alert('Failed to update status');
                }
            })
            .catch((err) => {
                console.error(err);
                alert('Failed to update status');
            })
            .finally(() => {
                button.disabled = false;
            });
    }

    buildPostsList() {
        const postsList = document.getElementById('posts_list');
        if (!postsList || !window.posts || window.posts.length <= 1) {
            return;
        }
        window.posts.forEach((post) => {
            const el = document.createElement('div');
            el.className = 'topic-item';
            el.style.backgroundColor = '#4285f440';
            el.style.borderLeft = '4px solid #4285f4';
            el.innerHTML = '<span class="topic-name">Post ' + post.post_id + '</span>' +
                '<span class="topic-count">(' + (post.feed_title || 'Unknown') + ')</span>';
            el.onclick = () => {
                const section = document.querySelector('[data-post-id="' + post.post_id + '"]');
                if (section) {
                    setTimeout(() => {
                        section.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        section.classList.add('range-highlight', 'pulse');
                        setTimeout(() => {
                            section.classList.remove('range-highlight', 'pulse');
                        }, 2000);
                    }, 50);
                }
            };
            postsList.appendChild(el);
        });
    }

    attachSentenceGroupHandlers() {
        document.querySelectorAll('.sentence-group').forEach(span => {
            span.addEventListener('click', (ev) => {
                ev.stopPropagation();
                const sentNum = parseInt(span.getAttribute('data-sentence'));
                if (!sentNum) return;

                let topicName = null;
                let topicElement = null;

                Object.keys(window.groups || {}).forEach(groupName => {
                    if (window.groups[groupName].includes(sentNum)) {
                        topicName = groupName;
                    }
                });

                if (topicName) {
                    topicElement = this.topicElements.get(topicName);
                    if (topicElement) {
                        topicElement.click();
                    }
                }
            });
        });
    }

    highlightSentences(sentenceIndices, color, focusIndex, shouldScroll = true) {
        if (!sentenceIndices || sentenceIndices.length === 0) return;

        document.querySelectorAll('.sentence-group.highlighted').forEach(span => {
            span.classList.remove('highlighted');
        });

        const highlightedElements = [];
        const highlightedBySentence = {};
        sentenceIndices.forEach(sentNum => {
            const spans = document.querySelectorAll('.sentence-group[data-sentence="' + sentNum + '"]');
            spans.forEach(span => {
                span.classList.add('highlighted');
                highlightedElements.push(span);
                if (!highlightedBySentence[sentNum]) {
                    highlightedBySentence[sentNum] = [];
                }
                highlightedBySentence[sentNum].push(span);
            });
        });

        if (highlightedElements.length > 0) {
            const targetIdx = Number.isFinite(focusIndex) ? Math.max(0, Math.min(highlightedElements.length - 1, focusIndex)) : 0;
            const clampedSentenceIndex = Number.isFinite(focusIndex)
                ? Math.max(0, Math.min(sentenceIndices.length - 1, focusIndex))
                : 0;
            const targetSentence = sentenceIndices[clampedSentenceIndex];
            const targetSpan = (targetSentence && highlightedBySentence[targetSentence] && highlightedBySentence[targetSentence][0])
                ? highlightedBySentence[targetSentence][0]
                : highlightedElements[targetIdx];
            if (targetSpan && shouldScroll) {
                setTimeout(() => {
                    targetSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    targetSpan.classList.add('pulse');
                    setTimeout(() => targetSpan.classList.remove('pulse'), 1200);
                }, 100);
            }
        }
    }

    highlightPosts(postIds, color) {
        if (!postIds || postIds.length === 0) return;

        document.querySelectorAll('#grouped_posts .post-section').forEach(section => {
            section.classList.remove('range-highlight');
            section.style.backgroundColor = '';
            section.style.borderLeft = '';
        });

        const highlightedSections = [];
        postIds.forEach(postId => {
            const section = document.querySelector('[data-post-id="' + postId + '"]');
            if (section) {
                section.classList.add('range-highlight');
                section.style.backgroundColor = color + '40';
                section.style.borderLeft = '3px solid ' + color;
                highlightedSections.push(section);
            }
        });

        if (highlightedSections.length > 0) {
            const target = highlightedSections[0];
            setTimeout(() => {
                target.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 100);
        }
    }

    moveTopicPointer(topicName, delta) {
        const state = this.topicState[topicName];
        if (!state) return;

        if (!state.sentences || state.sentences.length === 0) {
            if (!window.has_grouped_data && window.groups[topicName]) {
                this.highlightPosts(window.groups[topicName], state.color || '#4a6baf');
            }
            return;
        }

        const total = state.sentences.length;
        state.index = ((state.index + delta) % total + total) % total;

        if (window.has_grouped_data) {
            this.highlightSentences(state.sentences, state.color, state.index);
        } else {
            this.highlightPosts(state.sentences, state.color);
        }
    }

    handleHighlightSentenceFromUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        const highlightSentNum = parseInt(urlParams.get('highlight_sentence'));
        if (isNaN(highlightSentNum)) return;

        let topicName = null;
        Object.keys(window.groups || {}).forEach(name => {
            if (window.groups[name].includes(highlightSentNum)) {
                topicName = name;
            }
        });

        if (topicName && this.isContentReady) {
            const color = window.group_colors[topicName] || '#4a6baf';
            setTimeout(() => {
                this.highlightSentences([highlightSentNum], color, 0);
                const topicEl = this.topicElements.get(topicName);
                if (topicEl) {
                    this.setActiveTopic(topicName);
                    topicEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }, 500);
        }
    }

    initTabs() {
        const tabs = document.querySelectorAll('.tab-header > .tab-btn');
        const contents = document.querySelectorAll('.tab-content');
        if (!tabs.length || !contents.length) {
            return;
        }

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.getAttribute('data-tab');
                if (!target) return;

                tabs.forEach(t => t.classList.remove('active'));
                contents.forEach(c => c.classList.remove('active'));

                tab.classList.add('active');
                if (target === 'posts') {
                    document.getElementById('tab-posts').classList.add('active');
                } else if (target === 'topic-chart') {
                    document.getElementById('tab-topic-chart').classList.add('active');
                    if (!this.chartInitialized) {
                        this.topicFlowChart = this.initChart();
                        this.chartInitialized = true;
                    }
                }
            });
        });

        this.initLocalTabs();
    }

    initLocalTabs() {
        const localTabs = document.querySelectorAll('.local-tab-btn');
        localTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const postId = tab.getAttribute('data-post-id');
                const target = tab.getAttribute('data-local-tab');
                const postSection = document.getElementById('post_' + postId);
                if (!postSection) return;

                // Toggle tabs
                postSection.querySelectorAll('.local-tab-btn').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Toggle contents
                postSection.querySelectorAll('.local-tab-content').forEach(c => c.classList.remove('active'));
                const targetContent = postSection.querySelector(`.local-tab-content[data-local-content="${target}"]`);
                if (targetContent) {
                    targetContent.classList.add('active');
                }

                if (target === 'river') {
                    // Small delay to ensure container is visible and has dimensions
                    setTimeout(() => this.initRiverChart(postId), 10);
                }
            });
        });
    }

    initRiverChart(postId) {
        if (this.riverCharts[postId]) {
            this.riverCharts[postId].render();
            return;
        }

        const post = window.posts.find(p => String(p.post_id) === String(postId));
        if (!post || !post.river_data) return;

        const containerId = 'river_chart_' + postId;
        this.riverCharts[postId] = new TopicsRiverChart('#' + containerId, {
            topics: post.river_data.topics,
            articleLength: post.river_data.articleLength
        });
    }

    initZoomControls() {
        const zoomIn = document.getElementById('zoom-in');
        const zoomOut = document.getElementById('zoom-out');
        const resetZoom = document.getElementById('reset-zoom');
        if (!zoomIn || !zoomOut || !resetZoom) {
            return;
        }

        zoomIn.addEventListener('click', () => {
            if (this.topicFlowChart) this.topicFlowChart.zoomIn();
        });
        zoomOut.addEventListener('click', () => {
            if (this.topicFlowChart) this.topicFlowChart.zoomOut();
        });
        resetZoom.addEventListener('click', () => {
            if (this.topicFlowChart) this.topicFlowChart.resetZoom();
        });
    }

    initChart() {
        if (!window.groups) return null;

        const children = Object.keys(window.groups).map(key => ({
            name: key,
            value: window.groups[key].length
        }));

        const data = {
            name: 'Topics',
            children: children
        };

        return new TopicFlow(data, '#topic_flow_chart');
    }
}
