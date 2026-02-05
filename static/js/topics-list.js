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
            renderTopicsPieChart();
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
        renderTopicsPieChart();
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
            renderTopicsPieChart();
        }, 150);
    });
}

function renderTopicsPieChart() {
    const data = Array.isArray(window.topics_chart_data) ? window.topics_chart_data : [];
    const container = document.getElementById('topics_pie_chart');
    const legend = document.getElementById('topics_pie_legend');

    if (!container || !legend) {
        return;
    }

    container.innerHTML = '';
    legend.innerHTML = '';

    if (typeof d3 === 'undefined') {
        container.textContent = 'Pie chart is unavailable because D3.js is not loaded.';
        return;
    }

    if (!data.length) {
        container.textContent = 'No topics available for this page.';
        return;
    }

    const width = Math.max(container.clientWidth, 320);
    const height = Math.max(container.clientHeight, 320);
    const radius = Math.min(width, height) / 2 - 10;

    const colorRange = d3.quantize(d3.interpolateTurbo, Math.max(data.length, 3));
    const color = d3.scaleOrdinal()
        .domain(data.map((d) => d.topic))
        .range(colorRange);

    const svg = d3.select(container)
        .append('svg')
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('class', 'topics-pie-svg');

    const chartGroup = svg.append('g')
        .attr('transform', `translate(${width / 2}, ${height / 2})`);

    const pie = d3.pie()
        .value((d) => d.count)
        .sort(null);

    const arc = d3.arc()
        .innerRadius(0)
        .outerRadius(radius);

    let tooltip = container.querySelector('.topics-pie-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.className = 'topics-pie-tooltip';
        tooltip.style.display = 'none';
        container.appendChild(tooltip);
    }

    chartGroup
        .selectAll('path')
        .data(pie(data))
        .enter()
        .append('path')
        .attr('d', arc)
        .attr('fill', (d) => color(d.data.topic))
        .attr('stroke', '#fff')
        .attr('stroke-width', 1)
        .on('mousemove', (event, d) => {
            const pointer = d3.pointer(event, container);
            tooltip.textContent = `${d.data.topic} (${d.data.count})`;
            tooltip.style.left = `${pointer[0] + 12}px`;
            tooltip.style.top = `${pointer[1] + 12}px`;
            tooltip.style.display = 'block';
        })
        .on('mouseleave', () => {
            tooltip.style.display = 'none';
        });

    data.forEach((entry) => {
        const item = document.createElement('div');
        item.className = 'topics-pie-legend-item';
        const swatch = document.createElement('span');
        swatch.className = 'topics-pie-legend-color';
        swatch.style.backgroundColor = color(entry.topic);
        const label = document.createElement('span');
        label.textContent = `${entry.topic} (${entry.count})`;
        item.appendChild(swatch);
        item.appendChild(label);
        legend.appendChild(item);
    });
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

document.addEventListener('DOMContentLoaded', () => {
    initTopicTabs();
    initTopicsSearch();
    initTopicTreeControls();
});
