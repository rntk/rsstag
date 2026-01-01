'use strict';
import Sunburst from 'sunburst-chart';

export default class TagSunburst {
    constructor(data) {
        this.data = data;
        this.base_color = "#d7d7af";
        this.color_range = 20;
        this.maxChildrenPerChart = 50; // Split if more than this many children
        this.currentPage = 0;
        this.charts = [];
        this.splitData = null;
        this.initializeCharts();
    }

    initializeCharts() {
        // Prepare children for sunburst if they are split into before/after
        if (!this.data.children && (this.data.before || this.data.after)) {
            this.data.children = [
                ...(this.data.before || []),
                ...(this.data.after || [])
            ];
        }

        // Check if we need to split the data
        if (this.data.children && this.data.children.length > this.maxChildrenPerChart) {
            this.splitData = this.createSplitData();
            this.charts = this.splitData.map(() => Sunburst());
        } else {
            this.charts = [Sunburst()];
            this.splitData = [this.data];
        }
    }

    createSplitData() {
        const children = this.data.children;
        const chunks = [];
        
        for (let i = 0; i < children.length; i += this.maxChildrenPerChart) {
            const chunk = children.slice(i, i + this.maxChildrenPerChart);
            chunks.push({
                ...this.data,
                children: chunk,
                _pageInfo: {
                    current: Math.floor(i / this.maxChildrenPerChart),
                    total: Math.ceil(children.length / this.maxChildrenPerChart),
                    startIndex: i,
                    endIndex: Math.min(i + this.maxChildrenPerChart, children.length)
                }
            });
        }
        
        return chunks;
    }

    render(selector) {
        const container = document.querySelector(selector);
        if (!container) return;

        // Clear existing content
        container.innerHTML = '';

        // Create chart container
        const chartContainer = document.createElement('div');
        chartContainer.id = 'sunburst-chart-container';
        container.appendChild(chartContainer);

        // Create navigation if we have multiple charts
        if (this.splitData.length > 1) {
            this.createNavigation(container);
        }

        // Render current chart
        this.renderCurrentChart(chartContainer);
    }

    createNavigation(container) {
        const nav = document.createElement('div');
        nav.className = 'sunburst-navigation';
        nav.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 5px;
        `;

        const info = this.splitData[this.currentPage]._pageInfo;
        
        // Previous button
        const prevBtn = document.createElement('button');
        prevBtn.textContent = '← Previous';
        prevBtn.disabled = this.currentPage === 0;
        prevBtn.onclick = () => this.navigateToPage(this.currentPage - 1);
        prevBtn.style.cssText = `
            padding: 5px 10px;
            border: 1px solid #ccc;
            background: ${prevBtn.disabled ? '#f0f0f0' : '#fff'};
            cursor: ${prevBtn.disabled ? 'not-allowed' : 'pointer'};
            border-radius: 3px;
        `;

        // Page info
        const pageInfo = document.createElement('span');
        pageInfo.textContent = `Page ${info.current + 1} of ${info.total} (showing ${info.startIndex + 1}-${info.endIndex} of ${this.data.children.length} tags)`;
        pageInfo.style.cssText = 'font-weight: bold; margin: 0 15px;';

        // Next button
        const nextBtn = document.createElement('button');
        nextBtn.textContent = 'Next →';
        nextBtn.disabled = this.currentPage === this.splitData.length - 1;
        nextBtn.onclick = () => this.navigateToPage(this.currentPage + 1);
        nextBtn.style.cssText = `
            padding: 5px 10px;
            border: 1px solid #ccc;
            background: ${nextBtn.disabled ? '#f0f0f0' : '#fff'};
            cursor: ${nextBtn.disabled ? 'not-allowed' : 'pointer'};
            border-radius: 3px;
        `;

        nav.appendChild(prevBtn);
        nav.appendChild(pageInfo);
        nav.appendChild(nextBtn);
        container.appendChild(nav);
    }

    navigateToPage(pageIndex) {
        if (pageIndex < 0 || pageIndex >= this.splitData.length) return;
        
        this.currentPage = pageIndex;
        const chartContainer = document.querySelector('#sunburst-chart-container');
        if (chartContainer) {
            this.renderCurrentChart(chartContainer);
        }
        
        // Update navigation
        const container = chartContainer.parentElement;
        const nav = container.querySelector('.sunburst-navigation');
        if (nav) {
            nav.remove();
            this.createNavigation(container);
        }
    }

    renderCurrentChart(container) {
        // Clear container
        container.innerHTML = '';
        
        const currentData = this.splitData[this.currentPage];
        const currentChart = this.charts[this.currentPage];
        
        currentChart
            .data(currentData)
            .color(d => generateSimilarColor(this.base_color, this.color_range))
            .minSliceAngle(0)
            .onClick((d, event) => {
                if (d) {
                    let new_tag = encodeURIComponent(currentData["name"] + ' ' + d.name);
                    if (event.ctrlKey || event.metaKey) {
                        // open new tab/window
                        window.open('/entity/' + new_tag, '_blank');
                    } else {
                        window.location.href = '/sunburst/' + new_tag;
                    }
                } else {
                    let tags = currentData["name"].split(' ');
                    if (tags.length > 1) {
                        tags.pop();
                        window.location.href = '/sunburst/' + encodeURIComponent(tags.join(' '));
                    } else {
                        window.location.href = '/';
                    }
                }
            })(container);
    }
}

function generateSimilarColor(baseColor, range) {
    // Helper function to ensure a value is within 0-255
    const clamp = (value) => Math.min(255, Math.max(0, value));

    // Convert base color to RGB
    const baseRGB = hexToRGB(baseColor);

    // Generate new RGB values within the specified range
    const newRGB = baseRGB.map(value => {
        const min = Math.max(0, value - range);
        const max = Math.min(255, value + range);
        return clamp(Math.floor(Math.random() * (max - min + 1) + min));
    });
  // Convert back to hex
  return rgbToHex(newRGB);
}

// Helper function to convert hex to RGB
function hexToRGB(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return [r, g, b];
}

// Helper function to convert RGB to hex
function rgbToHex(rgb) {
    return '#' + rgb.map(x => {
    const hex = x.toString(16);
    return hex.length === 1 ? '0' + hex : hex;
    }).join('');
}