'use strict';

import * as d3 from 'd3';

const DEFAULT_ACTIONS = ['tags', 'sentences', 'sources', 'categories', 'subtopics'];
const ACTION_LABELS = {
  tags: 'Tags',
  sentences: 'Sentences',
  sources: 'Sources',
  categories: 'Categories',
  subtopics: 'Subtopics',
};

export default class TopicsMindmap {
  constructor() {
    this.margin = { top: 20, right: 200, bottom: 20, left: 120 };
    this.nodeHeight = 32;
    this.nodeSpacingY = 20;
    this.nodeMinWidth = 96;
    this.nodeMaxWidth = 440;
    this.nodeCharWidth = 7.5;
    this.nodeHorizontalPadding = 54;
    this.nodeLabelPadding = 10;
    this.nodeArrowWidth = 20;
    this.nodeMenuBtnWidth = 22;
    this.nodeGapX = 80;
    this.snippetPanelWidth = 420;
    this.snippetItemHeight = 80;
    this.snippetMaxHeight = 500;
    this.snippetOverlay = null;
    this.overlaySnippetNode = null;
    this.menuElement = null;
    this.menuNode = null;
    this.gMain = null;
    this.duration = 400;
    this.i = 0;
    this.root = null;
    this.svg = null;
    this.gLinks = null;
    this.gNodes = null;
    this.container = null;
    this.zoom = null;
    this.resizeHandler = null;
    this.documentClickHandler = null;
    this.escapeHandler = null;
    this.baseColor = '#d7d7af';
    this.nodeColors = ['#c8d0e8', '#d7d7af', '#c8e0c8', '#e0d0c8', '#d8c8e0', '#c8dce0'];
    this.options = {
      topicClickAction: 'navigate',
      countLabel: 'posts',
    };
  }

  render(selector, data, options = {}) {
    const container = document.querySelector(selector);
    if (!container) {
      return;
    }

    this.container = container;
    this.options = {
      topicClickAction: 'navigate',
      countLabel: 'posts',
      ...options,
    };
    this.container.innerHTML = '';
    this._closeContextMenu();
    this._closeSnippetOverlay();

    const { width, height } = this._getViewportSize();
    const hierarchyData = {
      name: '__root__',
      node_kind: 'root',
      available_actions: [],
      children: Array.isArray(data.children) ? data.children : [],
    };

    this.root = d3.hierarchy(hierarchyData);
    this.root.x0 = height / 2;
    this.root.y0 = 0;

    this.root.descendants().forEach((node) => {
      this._normalizeNodeData(node);
      node.id = this.i++;
    });

    if (Array.isArray(this.root.children)) {
      this.root.children.forEach((child) => {
        this._collapseAll(child);
      });
    }

    this.svg = d3
      .select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'topics-mindmap-svg');

