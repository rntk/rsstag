'use strict';

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 2.4;
const BATCH_SIZE = 250;
const ROW_HEIGHT = 60;
const TILE_HEIGHT = 720;
const MENU_SIZE = 360;
const MIN_FONT_SIZE = 16;
const MAX_FONT_SIZE = 40;
const SVG_NS = 'http://www.w3.org/2000/svg';

function sectorPoint(radius, angle) {
  const radians = (angle * Math.PI) / 180;
  return [180 + radius * Math.cos(radians), 180 + radius * Math.sin(radians)];
}

function sectorPath(start, end) {
  const [outerStartX, outerStartY] = sectorPoint(174, start);
  const [outerEndX, outerEndY] = sectorPoint(174, end);
  const [innerEndX, innerEndY] = sectorPoint(64, end);
  const [innerStartX, innerStartY] = sectorPoint(64, start);
  return `M ${outerStartX} ${outerStartY} A 174 174 0 0 1 ${outerEndX} ${outerEndY} L ${innerEndX} ${innerEndY} A 64 64 0 0 0 ${innerStartX} ${innerStartY} Z`;
}

function menuActions(tag) {
  const name = encodeURIComponent(tag.tag);
  return [
    { label: ['Info'], href: `/tag-info/${name}` },
    { label: ['Sentences'], href: `/sentences/with/tags/${name}` },
    { label: ['Sunburst'], href: `/sunburst/${name}` },
    { label: ['Chains'], href: `/chain/${name}` },
    { label: ['Context', 'tree'], href: `/tag-context-tree/${name}` },
    { label: ['Concordance'], href: `/tag-concordance/${name}` },
    { label: ['Explorer'], href: `/tag-explorer/${name}` },
    { label: ['Context', 'tags'], href: `/context-tags/${name}` },
    { label: ['Words'], words: true },
  ];
}

function addSector(svg, action, index, total, showWords) {
  const start = -110 + (360 * index) / total;
  const end = -110 + (360 * (index + 1)) / total;
  const middle = (start + end) / 2;
  const sector = document.createElementNS(SVG_NS, action.words ? 'g' : 'a');
  const label = action.label.join(' ');
  sector.setAttribute('aria-label', label);
  sector.setAttribute('tabindex', '0');
  if (action.words) {
    sector.setAttribute('role', 'button');
    sector.addEventListener('mouseenter', showWords);
    sector.addEventListener('focus', showWords);
    sector.addEventListener('click', showWords);
    sector.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        showWords();
      }
    });
  } else {
    sector.setAttribute('href', action.href);
  }
  const path = document.createElementNS(SVG_NS, 'path');
  path.setAttribute('d', sectorPath(start, end));
  sector.append(path);
  const [textX, textY] = sectorPoint(119, middle);
  const text = document.createElementNS(SVG_NS, 'text');
  text.setAttribute('x', textX);
  text.setAttribute('y', textY - (action.label.length - 1) * 8);
  action.label.forEach((line, lineIndex) => {
    const part = document.createElementNS(SVG_NS, 'tspan');
    part.setAttribute('x', textX);
    part.setAttribute('dy', lineIndex ? '16' : '0');
    part.textContent = line;
    text.append(part);
  });
  sector.append(text);
  svg.append(sector);
}

export class TagsCanvas {
  constructor(viewport, canvas) {
    this.viewport = viewport;
    this.canvas = canvas;
    this.context = canvas.getContext('2d');
    this.status = document.getElementById('tag-canvas-status');
    this.error = document.getElementById('tag-canvas-error');
    this.tags = [];
    this.rows = [];
    this.tiles = new Map();
    this.activeTile = null;
    this.worldWidth = 1100;
    this.laidOut = 0;
    this.metric = 'count';
    this.fontScale = { metric: null, count: 0, min: 0, max: 0 };
    this.zoom = 1;
    this.x = 20;
    this.y = 20;
    this.total = null;
    this.loading = false;
    this.exhausted = false;
    this.drag = null;
    this.gesture = false;
    this.pointers = new Map();
    this.frame = 0;
    this.topicFilter = new URLSearchParams(location.search).get('topics') === '1';
    this.menu = document.getElementById('tag-canvas-menu');
    this.menuRing = this.menu.querySelector('svg');
    this.menuCenter = this.menu.querySelector('.tag-canvas-menu__center');
    this.wordsPopup = this.menu.querySelector('.tag-canvas-menu__words');
    this.hoveredTag = null;
    this.dismissedTag = null;
    this.menuHideTimer = null;
  }

