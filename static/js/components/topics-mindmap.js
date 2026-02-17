'use strict';

import * as d3 from 'd3';

/**
 * Topics Mindmap - Interactive collapsible horizontal tree
 * Uses D3 tree layout with zoom/pan and click-to-collapse/expand.
 * Leaf nodes can expand inline to show topic snippets.
 */
export default class TopicsMindmap {
  constructor() {
    this.margin = { top: 20, right: 200, bottom: 20, left: 120 };
    this.nodeHeight = 32;
    this.nodeSpacingY = 8;
    this.snippetPanelWidth = 420;
    this.snippetItemHeight = 80;
    this.snippetMaxHeight = 500;
    this.duration = 400;
    this.i = 0; // node id counter
    this.root = null;
    this.svg = null;
    this.gLinks = null;
    this.gNodes = null;
    this.zoom = null;
    this.baseColor = '#d7d7af';
    this.nodeColors = ['#c8d0e8', '#d7d7af', '#c8e0c8', '#e0d0c8', '#d8c8e0', '#c8dce0'];
  }

  render(selector, data) {
    const container = document.querySelector(selector);
    if (!container) return;
    container.innerHTML = '';

    const width = container.clientWidth || window.innerWidth;
    const height = window.innerHeight - 140;

    // Build hierarchy: synthetic hidden root wrapping top-level topics
    const hierarchyData = {
      name: '__root__',
      children: data.children || []
    };

    this.root = d3.hierarchy(hierarchyData);
    this.root.x0 = height / 2;
    this.root.y0 = 0;

    // Assign unique ids
    this.root.descendants().forEach((d) => {
      d.id = this.i++;
    });

    // Collapse beyond depth 1 (root's grandchildren and below)
    this.root.children.forEach((child) => {
      this._collapseAll(child);
    });

    // Create SVG
    this.svg = d3
      .select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'topics-mindmap-svg');

