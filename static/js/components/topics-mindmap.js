'use strict';

import * as d3 from 'd3';

/**
 * Topics Mindmap - Interactive collapsible horizontal tree
 * Uses D3 tree layout with zoom/pan and click-to-collapse/expand.
 * Leaf nodes expand to "Sentences" and "Sources" pseudo-nodes.
 */
export default class TopicsMindmap {
  constructor() {
    this.margin = { top: 20, right: 200, bottom: 20, left: 120 };
    this.nodeHeight = 32;
    this.nodeSpacingY = 20;
    this.nodeMinWidth = 80;
    this.nodeMaxWidth = 420;
    this.nodeCharWidth = 7.5;
    this.nodeHorizontalPadding = 40;
    this.nodeLabelPadding = 10;
    this.nodeArrowWidth = 20;
    this.nodeSearchBtnWidth = 20;
    this.nodeGapX = 80;
    this.snippetPanelWidth = 420;
    this.snippetItemHeight = 80;
    this.snippetMaxHeight = 500;
    this.snippetOverlay = null;
    this.overlaySnippetNode = null;
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

  _isSentencesPseudo(d) {
    return d.data._isSentencesPseudo === true;
  }

  _isSourcesPseudo(d) {
    return d.data._isSourcesPseudo === true;
  }

  _isSourceNode(d) {
    return d.data._isSourceNode === true;
  }

  _isTagSearchResult(d) {
    return d.data._isTagSearchResult === true;
  }

  _isPseudoOrSource(d) {
    return this._isSentencesPseudo(d) || this._isSourcesPseudo(d) || this._isSourceNode(d);
  }

  _hasSearchButton(d) {
    if (this._isSnippetNode(d) || this._isPseudoOrSource(d) || this._isTagSearchResult(d)) return false;
    return !!d.data._topicPath;
  }

  _nodeWidth(d) {
    if (this._isSnippetNode(d)) {
      return this.snippetPanelWidth;
    }
    const name = d.data.name || '';
    const searchExtra = this._hasSearchButton(d) ? this.nodeSearchBtnWidth : 0;
    const estimatedWidth = name.length * this.nodeCharWidth + this.nodeHorizontalPadding + searchExtra;
    return Math.min(Math.max(estimatedWidth, this.nodeMinWidth), this.nodeMaxWidth);
  }

  _displayNodeLabel(d) {
    if (this._isSnippetNode(d)) return '';

    const name = d.data.name || '';
    const width = this._nodeWidth(d);
    const arrowSpace = this._hasArrow(d) ? this.nodeArrowWidth : 0;
    const searchSpace = this._hasSearchButton(d) ? this.nodeSearchBtnWidth : 0;
    const usableWidth = width - this.nodeLabelPadding - arrowSpace - searchSpace - 4;
    const maxChars = Math.max(Math.floor(usableWidth / this.nodeCharWidth), 3);

    if (name.length <= maxChars) return name;
    if (maxChars <= 3) return '...';
    return name.slice(0, maxChars - 3) + '...';
  }

  _nodeHeightFor(d) {
    if (this._isSnippetNode(d)) {
      const snippets = d.data._snippets || [];
      const multiSentenceExtra = snippets.length > 1 ? 20 : 8;
      const contentH = 36 + snippets.length * this.snippetItemHeight + multiSentenceExtra;
      return Math.min(contentH, this.snippetMaxHeight);
    }
    return this.nodeHeight;
  }

  _depthColor(depth) {
    return this.nodeColors[(depth - 1) % this.nodeColors.length] || this.baseColor;
  }

  _hasArrow(d) {
    if (this._isSnippetNode(d)) return false;
    if (this._isTagSearchResult(d)) return false;
    const hasBranchChildren = d.data.children && d.data.children.length > 0;
    const isLeaf = this._isLeafTopic(d);
    return hasBranchChildren || isLeaf || this._isPseudoOrSource(d);
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

      const snippets = data.snippets || [];
      d.data._cachedSnippets = snippets;

      // Count unique feeds
      const feedSet = new Set(snippets.map((s) => s.feed_id || ''));
      const feedCount = feedSet.size;

      // Create two pseudo-children: Sentences and Sources
      const sentencesData = {
        name: `Sentences (${snippets.length})`,
        _isSentencesPseudo: true,
        _cachedSnippets: snippets,
      };

      const sourcesData = {
        name: `Sources (${feedCount})`,
        _isSourcesPseudo: true,
        _cachedSnippets: snippets,
      };

      const sentencesNode = d3.hierarchy(sentencesData);
      sentencesNode.depth = d.depth + 1;
      sentencesNode.parent = d;
      sentencesNode.id = this.i++;

      const sourcesNode = d3.hierarchy(sourcesData);
      sourcesNode.depth = d.depth + 1;
      sourcesNode.parent = d;
      sourcesNode.id = this.i++;

      d.children = [sentencesNode, sourcesNode];
      d._children = null;

      this._update(d);
    } catch (err) {
      d.data._loading = false;
      console.error('Failed to load snippets:', err);
      this._update(d);
    }
  }

