'use strict';

import * as d3 from 'd3';

/**
 * Topics Mindmap - Interactive collapsible horizontal tree
 * Uses D3 tree layout with zoom/pan and click-to-collapse/expand.
 */
export default class TopicsMindmap {
  constructor() {
    this.margin = { top: 20, right: 200, bottom: 20, left: 120 };
    this.nodeHeight = 32;
    this.nodeSpacingY = 8;
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

  _nodeWidth(d) {
    const name = d.data.name || '';
    const displayName = name.length > 25 ? name.slice(0, 25) + '...' : name;
    return Math.max(displayName.length * 7.5 + 40, 80);
  }

  _depthColor(depth) {
    return this.nodeColors[(depth - 1) % this.nodeColors.length] || this.baseColor;
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
      .attr('class', 'mindmap-node')
      .attr('transform', () => `translate(${source.y0 || 0},${source.x0 || 0})`)
      .attr('opacity', 0);

    // Rounded rect background
    nodeEnter
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
    nodeEnter
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
    nodeEnter.append('title').text((d) => {
      const path = d.data._topicPath || d.data.name || '';
      const count = d.data.value || 0;
      return `${path} (${count} posts)`;
    });

    // Expand/collapse arrow button (only for nodes with children)
    nodeEnter
      .filter((d) => d.data.children && d.data.children.length > 0)
      .append('text')
      .attr('class', 'mindmap-node-arrow')
      .attr('x', (d) => this._nodeWidth(d) - 20)
      .attr('dy', '0.35em')
      .attr('font-size', '14px')
      .attr('text-anchor', 'middle')
      .attr('cursor', 'pointer')
      .attr('fill', '#555')
      .text((d) => (d.children ? '<' : '>'))
      .on('click', (event, d) => {
        event.stopPropagation();
        this._toggleChildren(d);
        this._update(d);
      });

    // Count badge
    nodeEnter
      .filter((d) => d.data.value)
      .append('text')
      .attr('class', 'mindmap-node-count')
      .attr('x', (d) => this._nodeWidth(d) + 5)
      .attr('dy', '0.35em')
      .attr('font-size', '10px')
      .attr('fill', '#888')
      .text((d) => `(${d.data.value})`);

    // Update + Enter (merge)
    const nodeUpdate = nodeEnter.merge(node);

    nodeUpdate
      .transition()
      .duration(this.duration)
      .attr('transform', (d) => `translate(${d.y},${d.x})`)
      .attr('opacity', 1);

    // Update arrow direction on merge
    nodeUpdate.select('.mindmap-node-arrow').text((d) => (d.children ? '<' : '>'));

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