    this.zoom = d3
      .zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        this.gMain.attr('transform', event.transform);
        this._closeContextMenu();
      });

    this.svg.call(this.zoom);
    this.gMain = this.svg.append('g').attr('class', 'mindmap-main');
    this.gLinks = this.gMain.append('g').attr('class', 'mindmap-links');
    this.gNodes = this.gMain.append('g').attr('class', 'mindmap-nodes');

    this._ensureContextMenu();
    this._ensureSnippetOverlay();
    this._update(this.root);
    setTimeout(() => this._fitToView(), 100);
    this._addResetButton(container);

    if (this.resizeHandler) {
      window.removeEventListener('resize', this.resizeHandler);
    }
    this.resizeHandler = () => this._handleResize();
    window.addEventListener('resize', this.resizeHandler);
  }

  _normalizeNodeData(node) {
    if (!node || !node.data) {
      return;
    }

    const data = node.data;
    data.node_kind = data.node_kind || data._nodeKind || (data._isSnippetNode ? 'snippet_panel' : 'topic');
    data.available_actions = Array.isArray(data.available_actions)
      ? data.available_actions
      : Array.isArray(data._availableActions)
        ? data._availableActions
        : this._defaultActionsForNodeKind(data.node_kind);

    if (!data.scope && data._mindmapScope) {
      data.scope = { ...data._mindmapScope };
    }

    if (!data.scope && data._topicPath) {
      data.scope = {
        node_kind: data.node_kind,
        topic_path: data._topicPath,
        post_ids: Array.isArray(data._topicPosts) ? [...data._topicPosts] : [],
      };
    }

    if (data.node_kind === 'snippet_panel') {
      data._isSnippetNode = true;
    }
  }

  _defaultActionsForNodeKind(nodeKind) {
    if (nodeKind === 'snippet_panel' || nodeKind === 'root') {
      return [];
    }
    return [...DEFAULT_ACTIONS];
  }

  _getViewportSize() {
    if (!this.container) {
      return {
        width: window.innerWidth,
        height: Math.max(window.innerHeight - 140, 480),
      };
    }

    const width = this.container.clientWidth || window.innerWidth;
    const rect = this.container.getBoundingClientRect();
    const availableHeight = window.innerHeight - rect.top - 24;
    return {
      width,
      height: Math.max(Math.floor(availableHeight), 480),
    };
  }

  _handleResize() {
    if (!this.svg) {
      return;
    }
    const { width, height } = this._getViewportSize();
    this.svg.attr('width', width).attr('height', height);
    this._closeContextMenu();
    this._fitToView();
  }

  _collapseAll(node) {
    if (node.children && node.data.node_kind !== 'snippet_panel') {
      node._children = node.children;
      node._children.forEach((child) => this._collapseAll(child));
      node.children = null;
    }
  }

  _toggleChildren(node) {
    if (node.children) {
      node._children = node.children;
      node.children = null;
    } else if (node._children) {
      node.children = node._children;
      node._children = null;
    }
  }

  _isSnippetNode(node) {
    return node?.data?.node_kind === 'snippet_panel' || node?.data?._isSnippetNode === true;
  }

  _hasMenuButton(node) {
    return !this._isSnippetNode(node) && (this._getAvailableActions(node).length > 0);
  }

  _getAvailableActions(node) {
    if (!node?.data) {
      return [];
    }
    return Array.isArray(node.data.available_actions)
      ? node.data.available_actions
      : this._defaultActionsForNodeKind(node.data.node_kind);
  }

  _nodeWidth(node) {
    if (this._isSnippetNode(node)) {
      return this.snippetPanelWidth;
    }

    const name = String(node.data.name || '');
    const arrowSpace = this._hasArrow(node) ? this.nodeArrowWidth : 0;
    const menuSpace = this._hasMenuButton(node) ? this.nodeMenuBtnWidth : 0;
    const estimatedWidth =
      name.length * this.nodeCharWidth +
      this.nodeHorizontalPadding +
      arrowSpace +
      menuSpace;
    return Math.min(Math.max(estimatedWidth, this.nodeMinWidth), this.nodeMaxWidth);
  }

  _displayNodeLabel(node) {
    if (this._isSnippetNode(node)) {
      return '';
    }

    const name = String(node.data.name || '');
    const width = this._nodeWidth(node);
    const arrowSpace = this._hasArrow(node) ? this.nodeArrowWidth : 0;
    const menuSpace = this._hasMenuButton(node) ? this.nodeMenuBtnWidth : 0;
    const usableWidth = width - this.nodeLabelPadding - arrowSpace - menuSpace - 6;
    const maxChars = Math.max(Math.floor(usableWidth / this.nodeCharWidth), 3);

    if (name.length <= maxChars) {
      return name;
    }
    if (maxChars <= 3) {
      return '...';
    }
    return `${name.slice(0, maxChars - 3)}...`;
  }

  _nodeHeightFor(node) {
    if (this._isSnippetNode(node)) {
      const snippets = Array.isArray(node.data.snippets) ? node.data.snippets : [];
      const multiSentenceExtra = snippets.length > 1 ? 20 : 8;
      const contentHeight = 36 + snippets.length * this.snippetItemHeight + multiSentenceExtra;
      return Math.min(contentHeight, this.snippetMaxHeight);
    }
    return this.nodeHeight;
  }

  _depthColor(depth) {
    return this.nodeColors[(Math.max(depth, 1) - 1) % this.nodeColors.length] || this.baseColor;
  }

  _hasArrow(node) {
    if (this._isSnippetNode(node)) {
      return false;
    }
    return Boolean(node.children || node._children);
  }

  _isNavigableNode(node) {
    const nodeKind = String(node?.data?.node_kind || '');
    if (!['topic', 'subtopic'].includes(nodeKind)) {
      return false;
    }
    const scope = this._getNodeScope(node);
    return Boolean(scope.topic_path && Array.isArray(scope.post_ids) && scope.post_ids.length > 0);
  }

  _getNodeScope(node) {
    const scope = node?.data?.scope || node?.data?._mindmapScope || {};
    const topicPath = scope.topic_path || node?.data?._topicPath || '';
    const postIds = Array.isArray(scope.post_ids)
      ? [...scope.post_ids]
      : Array.isArray(node?.data?._topicPosts)
        ? [...node.data._topicPosts]
        : [];

    const normalizedScope = {
      node_kind: scope.node_kind || node?.data?.node_kind || 'topic',
      topic_path: topicPath,
      post_ids: postIds,
    };

    for (const key of ['cluster_id', 'feed_id', 'category_id']) {
      if (scope[key]) {
        normalizedScope[key] = scope[key];
      }
    }

    if (Array.isArray(scope.tags) && scope.tags.length > 0) {
      normalizedScope.tags = [...scope.tags];
    } else if (scope.tag) {
      normalizedScope.tag = scope.tag;
    }

    return normalizedScope;
  }

  _escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  _truncate(str, len) {
    if (!str) {
      return '';
    }
    return str.length > len ? `${str.slice(0, len)}...` : str;
  }

  _buildSnippetHTML(node, options = {}) {
    const snippets = Array.isArray(node.data.snippets) ? node.data.snippets : [];
    const panelHeight = options.panelHeight || this._nodeHeightFor(node);
    const scrollHeight = options.scrollHeight || panelHeight - 36;
    const containerWidth = options.containerWidth || `${this.snippetPanelWidth - 16}px`;
    const containerMaxHeight = options.containerMaxHeight || `${panelHeight}px`;
    const includeMaximize = options.includeMaximize !== false;
    const includeClose = options.includeClose === true;
    const textPreviewLimit =
      typeof options.textPreviewLimit === 'number' ? options.textPreviewLimit : 200;
    const sourceTitleLimit =
      typeof options.sourceTitleLimit === 'number' ? options.sourceTitleLimit : 30;

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
    html += `<div class="mindmap-snippet-list" style="max-height:${scrollHeight}px;overflow-y:auto;">`;

    snippets.forEach((snippet, index) => {
      const readClass = snippet.read ? 'read' : '';
      const btnLabel = snippet.read ? 'Unread' : 'Read';
      const btnClass = snippet.read ? 'snippet-tag-read' : 'snippet-tag-unread';
      const rawText = snippet.html || snippet.text || '';
      const textPreview =
        textPreviewLimit > 0 && snippet.text && snippet.text.length > textPreviewLimit
          ? `${snippet.text.slice(0, textPreviewLimit)}...`
          : rawText;
      html += `<div class="mindmap-snippet-item ${readClass}" data-index="${index}">`;
      html += `<div class="mindmap-snippet-text">${textPreview}</div>`;
      html += `<div class="mindmap-snippet-meta">`;
      html += `<span class="mindmap-snippet-source" title="${this._escapeHtml(snippet.post_title || '')}">${this._escapeHtml(this._truncate(snippet.post_title || '', sourceTitleLimit))}</span>`;
      html += `<button class="mindmap-snippet-toggle-btn ${btnClass}" data-index="${index}">${btnLabel}</button>`;
      html += `</div></div>`;
    });

    html += `</div></div>`;
    return html;
  }

  _setupSnippetEvents(nodeEnter) {
    nodeEnter
      .filter((node) => this._isSnippetNode(node))
      .each((node, index, nodes) => {
        const foreignObject = d3.select(nodes[index]).select('foreignObject');
        const container = foreignObject.node();
        if (!container) {
          return;
        }

        container.addEventListener('click', (event) => {
          const btn = event.target.closest('.mindmap-snippet-toggle-btn');
          const batchBtn = event.target.closest('.mindmap-snippet-batch-btn');

          if (btn) {
            event.stopPropagation();
            const snippetIndex = parseInt(btn.dataset.index, 10);
            this._toggleSnippetRead(node, snippetIndex, container);
          } else if (batchBtn) {
            event.stopPropagation();
            const action = batchBtn.dataset.action;
            if (action === 'maximize') {
              this._openSnippetOverlay(node);
            } else if (action === 'read-all' || action === 'unread-all') {
              this._batchToggleRead(node, action === 'read-all', container);
            }
          }
        });
      });
  }

  _ensureSnippetOverlay() {
    if (this.snippetOverlay) {
      return;
    }

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
      if (!this.overlaySnippetNode) {
        return;
      }

      if (btn) {
        event.stopPropagation();
        const snippetIndex = parseInt(btn.dataset.index, 10);
        this._toggleSnippetRead(this.overlaySnippetNode, snippetIndex, overlay);
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

    document.body.appendChild(overlay);
    this.snippetOverlay = overlay;

    if (!this.escapeHandler) {
      this.escapeHandler = (event) => {
        if (event.key === 'Escape') {
          this._closeContextMenu();
          this._closeSnippetOverlay();
        }
      };
      document.addEventListener('keydown', this.escapeHandler);
    }
  }

  _openSnippetOverlay(node) {
    if (!this._isSnippetNode(node)) {
      return;
    }

    this._ensureSnippetOverlay();
    this.overlaySnippetNode = node;

    const html = this._buildSnippetHTML(node, {
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
    if (!this.snippetOverlay) {
      return;
    }
    this.snippetOverlay.classList.remove('open');
    this.snippetOverlay.innerHTML = '';
    this.overlaySnippetNode = null;
    document.body.classList.remove('mindmap-snippet-overlay-open');
  }

  async _toggleSnippetRead(node, snippetIndex, container) {
    const snippets = node.data.snippets;
    if (!Array.isArray(snippets) || !snippets[snippetIndex]) {
      return;
    }

    const snippet = snippets[snippetIndex];
    const newRead = !snippet.read;

    try {
      await fetch('/read/snippets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          readed: newRead,
          selections: [
            {
              post_id: snippet.post_id,
              sentence_indices: snippet.indices,
            },
          ],
        }),
      });

      snippet.read = newRead;
      this._updateSnippetDOM(node, container);
      if (
        this.overlaySnippetNode === node &&
        this.snippetOverlay &&
        this.snippetOverlay.classList.contains('open')
      ) {
        this._updateSnippetDOM(node, this.snippetOverlay);
      }
    } catch (error) {
      console.error('Failed to toggle snippet read state:', error);
    }
  }

  async _batchToggleRead(node, shouldRead, container) {
    const snippets = Array.isArray(node.data.snippets) ? node.data.snippets : [];
    if (snippets.length === 0) {
      return;
    }

    try {
      await fetch('/read/snippets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          readed: shouldRead,
          selections: snippets.map((snippet) => ({
            post_id: snippet.post_id,
            sentence_indices: snippet.indices,
          })),
        }),
      });

      snippets.forEach((snippet) => {
        snippet.read = shouldRead;
      });
      this._updateSnippetDOM(node, container);
      if (
        this.overlaySnippetNode === node &&
        this.snippetOverlay &&
        this.snippetOverlay.classList.contains('open')
      ) {
        this._updateSnippetDOM(node, this.snippetOverlay);
      }
    } catch (error) {
      console.error('Failed to batch toggle snippets:', error);
    }
  }

  _updateSnippetDOM(node, container) {
    const root = container.querySelector('.mindmap-snippet-container') || container;
    const items = root.querySelectorAll('.mindmap-snippet-item');
    const snippets = Array.isArray(node.data.snippets) ? node.data.snippets : [];

    items.forEach((item) => {
      const index = parseInt(item.dataset.index, 10);
      const snippet = snippets[index];
      if (!snippet) {
        return;
      }

      item.classList.toggle('read', Boolean(snippet.read));
      const btn = item.querySelector('.mindmap-snippet-toggle-btn');
      if (btn) {
        btn.textContent = snippet.read ? 'Unread' : 'Read';
        btn.className = `mindmap-snippet-toggle-btn ${snippet.read ? 'snippet-tag-read' : 'snippet-tag-unread'}`;
      }
    });
  }

  _ensureContextMenu() {
    if (this.menuElement) {
      return;
    }

    const menu = document.createElement('div');
    menu.className = 'mindmap-context-menu';
    menu.hidden = true;
    menu.addEventListener('click', (event) => {
      const button = event.target.closest('[data-action]');
      if (!button || !this.menuNode) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (button.disabled) {
        return;
      }
      const action = button.dataset.action;
      const selectedNode = this.menuNode;
      this._closeContextMenu();
      this._loadActionChildren(selectedNode, action);
    });

    this.container.appendChild(menu);
    this.menuElement = menu;

    if (!this.documentClickHandler) {
      this.documentClickHandler = (event) => {
        if (
          this.menuElement &&
          !this.menuElement.hidden &&
          !this.menuElement.contains(event.target)
        ) {
          this._closeContextMenu();
        }
      };
      document.addEventListener('click', this.documentClickHandler);
    }
  }

  _openContextMenu(node, event) {
    if (!this.menuElement || !this.container) {
      return;
    }

    event.stopPropagation();
    this.menuNode = node;
    const actions = this._getAvailableActions(node);
    const activeAction = node.data._activeAction || '';
    const loadingAction = node.data._loadingAction || '';

    this.menuElement.innerHTML = actions
      .map((action) => {
        const isLoading = loadingAction === action;
        const isActive = activeAction === action;
        return `<button type="button" class="mindmap-context-menu-item${isActive ? ' active' : ''}" data-action="${action}"${isLoading ? ' disabled' : ''}>${ACTION_LABELS[action] || action}${isLoading ? ' ...' : ''}</button>`;
      })
      .join('');

    const containerRect = this.container.getBoundingClientRect();
    const left = event.clientX - containerRect.left + 8;
    const top = event.clientY - containerRect.top + 8;
    this.menuElement.style.left = `${left}px`;
    this.menuElement.style.top = `${top}px`;
    this.menuElement.hidden = false;
  }

  _closeContextMenu() {
    if (!this.menuElement) {
      return;
    }
    this.menuElement.hidden = true;
    this.menuNode = null;
  }

  async _loadActionChildren(node, action) {
    if (!node || !action) {
      return;
    }

    if (node.data._loadingAction) {
      return;
    }

    const cacheKey = String(action);
    const hasCachedChildren =
      Boolean(node.data._actionChildren) &&
      Object.prototype.hasOwnProperty.call(node.data._actionChildren, cacheKey);
    const cachedChildren = hasCachedChildren ? node.data._actionChildren[cacheKey] : null;
    if (hasCachedChildren) {
      node.children = cachedChildren;
      node._children = null;
      node.data._activeAction = action;
      this._update(node);
      return;
    }

    node.data._loadingAction = action;
    this._update(node);

    try {
      const response = await fetch('/api/mindmap-node-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          scope: this._getNodeScope(node),
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      const items = Array.isArray(payload.items) ? payload.items : [];
      const hierarchyChildren = items.map((item) => this._materializeActionChild(node, item));

      node.data._actionChildren = node.data._actionChildren || {};
      node.data._actionChildren[cacheKey] = hierarchyChildren;
      node.data._activeAction = action;
      if (Array.isArray(payload.available_actions) && payload.available_actions.length > 0) {
        node.data.available_actions = payload.available_actions;
      }
      if (payload.scope && Array.isArray(payload.scope.post_ids)) {
        node.data.scope = payload.scope;
      }

      node.children = hierarchyChildren;
      node._children = null;
      this._update(node);
    } catch (error) {
      console.error('Failed to load mindmap node data:', error);
    } finally {
      node.data._loadingAction = '';
      this._update(node);
    }
  }

  _materializeActionChild(parent, item) {
    const nodeData = {
      name: item.name || '',
      value: item.value || 0,
      node_kind: item.node_kind || 'topic',
      available_actions: Array.isArray(item.available_actions)
        ? item.available_actions
        : this._defaultActionsForNodeKind(item.node_kind || 'topic'),
      scope: item.scope || {},
      snippets: Array.isArray(item.snippets) ? item.snippets : [],
    };

    const child = d3.hierarchy(nodeData);
    child.parent = parent;
    child.depth = parent.depth + 1;
    child.id = this.i++;
    this._normalizeNodeData(child);
    return child;
  }

  _activateNode(node) {
    const topicClickAction = this.options?.topicClickAction || 'navigate';

    if (this._hasArrow(node)) {
      this._toggleChildren(node);
      this._update(node);
      return;
    }

    if (topicClickAction === 'toggle') {
      const availableActions = this._getAvailableActions(node);
      if (availableActions.includes('subtopics')) {
        this._loadActionChildren(node, 'subtopics');
        return;
      }
      if (availableActions.includes('sentences')) {
        this._loadActionChildren(node, 'sentences');
        return;
      }
    }

    if (this._isNavigableNode(node)) {
      this._navigateToTopic(node);
    }
  }

  _navigateToTopic(node) {
    const scope = this._getNodeScope(node);
    if (!scope.topic_path || !Array.isArray(scope.post_ids) || scope.post_ids.length === 0) {
      return;
    }
    const postIds = scope.post_ids.join('_');
    window.location.href = `/post-grouped/${postIds}?topic=${encodeURIComponent(scope.topic_path)}`;
  }

  _setHorizontalPosition(node, y) {
    node.y = y;
    const children = node.children || node._children;
    if (!children || children.length === 0) {
      return;
    }
    const childY = y + this._nodeWidth(node) + this.nodeGapX;
    children.forEach((child) => {
      this._setHorizontalPosition(child, childY);
    });
  }

  _update(source) {
    this._closeContextMenu();

    const treeLayout = d3.tree().nodeSize([this.nodeHeight + this.nodeSpacingY, 120]);
    treeLayout(this.root);
    this._setHorizontalPosition(this.root, this.margin.left);

    const visibleNodes = this.root.descendants().filter((node) => node.depth > 0);
    const visibleLinks = this.root.links().filter((link) => link.source.depth >= 0);

    const node = this.gNodes.selectAll('g.mindmap-node').data(visibleNodes, (d) => d.id);

    const nodeEnter = node
      .enter()
      .append('g')
      .attr('class', (nodeData) => {
        let cls = 'mindmap-node';
        if (this._isSnippetNode(nodeData)) {
          cls += ' mindmap-snippet-group';
        } else {
          cls += ` mindmap-node-kind-${nodeData.data.node_kind}`;
        }
        return cls;
      })
      .attr('transform', () => `translate(${source.y0 || 0},${source.x0 || 0})`)
      .attr('opacity', 0);

    const regularEnter = nodeEnter.filter((nodeData) => !this._isSnippetNode(nodeData));

    regularEnter
      .append('rect')
      .attr('class', 'mindmap-node-rect')
      .attr('x', 0)
      .attr('y', -this.nodeHeight / 2)
      .attr('width', (nodeData) => this._nodeWidth(nodeData))
      .attr('height', this.nodeHeight)
      .attr('rx', 8)
      .attr('ry', 8)
      .attr('fill', (nodeData) => this._depthColor(nodeData.depth))
      .attr('stroke', '#999')
      .attr('stroke-width', 1)
      .attr('cursor', 'pointer')
      .on('click', (event, nodeData) => {
        event.stopPropagation();
        this._activateNode(nodeData);
      });

    regularEnter
      .append('text')
      .attr('class', 'mindmap-node-text')
      .attr('x', this.nodeLabelPadding)
      .attr('dy', '0.35em')
      .attr('font-size', '12px')
      .attr('cursor', 'pointer')
      .text((nodeData) => this._displayNodeLabel(nodeData))
      .on('click', (event, nodeData) => {
        event.stopPropagation();
        this._activateNode(nodeData);
      });

    regularEnter
      .append('title')
      .text((nodeData) => {
        const scope = this._getNodeScope(nodeData);
        const title = scope.topic_path || nodeData.data.name || '';
        const count = nodeData.data.value || 0;
        return `${title} (${count} ${this.options.countLabel})`;
      });

    regularEnter
      .filter((nodeData) => this._hasArrow(nodeData))
      .append('text')
      .attr('class', 'mindmap-node-arrow')
      .attr('x', (nodeData) => this._nodeWidth(nodeData) - this.nodeArrowWidth)
      .attr('dy', '0.35em')
      .attr('font-size', '14px')
      .attr('text-anchor', 'middle')
      .attr('cursor', 'pointer')
      .attr('fill', '#555')
      .text((nodeData) => (nodeData.children ? '<' : '>'))
      .on('click', (event, nodeData) => {
        event.stopPropagation();
        this._toggleChildren(nodeData);
        this._update(nodeData);
      });

    regularEnter
      .filter((nodeData) => this._hasMenuButton(nodeData))
      .append('text')
      .attr('class', 'mindmap-node-menu-btn')
      .attr('x', (nodeData) => this._nodeWidth(nodeData) - this.nodeArrowWidth - this.nodeMenuBtnWidth)
      .attr('dy', '0.35em')
      .attr('font-size', '14px')
      .attr('text-anchor', 'middle')
      .attr('cursor', 'pointer')
      .attr('fill', '#5a6775')
      .text((nodeData) => (nodeData.data._loadingAction ? '...' : '\u2261'))
      .on('click', (event, nodeData) => {
        this._openContextMenu(nodeData, event);
      });

    regularEnter
      .filter((nodeData) => nodeData.data.value)
      .append('text')
      .attr('class', 'mindmap-node-count')
      .attr('x', (nodeData) => this._nodeWidth(nodeData) + 5)
      .attr('dy', '0.35em')
      .attr('font-size', '10px')
      .attr('fill', '#888')
      .text((nodeData) => `(${nodeData.data.value})`);

    const snippetEnter = nodeEnter.filter((nodeData) => this._isSnippetNode(nodeData));

    snippetEnter
      .append('rect')
      .attr('class', 'mindmap-snippet-panel-bg')
      .attr('x', 0)
      .attr('y', (nodeData) => -this._nodeHeightFor(nodeData) / 2)
      .attr('width', this.snippetPanelWidth)
      .attr('height', (nodeData) => this._nodeHeightFor(nodeData))
      .attr('rx', 8)
      .attr('ry', 8)
      .attr('fill', '#fff')
      .attr('stroke', '#999')
      .attr('stroke-width', 1);

    snippetEnter
      .append('foreignObject')
      .attr('x', 4)
      .attr('y', (nodeData) => -this._nodeHeightFor(nodeData) / 2 + 4)
      .attr('width', this.snippetPanelWidth - 8)
      .attr('height', (nodeData) => this._nodeHeightFor(nodeData) - 8)
      .append('xhtml:div')
      .html((nodeData) => this._buildSnippetHTML(nodeData));

    this._setupSnippetEvents(snippetEnter);

    const nodeUpdate = nodeEnter.merge(node);

    nodeUpdate
      .transition()
      .duration(this.duration)
      .attr('transform', (nodeData) => `translate(${nodeData.y},${nodeData.x})`)
      .attr('opacity', 1);

    nodeUpdate
      .select('.mindmap-node-rect')
      .attr('width', (nodeData) => this._nodeWidth(nodeData))
      .attr('fill', (nodeData) => this._depthColor(nodeData.depth));

    nodeUpdate
      .select('.mindmap-node-text')
      .text((nodeData) => this._displayNodeLabel(nodeData));

    nodeUpdate
      .select('.mindmap-node-arrow')
      .attr('x', (nodeData) => this._nodeWidth(nodeData) - this.nodeArrowWidth)
      .text((nodeData) => (nodeData.children ? '<' : '>'));

    nodeUpdate
      .select('.mindmap-node-menu-btn')
      .attr('x', (nodeData) => this._nodeWidth(nodeData) - this.nodeArrowWidth - this.nodeMenuBtnWidth)
      .text((nodeData) => (nodeData.data._loadingAction ? '...' : '\u2261'));

    nodeUpdate
      .select('.mindmap-node-count')
      .attr('x', (nodeData) => this._nodeWidth(nodeData) + 5)
      .text((nodeData) => (nodeData.data.value ? `(${nodeData.data.value})` : ''));

    node
      .exit()
      .transition()
      .duration(this.duration)
      .attr('transform', () => `translate(${source.y || 0},${source.x || 0})`)
      .attr('opacity', 0)
      .remove();

    const linkGenerator = d3
      .linkHorizontal()
      .x((d) => d[0])
      .y((d) => d[1]);

    const link = this.gLinks.selectAll('path.mindmap-link').data(visibleLinks, (d) => d.target.id);

    const linkEnter = link
      .enter()
      .append('path')
      .attr('class', 'mindmap-link')
      .attr('fill', 'none')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.5)
      .attr('stroke-width', 1.5)
      .attr('d', () => {
        const origin = [source.y0 || 0, source.x0 || 0];
        return linkGenerator({ source: origin, target: origin });
      });

    linkEnter
      .merge(link)
      .transition()
      .duration(this.duration)
      .attr('d', (linkData) => {
        const sourceX = linkData.source.y + this._nodeWidth(linkData.source);
        const sourceY = linkData.source.x;
        const targetX = linkData.target.y;
        const targetY = linkData.target.x;
        return linkGenerator({
          source: [sourceX, sourceY],
          target: [targetX, targetY],
        });
      });

    link
      .exit()
      .transition()
      .duration(this.duration)
      .attr('d', () => {
        const origin = [source.y || 0, source.x || 0];
        return linkGenerator({ source: origin, target: origin });
      })
      .remove();

    visibleNodes.forEach((nodeData) => {
      nodeData.x0 = nodeData.x;
      nodeData.y0 = nodeData.y;
    });
  }

  _fitToView() {
    const svgElement = this.svg?.node();
    const graphElement = this.gMain?.node();
    if (!svgElement || !graphElement) {
      return;
    }

    const bounds = graphElement.getBBox();
    if (bounds.width === 0 || bounds.height === 0) {
      return;
    }

    const svgWidth = svgElement.clientWidth || svgElement.getBoundingClientRect().width;
    const svgHeight = svgElement.clientHeight || svgElement.getBoundingClientRect().height;
    const padding = 40;

    const scale = Math.min(
      (svgWidth - padding * 2) / bounds.width,
      (svgHeight - padding * 2) / bounds.height,
      1.5
    );
    const translateX = padding - bounds.x * scale;
    const translateY = svgHeight / 2 - (bounds.y + bounds.height / 2) * scale;

    this.svg
      .transition()
      .duration(500)
      .call(this.zoom.transform, d3.zoomIdentity.translate(translateX, translateY).scale(scale));
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
