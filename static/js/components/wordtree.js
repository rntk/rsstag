'use strict';
import { buildWordTrees } from '../libs/wordtree-layout.js';

const SVG_NS = 'http://www.w3.org/2000/svg';

/** @param {string} name @param {Object<string, string|number>} attributes @returns {SVGElement} */
function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}

export default class WordTree {
  /** @param {string|Element} container_id @param {Object} event_system */
  constructor(container_id, event_system) {
    this.ES = event_system;
    this._container =
      typeof container_id === 'string' ? document.querySelector(container_id) : container_id;
    this.updateWordTree = this.updateWordTree.bind(this);
  }

  /** @param {{texts: string[], tag: string}} data @returns {void} */
  updateWordTree(data) {
    if (!this._container) return;
    this._container.replaceChildren();
    if (!data.texts.length) {
      this.showEmpty(this._container, 'No texts');
      return;
    }
    const section = document.createElement('section');
    section.className = 'wordtree';
    section.setAttribute('aria-label', 'Word tree');
    const toolbar = document.createElement('div');
    toolbar.className = 'wordtree__toolbar';
    const label = document.createElement('label');
    label.textContent = 'Context ';
    const direction = document.createElement('select');
    for (const [value, text] of [
      ['after', 'Following words'],
      ['before', 'Preceding words'],
    ]) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = text;
      direction.appendChild(option);
    }
    label.appendChild(direction);
    const summary = document.createElement('span');
    summary.className = 'wordtree__summary';
    summary.setAttribute('aria-live', 'polite');
    toolbar.append(label, summary);
    const viewport = document.createElement('div');
    viewport.className = 'wordtree__viewport';
    viewport.tabIndex = 0;
    viewport.setAttribute('role', 'region');
    viewport.setAttribute('aria-label', 'Word tree diagram; scroll to explore branches');
    section.append(toolbar, viewport);
    this._container.appendChild(section);
    const render = () => {
      const backwards = direction.value === 'before';
      const trees = buildWordTrees(data.texts, data.tag, backwards);
      const fallback = trees[0].root.label !== data.tag.trim();
      viewport.replaceChildren();
      summary.textContent =
        (fallback ? 'Individual word contexts · ' : '') +
        trees
          .map((tree) => {
            let description = `${fallback ? tree.root.label + ': ' : ''}${tree.occurrences} occurrence${tree.occurrences === 1 ? '' : 's'}`;
            if (tree.totalPaths > tree.shownPaths) {
              description += ` · Showing ${tree.shownPaths} of ${tree.totalPaths} contexts`;
            }
            return description;
          })
          .join(' · ');
      if (!trees[0].occurrences) {
        this.showEmpty(viewport, 'No matching contexts in the loaded posts');
        return;
      }
      for (const tree of trees) this.drawTree(viewport, tree.root, backwards);
    };
    direction.addEventListener('change', render);
    render();
  }

  /** @param {Element} container @param {string} message @returns {void} */
  showEmpty(container, message) {
    const empty = document.createElement('p');
    empty.className = 'tag-info-empty-state';
    empty.textContent = message;
    container.appendChild(empty);
  }

  /** @param {Element} container @param {Object} root @param {boolean} backwards @returns {void} */
  drawTree(container, root, backwards) {
    const svg = svgElement('svg', { role: 'img', 'aria-label': `Word contexts for ${root.label}` });
    const title = svgElement('title');
    title.textContent = `${root.label}: ${root.count} occurrences. ${backwards ? 'Preceding' : 'Following'} words.`;
    svg.appendChild(title);
    container.appendChild(svg);
    const nodes = [];
    const edges = [];
    let row = 0;
    let width = 0;
    // Measure real SVG text so long phrases and Unicode never overlap branches.
    const place = (branch, x, isRoot = false) => {
      const size = isRoot ? 46 : Math.round(12 + 22 * Math.sqrt(branch.count / root.count));
      const text = svgElement('text', { x, 'font-size': size, 'dominant-baseline': 'middle' });
      text.textContent = branch.label;
      text.setAttribute('class', isRoot ? 'wordtree__root' : 'wordtree__phrase');
      const tooltip = svgElement('title');
      tooltip.textContent = `${branch.label} — ${branch.count} occurrence${branch.count === 1 ? '' : 's'}`;
      text.appendChild(tooltip);
      svg.appendChild(text);
      const textWidth =
        typeof text.getComputedTextLength === 'function'
          ? text.getComputedTextLength() || branch.label.length * size * 0.6
          : branch.label.length * size * 0.6;
      const item = { text, x, width: textWidth, y: 0 };
      const children = branch.children.map((child) => place(child, x + textWidth + 56));
      if (children.length) item.y = (children[0].y + children[children.length - 1].y) / 2;
      else item.y = 40 + row++ * 44;
      text.setAttribute('y', String(item.y));
      for (const child of children) edges.push({ parent: item, child });
      nodes.push(item);
      width = Math.max(width, x + textWidth + 24);
      return item;
    };
    place(root, 24, true);
    const height = Math.max(160, row * 44 + 40);
    if (backwards) {
      for (const item of nodes) {
        item.x = width - item.x - item.width;
        item.text.setAttribute('x', String(item.x));
      }
    }
    const links = svgElement('g', { class: 'wordtree__links', 'aria-hidden': 'true' });
    for (const { parent, child } of edges) {
      const start = backwards ? parent.x - 6 : parent.x + parent.width + 6;
      const end = backwards ? child.x + child.width + 6 : child.x - 6;
      const middle = (start + end) / 2;
      links.appendChild(
        svgElement('path', {
          d: `M ${start} ${parent.y} C ${middle} ${parent.y}, ${middle} ${child.y}, ${end} ${child.y}`,
        })
      );
    }
    svg.insertBefore(links, svg.children[1]);
    svg.setAttribute('width', String(width));
    svg.setAttribute('height', String(height));
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    if (backwards) container.scrollLeft = width;
  }

  /** @returns {void} */
  bindEvents() {
    this.ES.bind(this.ES.WORDTREE_TEXTS_UPDATED, this.updateWordTree);
  }

  /** @returns {void} */
  start() {
    this.bindEvents();
  }
}