  start() {
    this.resize();
    new ResizeObserver(() => this.resize()).observe(this.viewport);
    if (document.fonts) {
      document.fonts.ready.then(() => {
        this.layout(true);
        this.scheduleDraw();
        this.maybeLoad();
      });
    }
    this.canvas.addEventListener('pointerdown', (event) => this.pointerDown(event));
    this.canvas.addEventListener('pointermove', (event) => this.pointerMove(event));
    this.canvas.addEventListener('pointerup', (event) => this.pointerUp(event));
    this.canvas.addEventListener('pointercancel', (event) => this.pointerUp(event));
    this.canvas.addEventListener('pointerleave', () => {
      this.canvas.classList.remove('is-over-tag');
      this.dismissedTag = null;
    });
    this.menu.addEventListener('pointerenter', () => clearTimeout(this.menuHideTimer));
    this.menu.addEventListener('pointerleave', () => {
      if (!this.menu.contains(document.activeElement)) {
        this.menuHideTimer = setTimeout(() => this.hideMenu(), 120);
      }
    });
    window.addEventListener('keydown', (event) => this.handleKeyDown(event));
    document.addEventListener('pointerdown', (event) => {
      if (!this.menu.contains(event.target)) this.hideMenu();
    });
    this.menu.addEventListener('focusout', (event) => {
      if (!this.menu.contains(event.relatedTarget)) this.hideMenu();
    });
    this.viewport.addEventListener(
      'wheel',
      (event) => {
        if (this.wordsPopup.contains(event.target)) return;
        event.preventDefault();
        const bounds = this.canvas.getBoundingClientRect();
        const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.viewHeight : 1;
        this.zoomAt(
          Math.exp(-event.deltaY * unit * 0.001),
          event.clientX - bounds.left,
          event.clientY - bounds.top
        );
      },
      { passive: false }
    );
    document.querySelectorAll('.tag-canvas-navigation [data-pan]').forEach((button) => {
      button.addEventListener('click', () => this.pan(button.dataset.pan));
    });
    document.querySelectorAll('input[name="tag-canvas-metric"]').forEach((input) => {
      input.addEventListener('change', () => {
        if (input.checked) {
          this.hideMenu();
          this.metric = input.value;
          this.layout(true);
          this.scheduleDraw();
          this.maybeLoad();
        }
      });
    });
    document.getElementById('tag-canvas-zoom-in').addEventListener('click', () => this.zoomAt(1.2));
    document
      .getElementById('tag-canvas-zoom-out')
      .addEventListener('click', () => this.zoomAt(1 / 1.2));
    document.getElementById('tag-canvas-reset').addEventListener('click', () => {
      this.hideMenu();
      this.zoom = 1;
      this.x = 20;
      this.y = 20;
      this.updateZoomControls();
      this.scheduleDraw();
      this.maybeLoad();
    });
    this.updateZoomControls();
    this.loadMore();
  }

