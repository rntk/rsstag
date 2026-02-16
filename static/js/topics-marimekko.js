'use strict';

/**
 * Topics Marimekko Chart Component
 *
 * For each top-level topic, renders a Marimekko (mosaic) chart where:
 * - Each subtopic is a column (bar)
 * - Column width is proportional to the number of children (sub-subtopics)
 * - Inside each column, sub-subtopics are stacked vertically
 * - Sub-bar height is proportional to the sentence count (value)
 * - Paginated when there are too many subtopics
 */

const PALETTE = [
    '#7ba3cc', '#e8a87c', '#85bb65', '#c9a0dc',
    '#d4a5a5', '#a0c4a9', '#cfb997', '#9db4c0',
    '#c2b280', '#b5c7d3', '#d4a76a', '#a5b8d0',
    '#c4d4a0', '#d0b4c8', '#b3cfa0', '#c8b8a0',
];

const MAX_COLUMNS_PER_PAGE = 10;
const BOTTOM_LABEL_HEIGHT = 140;
const TOP_PADDING = 20;
const COL_GAP = 6;
const MIN_COL_WIDTH = 80;
const FONT_SIZE_LABEL = 16;
const FONT_SIZE_BOTTOM = 15;
const MIN_ROW_HEIGHT = FONT_SIZE_LABEL + 8;
const MIN_COL_HEIGHT = FONT_SIZE_LABEL + 10;

class TopicsMarimekko {
    constructor() {
        this.currentPage = 0;
        this.allColumns = [];
        this.totalPages = 0;
        this.container = null;
        this.maxColValue = 1;
    }

    _colorForBar(colIndex, rowIndex, rowCount) {
        const base = PALETTE[colIndex % PALETTE.length];
        const r = parseInt(base.slice(1, 3), 16);
        const g = parseInt(base.slice(3, 5), 16);
        const b = parseInt(base.slice(5, 7), 16);

        const factor = rowCount > 1
            ? 0.7 + 0.6 * (rowIndex / (rowCount - 1))
            : 1.0;
        const clamp = (v) => Math.min(255, Math.max(0, Math.round(v)));
        return `rgb(${clamp(r * factor)}, ${clamp(g * factor)}, ${clamp(b * factor)})`;
    }

    render(selector, topicNode) {
        const container = document.querySelector(selector);
        if (!container) return;
        this.container = container;

        const children = (topicNode && topicNode.children) || [];
        if (children.length === 0) {
            container.textContent = 'No subtopics.';
            return;
        }

        this.allColumns = children.map((sub, i) => {
            const subChildren = Array.isArray(sub.children) ? sub.children : [];
            const width = subChildren.length > 0 ? subChildren.length : 1;
            const getValue = (c) => {
                if (c.text_length !== undefined && c.text_length !== null) return c.text_length;
                if (c.value !== undefined && c.value !== null) return c.value;
                if (c.count !== undefined && c.count !== null) return c.count;
                return 1;
            };
            const rows = subChildren.length > 0
                ? subChildren.map((c) => ({
                    name: c.name || '',
                    value: getValue(c),
                    topicPath: c._topicPath || '',
                    topicPosts: Array.isArray(c._topicPosts) ? c._topicPosts : [],
                }))
                : [{
                    name: sub.name || '',
                    value: getValue(sub),
                    topicPath: sub._topicPath || '',
                    topicPosts: Array.isArray(sub._topicPosts) ? sub._topicPosts : [],
                }];
            return { name: sub.name || '', width, rows, originalIndex: i };
        });

        // Global max for consistent Y-axis scaling across pages
        this.maxColValue = Math.max(
            ...this.allColumns.map((c) => c.rows.reduce((s, r) => s + r.value, 0)),
            1
        );

        this.totalPages = Math.ceil(this.allColumns.length / MAX_COLUMNS_PER_PAGE);
        this.currentPage = 0;

        this._renderPage();
    }

    _getPageColumns() {
        const start = this.currentPage * MAX_COLUMNS_PER_PAGE;
        return this.allColumns.slice(start, start + MAX_COLUMNS_PER_PAGE);
    }