    // Add zoom
    this.zoom = d3
      .zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        this.gMain.attr('transform', event.transform);
      });

    this.svg.call(this.zoom);

    this.gMain = this.svg.append('g').attr('class', 'mindmap-main');
    this.gLinks = this.gMain.append('g').attr('class', 'mindmap-links');
    this.gNodes = this.gMain.append('g').attr('class', 'mindmap-nodes');

    // Initial update
    this._update(this.root);

    // Fit to view after initial render
    setTimeout(() => this._fitToView(), 100);

    // Add reset view button
    this._addResetButton(container);
  }

  _collapseAll(d) {
    if (d.children) {
      d._children = d.children;
      d._children.forEach((c) => this._collapseAll(c));
      d.children = null;
    }
  }

  _expandOne(d) {
    if (d._children) {
      d.children = d._children;
      d._children = null;
    }
  }

  _toggleChildren(d) {
    if (d.children) {
      d._children = d.children;
      d.children = null;
    } else if (d._children) {
      d.children = d._children;
      d._children = null;
    }
  }

  _isLeafTopic(d) {
    const hasOrigChildren = d.data.children && d.data.children.length > 0;
    const hasPosts = d.data._topicPosts && d.data._topicPosts.length > 0;
    return !hasOrigChildren && hasPosts;
  }

  _isSnippetNode(d) {
    return d.data._isSnippetNode === true;
  }

  _nodeWidth(d) {
    if (this._isSnippetNode(d)) {
      return this.snippetPanelWidth;
    }
    const name = d.data.name || '';
    const displayName = name.length > 25 ? name.slice(0, 25) + '...' : name;
    return Math.max(displayName.length * 7.5 + 40, 80);
  }

  _nodeHeightFor(d) {
    if (this._isSnippetNode(d)) {
      const snippets = d.data._snippets || [];
      const contentH = 36 + snippets.length * this.snippetItemHeight;
      return Math.min(contentH, this.snippetMaxHeight);
    }
    return this.nodeHeight;
  }

  _depthColor(depth) {
    return this.nodeColors[(depth - 1) % this.nodeColors.length] || this.baseColor;
  }

  _hasArrow(d) {
    if (this._isSnippetNode(d)) return false;
    const hasBranchChildren = d.data.children && d.data.children.length > 0;
    const isLeaf = this._isLeafTopic(d);
    return hasBranchChildren || isLeaf;
  }

  async _loadSnippets(d) {
    if (d.data._snippetsLoaded) {
      this._toggleChildren(d);
      this._update(d);
      return;
    }

    const topicPosts = d.data._topicPosts;
    const topicPath = d.data._topicPath;
    if (!topicPosts || !topicPath) return;

    const postIds = topicPosts.join('_');
    const url = `/api/topic-snippets/${postIds}?topic=${encodeURIComponent(topicPath)}`;

    // Show loading state
    d.data._loading = true;
    this._update(d);

    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      d.data._loading = false;
      d.data._snippetsLoaded = true;

      const snippetChild = {
        name: '__snippets__',
        _isSnippetNode: true,
        _snippets: data.snippets || [],
        _parentTopicPath: topicPath,
      };

      // Create as a D3 hierarchy child
      const childNode = d3.hierarchy(snippetChild);
      childNode.depth = d.depth + 1;
      childNode.parent = d;
      childNode.id = this.i++;

      d.children = [childNode];
      d._children = null;

      this._update(d);
    } catch (err) {
      d.data._loading = false;
      console.error('Failed to load snippets:', err);
      this._update(d);
    }
  }

  _buildSnippetHTML(d) {
    const snippets = d.data._snippets || [];
    const panelH = this._nodeHeightFor(d);
    const scrollH = panelH - 36;

    let html = `<div class="mindmap-snippet-container" style="width:${this.snippetPanelWidth - 16}px;max-height:${panelH}px;">`;
    html += `<div class="mindmap-snippet-header">`;
    html += `<span class="mindmap-snippet-title">${snippets.length} sentence${snippets.length !== 1 ? 's' : ''}</span>`;
    html += `<div class="mindmap-snippet-header-btns">`;
    html += `<button class="mindmap-snippet-batch-btn" data-action="read-all">Read All</button>`;
    html += `<button class="mindmap-snippet-batch-btn" data-action="unread-all">Unread All</button>`;
    html += `</div></div>`;
    html += `<div class="mindmap-snippet-list" style="max-height:${scrollH}px;overflow-y:auto;">`;

    snippets.forEach((s, i) => {
      const readClass = s.read ? 'read' : '';
      const btnLabel = s.read ? 'Unread' : 'Read';
      const btnClass = s.read ? 'snippet-tag-read' : 'snippet-tag-unread';
      const textPreview = s.text.length > 200 ? s.text.slice(0, 200) + '...' : s.text;
      html += `<div class="mindmap-snippet-item ${readClass}" data-index="${i}">`;
      html += `<div class="mindmap-snippet-text">${this._escapeHtml(textPreview)}</div>`;
      html += `<div class="mindmap-snippet-meta">`;
      html += `<span class="mindmap-snippet-source" title="${this._escapeHtml(s.post_title)}">${this._escapeHtml(this._truncate(s.post_title, 30))}</span>`;
      html += `<button class="mindmap-snippet-toggle-btn ${btnClass}" data-index="${i}">${btnLabel}</button>`;
      html += `</div></div>`;
    });

    html += `</div></div>`;
    return html;
  }

  _escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  _truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.slice(0, len) + '...' : str;
  }

  _setupSnippetEvents(nodeEnter) {
    nodeEnter
      .filter((d) => this._isSnippetNode(d))
      .each((d, i, nodes) => {
        const fo = d3.select(nodes[i]).select('foreignObject');
        const container = fo.node();
        if (!container) return;

        container.addEventListener('click', (event) => {
          const btn = event.target.closest('.mindmap-snippet-toggle-btn');
          const batchBtn = event.target.closest('.mindmap-snippet-batch-btn');

          if (btn) {
            event.stopPropagation();
            const idx = parseInt(btn.dataset.index, 10);
            this._toggleSnippetRead(d, idx, container);
          } else if (batchBtn) {
            event.stopPropagation();
            const action = batchBtn.dataset.action;
            this._batchToggleRead(d, action === 'read-all', container);
          }
        });
      });
  }

  async _toggleSnippetRead(d, snippetIndex, container) {
    const snippets = d.data._snippets;
    if (!snippets || !snippets[snippetIndex]) return;

    const snippet = snippets[snippetIndex];
    const newRead = !snippet.read;

    try {
      await fetch('/read/snippets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          readed: newRead,
          selections: [{
            post_id: snippet.post_id,
            sentence_indices: snippet.indices,
          }],
        }),
      });

      snippet.read = newRead;
      this._updateSnippetDOM(d, container);
    } catch (err) {
      console.error('Failed to toggle snippet read:', err);
    }
  }

  async _batchToggleRead(d, markRead, container) {
    const snippets = d.data._snippets;
    if (!snippets || snippets.length === 0) return;

    const selections = snippets.map((s) => ({
      post_id: s.post_id,
      sentence_indices: s.indices,
    }));

    try {
      await fetch('/read/snippets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ readed: markRead, selections }),
      });

      snippets.forEach((s) => { s.read = markRead; });
      this._updateSnippetDOM(d, container);
    } catch (err) {
      console.error('Failed to batch toggle read:', err);
    }
  }

  _updateSnippetDOM(d, container) {
    const snippets = d.data._snippets || [];
    const items = container.querySelectorAll('.mindmap-snippet-item');
    items.forEach((item, i) => {
      if (!snippets[i]) return;
      const s = snippets[i];
      if (s.read) {
        item.classList.add('read');
      } else {
        item.classList.remove('read');
      }
      const btn = item.querySelector('.mindmap-snippet-toggle-btn');
      if (btn) {
        btn.textContent = s.read ? 'Unread' : 'Read';
        btn.className = `mindmap-snippet-toggle-btn ${s.read ? 'snippet-tag-read' : 'snippet-tag-unread'}`;
      }
    });
  }

  _update(source) {
    const treeLayout = d3.tree().nodeSize([this.nodeHeight + this.nodeSpacingY, 260]);
    treeLayout(this.root);

    const nodes = this.root.descendants();
    const links = this.root.links();

    // Filter out the synthetic root from display
    const visibleNodes = nodes.filter((d) => d.depth > 0);
    const visibleLinks = links.filter((d) => d.source.depth > 0);

    // Shift positions so root's children start from x=0
    visibleNodes.forEach((d) => {
      d.y = (d.depth - 1) * 260;
    });

    // --- NODES ---
    const node = this.gNodes
      .selectAll('g.mindmap-node')
      .data(visibleNodes, (d) => d.id);

    // Enter
    const nodeEnter = node
      .enter()
      .append('g')
      .attr('class', (d) => 'mindmap-node' + (this._isSnippetNode(d) ? ' mindmap-snippet-group' : ''))
      .attr('transform', () => `translate(${source.y0 || 0},${source.x0 || 0})`)
      .attr('opacity', 0);

    // --- Regular nodes (non-snippet) ---
    const regularEnter = nodeEnter.filter((d) => !this._isSnippetNode(d));

    // Rounded rect background
    regularEnter
      .append('rect')
      .attr('class', 'mindmap-node-rect')
      .attr('x', 0)
      .attr('y', -this.nodeHeight / 2)
      .attr('width', (d) => this._nodeWidth(d))
      .attr('height', this.nodeHeight)
      .attr('rx', 8)
      .attr('ry', 8)
      .attr('fill', (d) => this._depthColor(d.depth))
      .attr('stroke', '#999')
      .attr('stroke-width', 1)
      .attr('cursor', 'pointer')
      .on('click', (event, d) => {
        event.stopPropagation();
        this._navigateToTopic(d);
      });

    // Label text
    regularEnter
      .append('text')
      .attr('class', 'mindmap-node-text')
      .attr('x', 10)
      .attr('dy', '0.35em')
      .attr('font-size', '12px')
      .attr('cursor', 'pointer')
      .text((d) => {
        const name = d.data.name || '';
        return name.length > 25 ? name.slice(0, 25) + '...' : name;
      })
      .on('click', (event, d) => {
        event.stopPropagation();
        this._navigateToTopic(d);
      });

    // Title tooltip
    regularEnter.append('title').text((d) => {
      const path = d.data._topicPath || d.data.name || '';
      const count = d.data.value || 0;
      return `${path} (${count} posts)`;
    });

    // Expand/collapse arrow (branch nodes with children OR leaf nodes with posts)
    regularEnter
      .filter((d) => this._hasArrow(d))
      .append('text')
      .attr('class', 'mindmap-node-arrow')
      .attr('x', (d) => this._nodeWidth(d) - 20)
      .attr('dy', '0.35em')
      .attr('font-size', '14px')
      .attr('text-anchor', 'middle')
      .attr('cursor', 'pointer')
      .attr('fill', '#555')
      .text((d) => {
        if (d.data._loading) return '...';
        return (d.children) ? '<' : '>';
      })
      .on('click', (event, d) => {
        event.stopPropagation();
        if (this._isLeafTopic(d)) {
          this._loadSnippets(d);
        } else {
          this._toggleChildren(d);
          this._update(d);
        }
      });

    // Count badge
    regularEnter
      .filter((d) => d.data.value)
      .append('text')
      .attr('class', 'mindmap-node-count')
      .attr('x', (d) => this._nodeWidth(d) + 5)
      .attr('dy', '0.35em')
      .attr('font-size', '10px')
      .attr('fill', '#888')
      .text((d) => `(${d.data.value})`);

    // --- Snippet nodes ---
    const snippetEnter = nodeEnter.filter((d) => this._isSnippetNode(d));

    snippetEnter
      .append('rect')
      .attr('class', 'mindmap-snippet-panel-bg')
      .attr('x', 0)
      .attr('y', (d) => -this._nodeHeightFor(d) / 2)
      .attr('width', this.snippetPanelWidth)
      .attr('height', (d) => this._nodeHeightFor(d))
      .attr('rx', 8)
      .attr('ry', 8)
      .attr('fill', '#fff')
      .attr('stroke', '#999')
      .attr('stroke-width', 1);

    snippetEnter
      .append('foreignObject')
      .attr('x', 4)
      .attr('y', (d) => -this._nodeHeightFor(d) / 2 + 4)
      .attr('width', this.snippetPanelWidth - 8)
      .attr('height', (d) => this._nodeHeightFor(d) - 8)
      .append('xhtml:div')
      .html((d) => this._buildSnippetHTML(d));

    this._setupSnippetEvents(snippetEnter);

    // Update + Enter (merge)
    const nodeUpdate = nodeEnter.merge(node);

    nodeUpdate
      .transition()
      .duration(this.duration)
      .attr('transform', (d) => `translate(${d.y},${d.x})`)
      .attr('opacity', 1);

    // Update arrow direction on merge
    nodeUpdate.select('.mindmap-node-arrow').text((d) => {
      if (d.data._loading) return '...';
      return (d.children) ? '<' : '>';
    });

    // Update rect fill on merge
    nodeUpdate.select('.mindmap-node-rect').attr('fill', (d) => this._depthColor(d.depth));

    // Exit
    node
      .exit()
      .transition()
      .duration(this.duration)
      .attr('transform', () => `translate(${source.y || 0},${source.x || 0})`)
      .attr('opacity', 0)
      .remove();

    // --- LINKS ---
    const linkGenerator = d3
      .linkHorizontal()
      .x((d) => d[0])
      .y((d) => d[1]);

    const link = this.gLinks
      .selectAll('path.mindmap-link')
      .data(visibleLinks, (d) => d.target.id);

    // Enter
    const linkEnter = link
      .enter()
      .append('path')
      .attr('class', 'mindmap-link')
      .attr('fill', 'none')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.5)
      .attr('stroke-width', 1.5)
      .attr('d', () => {
        const o = [source.y0 || 0, source.x0 || 0];
        return linkGenerator({ source: o, target: o });
      });

    // Update + Enter
    linkEnter
      .merge(link)
      .transition()
      .duration(this.duration)
      .attr('d', (d) => {
        const sourceX = d.source.y + this._nodeWidth(d.source);
        const sourceY = d.source.x;
        const targetX = d.target.y;
        const targetY = d.target.x;
        return linkGenerator({
          source: [sourceX, sourceY],
          target: [targetX, targetY],
        });
      });

    // Exit
    link
      .exit()
      .transition()
      .duration(this.duration)
      .attr('d', () => {
        const o = [source.y || 0, source.x || 0];
        return linkGenerator({ source: o, target: o });
      })
      .remove();

    // Store old positions for transitions
    visibleNodes.forEach((d) => {
      d.x0 = d.x;
      d.y0 = d.y;
    });
  }

  _navigateToTopic(d) {
    const topicPath = d.data._topicPath;
    const topicPosts = d.data._topicPosts;
    if (topicPath && topicPosts && topicPosts.length > 0) {
      const postIds = topicPosts.join('_');
      const url = `/post-grouped/${postIds}?topic=${encodeURIComponent(topicPath)}`;
      window.location.href = url;
    }
  }

  _fitToView() {
    const svgEl = this.svg.node();
    const gEl = this.gMain.node();
    if (!svgEl || !gEl) return;

    const bounds = gEl.getBBox();
    if (bounds.width === 0 || bounds.height === 0) return;

    const svgWidth = svgEl.clientWidth || svgEl.getBoundingClientRect().width;
    const svgHeight = svgEl.clientHeight || svgEl.getBoundingClientRect().height;
    const padding = 40;

    const scale = Math.min(
      (svgWidth - padding * 2) / bounds.width,
      (svgHeight - padding * 2) / bounds.height,
      1.5
    );

    const tx = padding - bounds.x * scale;
    const ty = svgHeight / 2 - (bounds.y + bounds.height / 2) * scale;

    this.svg
      .transition()
      .duration(500)
      .call(this.zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  }

  _addResetButton(container) {
    const btn = document.createElement('button');
    btn.className = 'mindmap-reset-btn';
    btn.textContent = 'Reset View';
    btn.type = 'button';
    btn.addEventListener('click', () => this._fitToView());
    container.appendChild(btn);
  }
}