  /** @param {KeyboardEvent} event @returns {void} */
  handleKeyDown(event) {
    if (event.key === 'Escape' && !this.menu.hidden) {
      event.preventDefault();
      const restoreFocus = this.menu.contains(document.activeElement);
      this.dismissedTag = this.hoveredTag;
      this.hideMenu();
      if (restoreFocus) this.canvas.focus({ preventScroll: true });
      return;
    }
    if (
      event.defaultPrevented ||
      event.target !== this.canvas ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      (event.target instanceof Element &&
        event.target.closest('input, textarea, select, [contenteditable="true"]'))
    )
      return;
    const direction = {
      ArrowLeft: 'left',
      ArrowRight: 'right',
      ArrowUp: 'up',
      ArrowDown: 'down',
      PageUp: 'page-up',
      PageDown: 'page-down',
    }[event.key];
    if (direction) {
      event.preventDefault();
      this.pan(direction);
    } else if (event.key === '+' || event.key === '=') {
      event.preventDefault();
      this.zoomAt(1.2);
    } else if (event.key === '-') {
      event.preventDefault();
      this.zoomAt(1 / 1.2);
    }
  }

  /** @returns {void} */
  updateZoomControls() {
    document.getElementById('tag-canvas-zoom-level').textContent =
      `${Math.round(this.zoom * 100)}%`;
    document.getElementById('tag-canvas-zoom-out').disabled = this.zoom <= MIN_ZOOM;
    document.getElementById('tag-canvas-zoom-in').disabled = this.zoom >= MAX_ZOOM;
  }

  resize() {
    const bounds = this.viewport.getBoundingClientRect();
    this.width = Math.max(1, Math.floor(bounds.width));
    this.viewHeight = Math.max(1, Math.floor(bounds.height));
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(this.width * ratio);
    this.canvas.height = Math.round(this.viewHeight * ratio);
    this.context.setTransform(ratio, 0, 0, ratio, 0, 0);
    this.worldWidth = Math.max(1100, Math.min(1800, this.width * 1.4));
    this.layout(true);
    this.scheduleDraw();
    this.maybeLoad();
    this.hideMenu();
  }

  /** @param {object} tag @returns {number} */
  score(tag) {
    const value = Number(tag[this.metric]);
    return Number.isFinite(value) ? Math.max(0, value) : 0;
  }