  _expandSentencesPseudo(d) {
    // Toggle if already expanded
    if (d.children || d._children) {
      this._toggleChildren(d);
      this._update(d);
      return;
    }

    const snippets = d.data._cachedSnippets || [];

    const snippetChild = {
      name: '__snippets__',
      _isSnippetNode: true,
      _snippets: snippets,
      _parentTopicPath: d.parent ? d.parent.data._topicPath : '',
    };

    const childNode = d3.hierarchy(snippetChild);
    childNode.depth = d.depth + 1;
    childNode.parent = d;
    childNode.id = this.i++;

    d.children = [childNode];
    d._children = null;

    this._update(d);
  }

  _expandSourcesPseudo(d) {
    // Toggle if already expanded
    if (d.children || d._children) {
      this._toggleChildren(d);
      this._update(d);
      return;
    }

    const snippets = d.data._cachedSnippets || [];

    // Group snippets by feed_id
    const feedMap = new Map();
    snippets.forEach((s) => {
      const fid = s.feed_id || 'unknown';
      if (!feedMap.has(fid)) {
        feedMap.set(fid, { title: s.feed_title || fid, snippets: [] });
      }
      feedMap.get(fid).snippets.push(s);
    });

    const children = [];
    for (const [feedId, info] of feedMap) {
      const sourceData = {
        name: `${info.title} (${info.snippets.length})`,
        _isSourceNode: true,
        _feedId: feedId,
        _sourceSnippets: info.snippets,
      };

      const childNode = d3.hierarchy(sourceData);
      childNode.depth = d.depth + 1;
      childNode.parent = d;
      childNode.id = this.i++;
      children.push(childNode);
    }

    d.children = children;
    d._children = null;

    this._update(d);
  }

  _expandSourceNode(d) {
    // Toggle if already expanded
    if (d.children || d._children) {
      this._toggleChildren(d);
      this._update(d);
      return;
    }

    const snippets = d.data._sourceSnippets || [];

    const snippetChild = {
      name: '__snippets__',
      _isSnippetNode: true,
      _snippets: snippets,
      _parentTopicPath: '',
    };

    const childNode = d3.hierarchy(snippetChild);
    childNode.depth = d.depth + 1;
    childNode.parent = d;
    childNode.id = this.i++;

    d.children = [childNode];
    d._children = null;

    this._update(d);
  }

