'use strict';

import TopicsSunburst from './topics-sunburst.js';

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
        'topics-chart': document.getElementById('tab-topics-chart')
    };

    let chartRendered = false;

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
        if (!chartRendered) {
            return;
        }
        if (resizeTimeout) {
            clearTimeout(resizeTimeout);
        }
        resizeTimeout = setTimeout(() => {
            renderTopicsSunburstChart();
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
        const sunburst = new TopicsSunburst(data);
        sunburst.render('#topics_sunburst_chart');
    } catch (error) {
        console.error('Error rendering sunburst chart:', error);
        container.textContent = 'Error rendering sunburst chart: ' + error.message;
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