  /** @returns {boolean} Whether existing tags need to be resized. */
  updateFontScale() {
    const previous = this.fontScale;
    const metricChanged = previous.metric !== this.metric;
    let min = metricChanged || !previous.count ? Infinity : previous.min;
    let max = metricChanged || !previous.count ? -Infinity : previous.max;
    const offset = metricChanged ? 0 : previous.count;
    for (let index = offset; index < this.tags.length; index++) {
      const value = this.score(this.tags[index]);
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
    if (!this.tags.length) min = max = 0;
    this.fontScale = { metric: this.metric, count: this.tags.length, min, max };
    return metricChanged || min !== previous.min || max !== previous.max;
  }

  /** @param {object} tag @returns {number} */
  fontSize(tag) {
    const { min, max } = this.fontScale;
    // Log scaling keeps common tags prominent without letting outliers dominate.
    const fraction =
      max > min
        ? Math.max(
            0,
            Math.min(
              1,
              (Math.log1p(this.score(tag)) - Math.log1p(min)) / (Math.log1p(max) - Math.log1p(min))
            )
          )
        : 0.5;
    return MIN_FONT_SIZE + (MAX_FONT_SIZE - MIN_FONT_SIZE) * fraction;
  }

  /** @param {boolean} reset @returns {void} */
  layout(reset = false) {
    if (!this.context || !this.worldWidth) return;
    if (this.updateFontScale()) reset = true;
    if (reset) {
      this.rows = [];
      this.tiles.clear();
      this.activeTile = null;
      this.laidOut = 0;
    }
    for (const tag of this.tags.slice(this.laidOut)) {
      if (!this.activeTile) {
        this.activeTile = this.nextTile();
        if (!this.activeTile) break;
      }
      let tile = this.activeTile;
      const size = this.fontSize(tag);
      this.context.font = `600 ${size}px Inter, sans-serif`;
      const width = Math.min(
        this.worldWidth - 48,
        Math.ceil(this.context.measureText(tag.tag).width) + 24
      );
      if (tile.x + width > this.worldWidth - 48 && tile.x) {
        tile.row += 1;
        tile.x = 0;
      }
      if (tile.row >= TILE_HEIGHT / ROW_HEIGHT) {
        tile.complete = true;
        this.activeTile = null;
        tile = this.nextTile();
        if (!tile) break;
        this.activeTile = tile;
      }
      if (!tile.x) {
        tile.currentRow = {
          y: tile.vertical * TILE_HEIGHT + tile.row * ROW_HEIGHT + 24,
          height: ROW_HEIGHT - 4,
          items: [],
        };
        this.rows.push(tile.currentRow);
      }
      tile.currentRow.items.push({
        tag,
        x: tile.horizontal * this.worldWidth + tile.x + 24,
        width,
        size,
      });
      tile.x += width + 4;
      this.laidOut += 1;
    }
    this.rows.sort((a, b) => a.y - b.y);
  }

  /** @returns {?{key: string, horizontal: number, vertical: number, row: number, x: number, complete: boolean, currentRow?: {y: number, height: number, items: Array<{tag: object, x: number, width: number, size: number}>}}} */
  nextTile() {
    const next = this.visibleTiles().find(({ key }) => !this.tiles.has(key));
    if (!next) return null;
    const tile = { ...next, row: 0, x: 0, complete: false };
    this.tiles.set(next.key, tile);
    return tile;
  }

  /** @returns {Array<{key: string, horizontal: number, vertical: number}>} */
  visibleTiles() {
    const margin = 120;
    const left = (-this.x - margin) / this.zoom;
    const right = (this.width - this.x + margin) / this.zoom;
    const top = (-this.y - margin) / this.zoom;
    const bottom = (this.viewHeight - this.y + margin) / this.zoom;
    const centerX = (left + right) / 2 / this.worldWidth;
    const centerY = (top + bottom) / 2 / TILE_HEIGHT;
    const tiles = [];
    for (
      let vertical = Math.floor(top / TILE_HEIGHT);
      vertical <= Math.floor(bottom / TILE_HEIGHT);
      vertical++
    ) {
      for (
        let horizontal = Math.floor(left / this.worldWidth);
        horizontal <= Math.floor(right / this.worldWidth);
        horizontal++
      ) {
        tiles.push({ key: `${horizontal},${vertical}`, horizontal, vertical });
      }
    }
    return tiles.sort(
      (a, b) =>
        Math.hypot(a.horizontal + 0.5 - centerX, a.vertical + 0.5 - centerY) -
        Math.hypot(b.horizontal + 0.5 - centerX, b.vertical + 0.5 - centerY)
    );
  }

  firstRowAt(y) {
    let low = 0;
    let high = this.rows.length;
    while (low < high) {
      const mid = (low + high) >> 1;
      if (this.rows[mid].y + this.rows[mid].height < y) low = mid + 1;
      else high = mid;
    }
    return low;
  }

  scheduleDraw() {
    if (!this.frame)
      this.frame = requestAnimationFrame(() => {
        this.frame = 0;
        this.draw();
      });
  }

  draw() {
    const ctx = this.context;
    ctx.clearRect(0, 0, this.width, this.viewHeight);
    ctx.save();
    ctx.translate(this.x, this.y);
    ctx.scale(this.zoom, this.zoom);
    const top = -this.y / this.zoom - 50;
    const bottom = (this.viewHeight - this.y) / this.zoom + 50;
    const left = -this.x / this.zoom - 50;
    const right = (this.width - this.x) / this.zoom + 50;
    for (let i = this.firstRowAt(top); i < this.rows.length; i++) {
      const row = this.rows[i];
      if (row.y > bottom) break;
      for (const item of row.items) {
        if (item.x + item.width < left || item.x > right) continue;
        ctx.font = `600 ${item.size}px Inter, sans-serif`;
        ctx.fillStyle = '#234e73';
        ctx.fillText(
          item.tag.tag,
          item.x + 8,
          row.y + (row.height + item.size) / 2 - 3,
          item.width - 16
        );
      }
    }
    ctx.restore();
  }

  hit(clientX, clientY) {
    const bounds = this.canvas.getBoundingClientRect();
    const x = (clientX - bounds.left - this.x) / this.zoom;
    const y = (clientY - bounds.top - this.y) / this.zoom;
    for (let i = this.firstRowAt(y); i < this.rows.length; i++) {
      const row = this.rows[i];
      if (row.y > y) break;
      if (y > row.y + row.height) continue;
      const item = row.items.find((item) => x >= item.x && x <= item.x + item.width);
      if (item) return item.tag;
    }
    return null;
  }

  showMenu(tag, clientX, clientY) {
    clearTimeout(this.menuHideTimer);
    if (!tag) {
      this.hideMenu();
      return;
    }
    if (this.hoveredTag === tag) return;
    this.hoveredTag = tag;
    const size = Math.min(MENU_SIZE, this.width, this.viewHeight);
    const bounds = this.canvas.getBoundingClientRect();
    const left = Math.max(0, Math.min(this.width - size, clientX - bounds.left - size / 2));
    const top = Math.max(0, Math.min(this.viewHeight - size, clientY - bounds.top - size / 2));
    this.menu.style.width = `${size}px`;
    this.menu.style.height = `${size}px`;
    this.menu.style.left = `${left}px`;
    this.menu.style.top = `${top}px`;
    this.menu.classList.toggle('is-right-edge', this.width - left - size < 250);
    this.menu.classList.toggle('is-compact', this.width < 900);
    const name = document.createElement('span');
    name.textContent = tag.tag;
    const count = document.createElement('small');
    count.textContent = `${Number(tag.count || 0).toLocaleString()} matches`;
    this.menuCenter.replaceChildren(name, count);
    this.menuCenter.href = tag.url;
    this.menuCenter.title = `${tag.tag} · ${count.textContent} · temperature ${tag.temperature ?? 0} · open posts`;
    this.wordsPopup.hidden = true;
    this.menuRing.replaceChildren();
    const actions = menuActions(tag);
    actions.forEach((action, index) => {
      addSector(this.menuRing, action, index, actions.length, () => this.showWords(tag));
    });
    this.menu.hidden = false;
  }

  showWords(tag) {
    this.wordsPopup.replaceChildren();
    const words = Array.isArray(tag.words) ? tag.words : [];
    const title = document.createElement('strong');
    title.textContent = `Words (${words.length})`;
    this.wordsPopup.append(title);
    if (words.length) {
      const list = document.createElement('ul');
      words.forEach((word) => {
        const item = document.createElement('li');
        item.textContent = word;
        list.append(item);
      });
      this.wordsPopup.append(list);
    } else {
      const empty = document.createElement('p');
      empty.textContent = 'No words recorded for this tag.';
      this.wordsPopup.append(empty);
    }
    this.wordsPopup.hidden = false;
  }

  hideMenu() {
    clearTimeout(this.menuHideTimer);
    this.hoveredTag = null;
    this.menu.hidden = true;
    this.wordsPopup.hidden = true;
  }

  pointerDown(event) {
    if (event.button !== 0) return;
    this.hideMenu();
    this.canvas.focus({ preventScroll: true });
    this.canvas.setPointerCapture(event.pointerId);
    this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (this.pointers.size > 1) this.gesture = true;
    this.drag = { x: event.clientX, y: event.clientY, moved: false };
    this.canvas.classList.add('is-dragging');
  }

  pointerMove(event) {
    const previous = this.pointers.get(event.pointerId);
    if (!previous) {
      const tag = this.hit(event.clientX, event.clientY);
      this.canvas.classList.toggle('is-over-tag', Boolean(tag));
      if (tag !== this.dismissedTag) this.dismissedTag = null;
      if (event.pointerType !== 'touch' && !this.dismissedTag) {
        this.showMenu(tag, event.clientX, event.clientY);
      }
      return;
    }
    if (
      this.drag &&
      Math.abs(event.clientX - this.drag.x) + Math.abs(event.clientY - this.drag.y) > 5
    ) {
      this.drag.moved = true;
    }
    if (this.pointers.size === 1) {
      this.x += event.clientX - previous.x;
      this.y += event.clientY - previous.y;
    } else {
      const other = [...this.pointers.entries()].find(([id]) => id !== event.pointerId)?.[1];
      if (other) {
        const before = Math.hypot(previous.x - other.x, previous.y - other.y);
        const after = Math.hypot(event.clientX - other.x, event.clientY - other.y);
        if (before > 0)
          this.zoomAt(
            after / before,
            (event.clientX + other.x) / 2 - this.canvas.getBoundingClientRect().left,
            (event.clientY + other.y) / 2 - this.canvas.getBoundingClientRect().top
          );
      }
    }
    this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    this.scheduleDraw();
    this.maybeLoad();
  }

  pointerUp(event) {
    const clicked =
      event.type !== 'pointercancel' &&
      this.pointers.has(event.pointerId) &&
      this.pointers.size === 1 &&
      !this.gesture &&
      this.drag &&
      !this.drag.moved;
    this.pointers.delete(event.pointerId);
    this.canvas.classList.remove('is-dragging');
    if (clicked) {
      const tag = this.hit(event.clientX, event.clientY);
      if (tag) {
        if (event.pointerType === 'touch') this.showMenu(tag, event.clientX, event.clientY);
        else window.location.href = tag.url;
      }
    }
    this.drag = null;
    if (!this.pointers.size) this.gesture = false;
  }

  zoomAt(factor, x = this.width / 2, y = this.viewHeight / 2) {
    this.hideMenu();
    const next = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, this.zoom * factor));
    const scale = next / this.zoom;
    this.x = x - (x - this.x) * scale;
    this.y = y - (y - this.y) * scale;
    this.zoom = next;
    this.updateZoomControls();
    this.scheduleDraw();
    this.maybeLoad();
  }

  pan(direction) {
    this.hideMenu();
    const step = direction.startsWith('page-') ? this.viewHeight * 0.85 : 100;
    const movement = {
      left: [step, 0],
      right: [-step, 0],
      up: [0, step],
      down: [0, -step],
      'page-up': [0, step],
      'page-down': [0, -step],
    }[direction];
    if (!movement) return;
    this.x += movement[0];
    this.y += movement[1];
    this.scheduleDraw();
    this.maybeLoad();
  }

  maybeLoad() {
    this.layout();
    if (
      !this.loading &&
      !this.exhausted &&
      (this.total === null || this.tags.length < this.total) &&
      this.visibleTiles().some(({ key }) => !this.tiles.get(key)?.complete)
    )
      this.loadMore();
  }

  async loadMore() {
    if (this.loading || this.exhausted || (this.total !== null && this.tags.length >= this.total))
      return;
    this.loading = true;
    this.status.textContent = `Loading · ${this.tags.length.toLocaleString()} tags`;
    const params = new URLSearchParams({ offset: this.tags.length, limit: BATCH_SIZE });
    if (this.topicFilter) params.set('topics', '1');
    try {
      const response = await fetch(`/api/tags/canvas?${params}`, { credentials: 'same-origin' });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const data = await response.json();
      this.total = data.total;
      if (!data.tags.length) this.exhausted = true;
      this.tags.push(...data.tags);
      this.layout();
      this.scheduleDraw();
      this.error.hidden = true;
      this.status.textContent = `${this.tags.length.toLocaleString()} of ${this.total.toLocaleString()} tags`;
    } catch (error) {
      this.error.textContent = `Could not load tags. ${error.message} Select here to retry.`;
      this.error.hidden = false;
      this.error.onclick = () => this.loadMore();
      this.status.textContent = 'Loading paused';
    } finally {
      this.loading = false;
      if (this.error.hidden && this.tags.length && !this.exhausted && this.tags.length < this.total)
        this.maybeLoad();
    }
  }
}

export function initTagsCanvas() {
  const viewport = document.getElementById('tag-canvas-viewport');
  const canvas = document.getElementById('tag-canvas');
  if (viewport && canvas) new TagsCanvas(viewport, canvas).start();
}