    _renderPage() {
        const container = this.container;
        container.innerHTML = '';

        if (this.totalPages > 1) {
            container.appendChild(this._buildNav());
        }

        const columns = this._getPageColumns();
        container.appendChild(this._buildSvg(columns));
    }

    _buildNav() {
        const nav = document.createElement('div');
        nav.className = 'marimekko-nav';

        const prevBtn = document.createElement('button');
        prevBtn.textContent = '\u2190 Previous';
        prevBtn.disabled = this.currentPage === 0;
        prevBtn.className = 'marimekko-nav-btn';
        prevBtn.addEventListener('click', () => {
            if (this.currentPage > 0) {
                this.currentPage--;
                this._renderPage();
            }
        });

        const info = document.createElement('span');
        info.className = 'marimekko-nav-info';
        const start = this.currentPage * MAX_COLUMNS_PER_PAGE + 1;
        const end = Math.min(start + MAX_COLUMNS_PER_PAGE - 1, this.allColumns.length);
        info.textContent = `Page ${this.currentPage + 1} / ${this.totalPages}  (subtopics ${start}\u2013${end} of ${this.allColumns.length})`;

        const nextBtn = document.createElement('button');
        nextBtn.textContent = 'Next \u2192';
        nextBtn.disabled = this.currentPage >= this.totalPages - 1;
        nextBtn.className = 'marimekko-nav-btn';
        nextBtn.addEventListener('click', () => {
            if (this.currentPage < this.totalPages - 1) {
                this.currentPage++;
                this._renderPage();
            }
        });

        nav.appendChild(prevBtn);
        nav.appendChild(info);
        nav.appendChild(nextBtn);
        return nav;
    }

