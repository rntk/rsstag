'use strict';

import TopicsSunburst from './topics-sunburst.js';
import TopicsMarimekko from './topics-marimekko.js';

// Topics List functionality

function togglePosts(index, event) {
    const postsElement = document.getElementById('posts_' + index);
    const button = event ? event.currentTarget : (window.event ? window.event.target : null);

    if (!postsElement) return;

    const isHidden = postsElement.style.display === 'none' ||
        window.getComputedStyle(postsElement).display === 'none';

    if (isHidden) {
        postsElement.style.display = 'block';
        if (button) {
            button.textContent = button.textContent.replace('[', '[-');
        }
    } else {
        postsElement.style.display = 'none';
        if (button) {
            button.textContent = button.textContent.replace('[-', '[');
        }
    }
}

function initTopicTabs() {
    const tabsContainer = document.querySelector('.topics-tabs');
    if (!tabsContainer) {
        return;
    }

    const tabs = tabsContainer.querySelectorAll('.tab-btn');
    const tabContents = {
        'topics-list': document.getElementById('tab-topics-list'),
        'topics-chart': document.getElementById('tab-topics-chart'),
        'topics-marimekko': document.getElementById('tab-topics-marimekko')
    };

    let chartRendered = false;
    let marimekkoRendered = false;

    const activateTab = (tabName) => {
        tabs.forEach((tab) => {
            tab.classList.toggle('active', tab.getAttribute('data-tab') === tabName);
        });
        Object.keys(tabContents).forEach((key) => {
            const content = tabContents[key];
            if (content) {
                content.classList.toggle('active', key === tabName);
            }
        });
        if (tabName === 'topics-chart' && !chartRendered) {
            renderTopicsSunburstChart();
            chartRendered = true;
        }
        if (tabName === 'topics-marimekko' && !marimekkoRendered) {
            renderTopicsMarimekkoChart();
            marimekkoRendered = true;
        }
    };

    tabs.forEach((tab) => {
        tab.addEventListener('click', () => {
            const tabName = tab.getAttribute('data-tab');
            if (tabName) {
                activateTab(tabName);
            }
        });
    });

    const activeTab = tabsContainer.querySelector('.tab-btn.active');
    if (activeTab && activeTab.getAttribute('data-tab') === 'topics-chart') {
        renderTopicsSunburstChart();
        chartRendered = true;
    }

    let resizeTimeout = 0;
    window.addEventListener('resize', () => {
        if (!chartRendered && !marimekkoRendered) {
            return;
        }
        if (resizeTimeout) {
            clearTimeout(resizeTimeout);
        }
        resizeTimeout = setTimeout(() => {
            if (chartRendered) {
                renderTopicsSunburstChart();
            }
            if (marimekkoRendered) {
                renderTopicsMarimekkoChart();
            }
        }, 150);
    });
}

function renderTopicsSunburstChart() {
    const data = window.sunburst_data;
    const container = document.getElementById('topics_sunburst_chart');

    if (!container) {
        return;
    }

    container.innerHTML = '';

    if (!data || !data.children || data.children.length === 0) {
        container.textContent = 'No topics available for this page.';
        return;
    }

    try {
        const chartGroups = buildTopicsSunburstGroups(data);
        renderTopicsSunburstGroups(container, chartGroups);
    } catch (error) {
        console.error('Error rendering sunburst chart:', error);
        container.textContent = 'Error rendering sunburst chart: ' + error.message;
    }
}

function buildTopicsSunburstGroups(data) {
    const topLevelTopics = Array.isArray(data.children) ? data.children : [];
    const MIN_SUBTOPICS_FOR_BIG_CHART = 8;
    const MIN_DESCENDANTS_FOR_BIG_CHART = 20;

    if (topLevelTopics.length === 0) {
        return [];
    }

    const getDescendantsCount = (node) => {
        if (!node || !Array.isArray(node.children) || node.children.length === 0) {
            return 0;
        }
        return node.children.reduce((acc, child) => acc + 1 + getDescendantsCount(child), 0);
    };

    const bigTopics = [];
    const tailTopics = [];

    topLevelTopics.forEach((topic) => {
        const directSubtopics = Array.isArray(topic.children) ? topic.children.length : 0;
        const descendants = getDescendantsCount(topic);
        const isBigTopic = directSubtopics >= MIN_SUBTOPICS_FOR_BIG_CHART ||
            descendants >= MIN_DESCENDANTS_FOR_BIG_CHART;

        if (isBigTopic) {
            bigTopics.push(topic);
        } else {
            tailTopics.push(topic);
        }
    });

    if (bigTopics.length === 0) {
        return [{ title: 'All Topics', data }];
    }

    const groups = bigTopics.map((topic) => ({
        title: topic.name,
        data: topic
    }));

    if (tailTopics.length > 0) {
        groups.push({
            title: 'Tail Topics',
            data: {
                name: 'Tail Topics',
                children: tailTopics
            }
        });
    }

    return groups;
}

