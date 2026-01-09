import TopicFlow from './topic-flow.js';
import TopicsRiverChart from './topics-river-chart.js';

export default class PostGroupedPage {
    constructor() {
        this.topicState = {};
        this.isContentReady = false;
        this.chartInitialized = false;
        this.topicFlowChart = null;
        this.riverCharts = {};
    }

    init() {
        this.setupPostSections();
        this.addPostHoverEffects();
        this.isContentReady = true;
        this.buildTopicsList();
        this.buildPostsList();
        this.attachSentenceGroupHandlers();
        this.initTabs();
        this.initZoomControls();
        this.handleHighlightSentenceFromUrl();
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

    buildTopicsList() {
        const topicsList = document.getElementById('topics_list');
        if (!topicsList) {
            return;
        }
        const groupKeys = Object.keys(window.groups || {});

        if (groupKeys.length === 0) {
            topicsList.innerHTML = '<p style="color: #666; font-style: italic;">No topics available</p>';
            return;
        }

        groupKeys.forEach(groupName => {
            const sentenceIndices = (window.groups[groupName] || []).slice().sort((a, b) => a - b);
            const color = window.group_colors[groupName] || '#4a6baf';
            const el = document.createElement('div');
            el.className = 'topic-item';
            el.style.backgroundColor = color + '40';
            el.style.borderLeft = '4px solid ' + color;

            const countLabel = sentenceIndices.length;
            const line = document.createElement('div');
            line.className = 'topic-line';

            const titleWrap = document.createElement('div');
            const nameSpan = document.createElement('span');
            nameSpan.className = 'topic-name';
            nameSpan.textContent = groupName;
            const countSpan = document.createElement('span');
            countSpan.className = 'topic-count';
            countSpan.textContent = '(' + countLabel + ')';
            titleWrap.appendChild(nameSpan);
            titleWrap.appendChild(countSpan);

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
            controls.appendChild(prevBtn);
            controls.appendChild(nextBtn);

            line.appendChild(titleWrap);
            line.appendChild(controls);
            el.appendChild(line);

            this.topicState[groupName] = {
                sentences: sentenceIndices,
                index: 0,
                color
            };

            el.onclick = () => {
                if (!this.isContentReady) return;

                document.querySelectorAll('.topic-item.active').forEach(item => {
                    item.classList.remove('active');
                });
                el.classList.add('active');

                if (window.has_grouped_data && this.topicState[groupName]) {
                    this.topicState[groupName].index = 0;
                    this.highlightSentences(sentenceIndices, color, 0);
                } else {
                    this.highlightPosts(sentenceIndices, color);
                }
            };

            prevBtn.addEventListener('click', (ev) => {
                ev.stopPropagation();
                ev.preventDefault();
                if (!this.isContentReady) return;

                document.querySelectorAll('.topic-item.active').forEach(item => {
                    item.classList.remove('active');
                });
                el.classList.add('active');

                this.moveTopicPointer(groupName, -1);
            });

            nextBtn.addEventListener('click', (ev) => {
                ev.stopPropagation();
                ev.preventDefault();
                if (!this.isContentReady) return;

                document.querySelectorAll('.topic-item.active').forEach(item => {
                    item.classList.remove('active');
                });
                el.classList.add('active');

                this.moveTopicPointer(groupName, 1);
            });
            topicsList.appendChild(el);
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
                    const topicItems = document.querySelectorAll('.topic-item');
                    for (let item of topicItems) {
                        const nameEl = item.querySelector('.topic-name');
                        if (nameEl && nameEl.textContent.trim() === topicName) {
                            topicElement = item;
                            break;
                        }
                    }

                    if (topicElement && typeof topicElement.onclick === 'function') {
                        topicElement.onclick();
                    }
                }
            });
        });
    }

    highlightSentences(sentenceIndices, color, focusIndex) {
        if (!sentenceIndices || sentenceIndices.length === 0) return;

        document.querySelectorAll('.sentence-group.highlighted').forEach(span => {
            span.classList.remove('highlighted');
        });

        const highlightedElements = [];
        sentenceIndices.forEach(sentNum => {
            const spans = document.querySelectorAll('.sentence-group[data-sentence="' + sentNum + '"]');
            spans.forEach(span => {
                span.classList.add('highlighted');
                highlightedElements.push(span);
            });
        });

        if (highlightedElements.length > 0) {
            const targetIdx = Number.isFinite(focusIndex) ? Math.max(0, Math.min(highlightedElements.length - 1, focusIndex)) : 0;
            const targetSpan = highlightedElements[targetIdx];
            if (targetSpan) {
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

                const topicItems = document.querySelectorAll('.topic-item');
                for (let item of topicItems) {
                    const nameEl = item.querySelector('.topic-name');
                    if (nameEl && nameEl.textContent.trim() === topicName) {
                        item.classList.add('active');
                        item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        break;
                    }
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