    _buildSvg(columns) {
        const chartWidth = Math.max(this.container.clientWidth, window.innerWidth * 0.9, 1000);
        const baseChartHeight = Math.round(window.innerHeight * 0.85);
        const baseBarAreaHeight = baseChartHeight - BOTTOM_LABEL_HEIGHT - TOP_PADDING;

        const totalWidthUnits = columns.reduce((s, c) => s + c.width, 0);
        const totalGap = COL_GAP * (columns.length - 1);
        const availableWidth = chartWidth - totalGap;

        const requiredBarAreaHeight = columns.reduce((maxHeight, col) => {
            const colTotalValue = col.rows.reduce((sum, row) => sum + row.value, 0);
            const proportionalHeight = (colTotalValue / this.maxColValue) * baseBarAreaHeight;
            const minReadableHeight = Math.max(MIN_COL_HEIGHT, col.rows.length * MIN_ROW_HEIGHT);
            return Math.max(maxHeight, proportionalHeight, minReadableHeight);
        }, baseBarAreaHeight);
        const barAreaHeight = Math.max(baseBarAreaHeight, requiredBarAreaHeight);
        const chartHeight = TOP_PADDING + barAreaHeight + BOTTOM_LABEL_HEIGHT;

        const svgNs = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(svgNs, 'svg');
        svg.setAttribute('width', chartWidth);
        svg.setAttribute('height', chartHeight);
        svg.style.display = 'block';

        let x = 0;
        columns.forEach((col, colIdx) => {
            const colWidth = Math.max(
                (col.width / totalWidthUnits) * availableWidth,
                MIN_COL_WIDTH
            );
            const colTotalValue = col.rows.reduce((s, r) => s + r.value, 0);
            const proportionalColHeight = (colTotalValue / this.maxColValue) * barAreaHeight;
            const minReadableColHeight = Math.max(MIN_COL_HEIGHT, col.rows.length * MIN_ROW_HEIGHT);
            const colHeight = Math.max(proportionalColHeight, minReadableColHeight);
            const rowHeights = this._computeRowHeights(col.rows, colHeight);

            let y = TOP_PADDING + (barAreaHeight - colHeight);

            // Use originalIndex for consistent color across pages
            const colorIdx = col.originalIndex;

            col.rows.forEach((row, rowIdx) => {
                const rowHeight = rowHeights[rowIdx];

                const rect = document.createElementNS(svgNs, 'rect');
                rect.setAttribute('x', x);
                rect.setAttribute('y', y);
                rect.setAttribute('width', colWidth);
                rect.setAttribute('height', Math.max(rowHeight, 1));
                rect.setAttribute('fill', this._colorForBar(colorIdx, rowIdx, col.rows.length));
                rect.setAttribute('stroke', '#fff');
                rect.setAttribute('stroke-width', '1');

                const title = document.createElementNS(svgNs, 'title');
                title.textContent = `${row.name}\ntext length: ${row.value}`;
                rect.appendChild(title);
                svg.appendChild(rect);

                // Label inside bar
                if (rowHeight >= MIN_ROW_HEIGHT && colWidth >= 50) {
                    const fontSize = Math.min(FONT_SIZE_LABEL, colWidth / 4.5);
                    const charWidth = fontSize * 0.55;
                    const maxChars = Math.max(Math.floor((colWidth - 10) / charWidth), 3);
                    const label = row.name.length > maxChars
                        ? row.name.slice(0, maxChars - 1) + '\u2026'
                        : row.name;

                    const topicPath = typeof row.topicPath === 'string' ? row.topicPath : '';
                    const topicPosts = Array.isArray(row.topicPosts)
                        ? row.topicPosts.filter(Boolean)
                        : [];
                    const canBuildLink = topicPath && topicPosts.length > 0;
                    const snippetsUrl = canBuildLink
                        ? `/post-grouped-snippets/${encodeURIComponent(topicPosts.join('_'))}?topic=${encodeURIComponent(topicPath)}`
                        : null;

                    const text = document.createElementNS(svgNs, 'text');
                    text.setAttribute('x', x + 4);
                    text.setAttribute('y', y + rowHeight / 2 + fontSize * 0.35);
                    text.setAttribute('font-size', fontSize);
                    text.setAttribute('fill', '#222');
                    text.setAttribute('text-decoration', 'underline');
                    text.textContent = label;

                    if (snippetsUrl) {
                        const link = document.createElementNS(svgNs, 'a');
                        link.setAttribute('href', snippetsUrl);
                        link.setAttribute('target', '_self');
                        link.setAttribute('aria-label', `Open snippets for ${row.name || topicPath}`);
                        link.appendChild(text);
                        svg.appendChild(link);
                    } else {
                        text.setAttribute('pointer-events', 'none');
                        svg.appendChild(text);
                    }
                }

                y += rowHeight;
            });

            // Bottom label (rotated)
            const labelX = x + colWidth / 2;
            const labelY = TOP_PADDING + barAreaHeight + 14;
            const label = document.createElementNS(svgNs, 'text');
            label.setAttribute('x', labelX);
            label.setAttribute('y', labelY);
            label.setAttribute('font-size', FONT_SIZE_BOTTOM);
            label.setAttribute('fill', '#333');
            label.setAttribute('text-anchor', 'start');
            label.setAttribute('transform', `rotate(40, ${labelX}, ${labelY})`);

            const maxLabelLen = 35;
            const colLabel = col.name.length > maxLabelLen
                ? col.name.slice(0, maxLabelLen - 1) + '\u2026'
                : col.name;
            label.textContent = `${colLabel} (${col.width})`;
            svg.appendChild(label);

            x += colWidth + COL_GAP;
        });

        return svg;
    }

    _computeRowHeights(rows, colHeight) {
        const rowCount = rows.length;
        if (rowCount === 0) {
            return [];
        }

        const minTotal = rowCount * MIN_ROW_HEIGHT;
        if (colHeight <= minTotal) {
            return new Array(rowCount).fill(colHeight / rowCount);
        }

        const values = rows.map((row) => Math.max(0, Number(row.value) || 0));
        const valueSum = values.reduce((sum, value) => sum + value, 0);
        const extraHeight = colHeight - minTotal;

        if (valueSum <= 0) {
            return new Array(rowCount).fill(colHeight / rowCount);
        }

        return values.map((value) => MIN_ROW_HEIGHT + (value / valueSum) * extraHeight);
    }
}

export default TopicsMarimekko;