  _buildSnippetHTML(d, options = {}) {
    const snippets = d.data._snippets || [];
    const panelH = options.panelHeight || this._nodeHeightFor(d);
    const scrollH = options.scrollHeight || panelH - 36;
    const containerWidth = options.containerWidth || `${this.snippetPanelWidth - 16}px`;
    const containerMaxHeight = options.containerMaxHeight || `${panelH}px`;
    const includeMaximize = options.includeMaximize !== false;
    const includeClose = options.includeClose === true;
    const textPreviewLimit = typeof options.textPreviewLimit === 'number' ? options.textPreviewLimit : 200;
    const sourceTitleLimit = typeof options.sourceTitleLimit === 'number' ? options.sourceTitleLimit : 30;

    let html = `<div class="mindmap-snippet-container" style="width:${containerWidth};max-height:${containerMaxHeight};">`;
    html += `<div class="mindmap-snippet-header">`;
    html += `<span class="mindmap-snippet-title">${snippets.length} sentence${snippets.length !== 1 ? 's' : ''}</span>`;
    html += `<div class="mindmap-snippet-header-btns">`;
    if (includeMaximize) {
      html += `<button class="mindmap-snippet-batch-btn mindmap-snippet-maximize-btn" data-action="maximize">Maximize</button>`;
    }
    html += `<button class="mindmap-snippet-batch-btn" data-action="read-all">Read All</button>`;
    html += `<button class="mindmap-snippet-batch-btn" data-action="unread-all">Unread All</button>`;
    if (includeClose) {
      html += `<button class="mindmap-snippet-batch-btn mindmap-snippet-close-btn" data-action="close-overlay">Close</button>`;
    }
    html += `</div></div>`;
    html += `<div class="mindmap-snippet-list" style="max-height:${scrollH}px;overflow-y:auto;">`;

    snippets.forEach((s, i) => {
      const readClass = s.read ? 'read' : '';
      const btnLabel = s.read ? 'Unread' : 'Read';
      const btnClass = s.read ? 'snippet-tag-read' : 'snippet-tag-unread';
      const textPreview = textPreviewLimit > 0 && s.text.length > textPreviewLimit ? s.text.slice(0, textPreviewLimit) + '...' : s.text;
      html += `<div class="mindmap-snippet-item ${readClass}" data-index="${i}">`;
      html += `<div class="mindmap-snippet-text">${this._escapeHtml(textPreview)}</div>`;
      html += `<div class="mindmap-snippet-meta">`;
      html += `<span class="mindmap-snippet-source" title="${this._escapeHtml(s.post_title)}">${this._escapeHtml(this._truncate(s.post_title, sourceTitleLimit))}</span>`;
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
            if (action === 'maximize') {
              this._openSnippetOverlay(d);
            } else if (action === 'read-all' || action === 'unread-all') {
              this._batchToggleRead(d, action === 'read-all', container);
            }
          }
        });
      });
  }

  _ensureSnippetOverlay() {
    if (this.snippetOverlay) return;

    const overlay = document.createElement('div');
    overlay.className = 'mindmap-snippet-overlay';
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) {
        this._closeSnippetOverlay();
      }
    });

    overlay.addEventListener('click', (event) => {
      const btn = event.target.closest('.mindmap-snippet-toggle-btn');
      const batchBtn = event.target.closest('.mindmap-snippet-batch-btn');
      if (!this.overlaySnippetNode) return;

      if (btn) {
        event.stopPropagation();
        const idx = parseInt(btn.dataset.index, 10);
        this._toggleSnippetRead(this.overlaySnippetNode, idx, overlay);
      } else if (batchBtn) {
        event.stopPropagation();
        const action = batchBtn.dataset.action;
        if (action === 'close-overlay') {
          this._closeSnippetOverlay();
        } else if (action === 'read-all' || action === 'unread-all') {
          this._batchToggleRead(this.overlaySnippetNode, action === 'read-all', overlay);
        }
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && this.snippetOverlay && this.snippetOverlay.classList.contains('open')) {
        this._closeSnippetOverlay();
      }
    });

    document.body.appendChild(overlay);
    this.snippetOverlay = overlay;
  }

  _openSnippetOverlay(d) {
    if (!this._isSnippetNode(d)) return;

    this._ensureSnippetOverlay();
    this.overlaySnippetNode = d;

    const html = this._buildSnippetHTML(d, {
      panelHeight: '100%',
      scrollHeight: 'calc(100vh - 170px)',
      containerWidth: 'min(1200px, calc(100vw - 80px))',
      containerMaxHeight: 'calc(100vh - 80px)',
      includeMaximize: false,
      includeClose: true,
      textPreviewLimit: 0,
      sourceTitleLimit: 120,
    });

    this.snippetOverlay.innerHTML = `<div class="mindmap-snippet-overlay-panel">${html}</div>`;
    this.snippetOverlay.classList.add('open');
    document.body.classList.add('mindmap-snippet-overlay-open');
  }

  _closeSnippetOverlay() {
    if (!this.snippetOverlay) return;
    this.snippetOverlay.classList.remove('open');
    this.snippetOverlay.innerHTML = '';
    this.overlaySnippetNode = null;
    document.body.classList.remove('mindmap-snippet-overlay-open');
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
      if (this.overlaySnippetNode === d && this.snippetOverlay && this.snippetOverlay.classList.contains('open') && container !== this.snippetOverlay) {
        this._updateSnippetDOM(d, this.snippetOverlay);
      }
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
      if (this.overlaySnippetNode === d && this.snippetOverlay && this.snippetOverlay.classList.contains('open') && container !== this.snippetOverlay) {
        this._updateSnippetDOM(d, this.snippetOverlay);
      }
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

    // Position nodes horizontally using parent width + fixed gap,
    // so wide nodes do not overlap their children.
    if (this.root.children) {
      this.root.children.forEach((child) => {
        this._setHorizontalPosition(child, 0);
      });
    }

    // --- NODES ---
    const node = this.gNodes
      .selectAll('g.mindmap-node')
      .data(visibleNodes, (d) => d.id);

    // Enter
    const nodeEnter = node
      .enter()
      .append('g')
      .attr('class', (d) => {
        let cls = 'mindmap-node';
        if (this._isSnippetNode(d)) cls += ' mindmap-snippet-group';
        if (this._isPseudoOrSource(d)) cls += ' mindmap-pseudo-node';
        return cls;
      })
      .attr('transform', () => `translate(${source.y0 || 0},${source.x0 || 0})`)
      .attr('opacity', 0);

    // --- Regular nodes (non-snippet) ---
    const regularEnter = nodeEnter.filter((d) => !this._isSnippetNode(d));

    // Rounded rect background
    regularEnter
      .append('rect')
      .attr('class', (d) => 'mindmap-node-rect' + (this._isPseudoOrSource(d) ? ' mindmap-pseudo-rect' : '') + (this._isTagSearchResult(d) ? ' mindmap-tag-search-result-rect' : ''))
      .attr('x', 0)
      .attr('y', -this.nodeHeight / 2)
      .attr('width', (d) => this._nodeWidth(d))
      .attr('height', this.nodeHeight)
      .attr('rx', 8)
      .attr('ry', 8)
      .attr('fill', (d) => this._isTagSearchResult(d) ? '#fde8c0' : this._depthColor(d.depth))
      .attr('stroke', (d) => this._isTagSearchResult(d) ? '#c8963c' : '#999')
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
      .attr('x', this.nodeLabelPadding)
      .attr('dy', '0.35em')
      .attr('font-size', '12px')
      .attr('cursor', 'pointer')
      .text((d) => this._displayNodeLabel(d))
      .on('click', (event, d) => {
        event.stopPropagation();
        this._navigateToTopic(d);
      });

    // Title tooltip
    regularEnter.append('title').text((d) => {
      if (this._isPseudoOrSource(d)) return d.data.name || '';
      const path = d.data._topicPath || d.data.name || '';
      const count = d.data.value || 0;
      return `${path} (${count} posts)`;
    });

    // Expand/collapse arrow
    regularEnter
      .filter((d) => this._hasArrow(d))
      .append('text')
      .attr('class', 'mindmap-node-arrow')
      .attr('x', (d) => this._nodeWidth(d) - this.nodeArrowWidth)
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
        if (this._isSentencesPseudo(d)) {
          this._expandSentencesPseudo(d);
        } else if (this._isSourcesPseudo(d)) {
          this._expandSourcesPseudo(d);
        } else if (this._isSourceNode(d)) {
          this._expandSourceNode(d);
        } else if (this._isLeafTopic(d)) {
          this._loadSnippets(d);
        } else {
          this._toggleChildren(d);
          this._update(d);
        }
      });

    // Search button (⊕) for topic nodes – opens a tag search for the node's word
    regularEnter
      .filter((d) => this._hasSearchButton(d))
      .append('text')
      .attr('class', 'mindmap-node-search-btn')
      .attr('x', (d) => this._nodeWidth(d) - this.nodeArrowWidth - this.nodeSearchBtnWidth)
      .attr('dy', '0.35em')
      .attr('font-size', '13px')
      .attr('text-anchor', 'middle')
      .attr('cursor', 'pointer')
      .attr('fill', '#5a7fa0')
      .text((d) => {
        if (d.data._tagSearchLoading) return '…';
        if (d.data._tagSearchDone) return '✓';
        return '⊕';
      })
      .on('click', (event, d) => {
        event.stopPropagation();
        this._searchTagsForNode(d);
      });

    // Count badge
    regularEnter
      .filter((d) => d.data.value && !this._isPseudoOrSource(d))
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

    // Keep width, colors, and labels in sync on updates
    nodeUpdate
      .select('.mindmap-node-rect')
      .attr('width', (d) => this._nodeWidth(d))
      .attr('fill', (d) => this._isTagSearchResult(d) ? '#fde8c0' : this._depthColor(d.depth))
      .attr('stroke', (d) => this._isTagSearchResult(d) ? '#c8963c' : '#999');

    nodeUpdate
      .select('.mindmap-node-text')
      .attr('x', this.nodeLabelPadding)
      .text((d) => this._displayNodeLabel(d));

    nodeUpdate
      .select('.mindmap-node-arrow')
      .attr('x', (d) => this._nodeWidth(d) - this.nodeArrowWidth);

    nodeUpdate
      .select('.mindmap-node-search-btn')
      .attr('x', (d) => this._nodeWidth(d) - this.nodeArrowWidth - this.nodeSearchBtnWidth)
      .text((d) => {
        if (d.data._tagSearchLoading) return '…';
        if (d.data._tagSearchDone) return '✓';
        return '⊕';
      });

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

  _setHorizontalPosition(d, y) {
    d.y = y;

    const children = d.children || d._children;
    if (!children || children.length === 0) return;

    const childY = y + this._nodeWidth(d) + this.nodeGapX;
    children.forEach((child) => {
      this._setHorizontalPosition(child, childY);
    });
  }

  _navigateToTopic(d) {
    // Tag search result nodes link to the tag page
    if (this._isTagSearchResult(d)) {
      if (d.data._tagUrl) window.location.href = d.data._tagUrl;
      return;
    }

    // No-op for pseudo-nodes and source nodes
    if (this._isPseudoOrSource(d)) return;

    const topicPath = d.data._topicPath;
    const topicPosts = d.data._topicPosts;
    if (topicPath && topicPosts && topicPosts.length > 0) {
      const postIds = topicPosts.join('_');
      const url = `/post-grouped/${postIds}?topic=${encodeURIComponent(topicPath)}`;
      window.location.href = url;
    }
  }

  async _searchTagsForNode(d) {
    if (d.data._tagSearchLoading || d.data._tagSearchDone) return;

    const word = (d.data.name || '').trim();
    if (!word) return;

    d.data._tagSearchLoading = true;
    this._update(d);

    try {
      const resp = await fetch(`/api/mindmap-tag-search?word=${encodeURIComponent(word)}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      d.data._tagSearchLoading = false;
      d.data._tagSearchDone = true;

      const tags = data.tags || [];

      if (tags.length > 0) {
        const tagNodes = tags.map((tag) => {
          const tagData = {
            name: tag.tag,
            value: tag.posts_count,
            _isTagSearchResult: true,
            _tagUrl: tag.url,
          };
          const node = d3.hierarchy(tagData);
          node.depth = d.depth + 1;
          node.parent = d;
          node.id = this.i++;
          return node;
        });

        // Merge with existing children; expand the node so results are visible
        const base = d.children || d._children || [];
        d.children = [...base, ...tagNodes];
        d._children = null;
      }

      this._update(d);
    } catch (err) {
      d.data._tagSearchLoading = false;
      console.error('Failed to search tags for node:', err);
      this._update(d);
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