function renderTopicsSunburstGroups(container, chartGroups) {
    if (!Array.isArray(chartGroups) || chartGroups.length === 0) {
        container.textContent = 'No topics available for this page.';
        return;
    }

    const groupsContainer = document.createElement('div');
    groupsContainer.className = 'topics-sunburst-groups';
    container.appendChild(groupsContainer);

    chartGroups.forEach((group, index) => {
        const section = document.createElement('section');
        section.className = 'topics-sunburst-group';

        const heading = document.createElement('h3');
        heading.className = 'topics-sunburst-group-title';
        heading.textContent = group.title;
        section.appendChild(heading);

        const chartHost = document.createElement('div');
        chartHost.className = 'topics-sunburst-chart';
        chartHost.id = `topics_sunburst_chart_${index}`;
        section.appendChild(chartHost);

        groupsContainer.appendChild(section);

        const sunburst = new TopicsSunburst(group.data);
        sunburst.render(`#${chartHost.id}`);
    });
}

function renderTopicsMarimekkoChart() {
    const data = window.sunburst_data;
    const container = document.getElementById('topics_marimekko_chart');

    if (!container) {
        return;
    }

    container.innerHTML = '';

    if (!data || !data.children || data.children.length === 0) {
        container.textContent = 'No topics available for this page.';
        return;
    }

    try {
        const topLevelTopics = data.children;
        const groupsContainer = document.createElement('div');
        groupsContainer.className = 'topics-marimekko-groups';
        container.appendChild(groupsContainer);

        topLevelTopics.forEach((topic, index) => {
            if (!topic.children || topic.children.length === 0) {
                return;
            }

            const section = document.createElement('section');
            section.className = 'topics-marimekko-group';

            const heading = document.createElement('h3');
            heading.className = 'topics-marimekko-group-title';
            heading.textContent = topic.name;
            section.appendChild(heading);

            const chartHost = document.createElement('div');
            chartHost.className = 'topics-marimekko-chart-host';
            chartHost.id = `topics_marimekko_chart_${index}`;
            section.appendChild(chartHost);

            groupsContainer.appendChild(section);

            const chart = new TopicsMarimekko();
            chart.render(`#${chartHost.id}`, topic);
        });
    } catch (error) {
        console.error('Error rendering marimekko chart:', error);
        container.textContent = 'Error rendering marimekko chart: ' + error.message;
    }
}

function initTopicsSearch() {
    const searchInput = document.getElementById('topics_search_field');
    const resultsContainer = document.getElementById('topics_search_result');
    if (!searchInput || !resultsContainer) {
        return;
    }

    let debounceTimer = 0;
    let lastRequest = '';
    const debounceMs = 500;

    const renderSuggestions = (items) => {
        resultsContainer.innerHTML = '';
        if (!Array.isArray(items) || items.length === 0) {
            resultsContainer.style.display = 'none';
            return;
        }
        resultsContainer.style.display = 'block';
        items.forEach((item) => {
            const row = document.createElement('p');
            row.className = 'search_result_item';
            const link = document.createElement('a');
            link.href = item.url;
            link.textContent = `${item.topic} (${item.count})`;
            row.appendChild(link);
            if (item.snippets_url) {
                row.appendChild(document.createTextNode(' '));
                const snippetsLink = document.createElement('a');
                snippetsLink.href = item.snippets_url;
                snippetsLink.textContent = '...';
                row.appendChild(snippetsLink);
            }
            resultsContainer.appendChild(row);
        });
    };

    const fetchSuggestions = (request) => {
        if (!request) {
            renderSuggestions([]);
            return;
        }
        lastRequest = request;
        const form = new FormData();
        form.append('req', request);
        fetch('/topics-search', {
            method: 'POST',
            credentials: 'include',
            body: form,
        })
            .then((response) => response.json())
            .then((data) => {
                if (lastRequest !== request) {
                    return;
                }
                if (data && data.data) {
                    renderSuggestions(data.data);
                } else {
                    renderSuggestions([]);
                }
            })
            .catch(() => {
                renderSuggestions([]);
            });
    };

    searchInput.addEventListener('input', (event) => {
        const value = event.target.value.trim();
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }
        debounceTimer = setTimeout(() => {
            fetchSuggestions(value);
        }, debounceMs);
    });

    document.addEventListener('click', (event) => {
        if (!resultsContainer.contains(event.target) && event.target !== searchInput) {
            resultsContainer.style.display = 'none';
        }
    });
}

function initTopicTreeControls() {
    const container = document.getElementById('topics_list_container');
    const foldAllButton = document.getElementById('topics_fold_all');
    const unfoldAllButton = document.getElementById('topics_unfold_all');
    if (!container || !foldAllButton || !unfoldAllButton) {
        return;
    }

    const setAllDetailsState = (isOpen) => {
        const details = container.querySelectorAll('.topic-tree-details');
        details.forEach((node) => {
            node.open = isOpen;
        });
    };

    foldAllButton.addEventListener('click', () => {
        setAllDetailsState(false);
    });

    unfoldAllButton.addEventListener('click', () => {
        setAllDetailsState(true);
    });
}

// Initialize topics page
export function initTopicsPage() {
    initTopicTabs();
    initTopicsSearch();
    initTopicTreeControls();
}
