import test from 'node:test';
import assert from 'node:assert/strict';
import { computeSectionState } from '../libs/tag-info-sections.js';

// ------------------------------------------------------------------
// Minimal DOM stub.
//
// jsdom is not available in this repo, so (matching the convention of
// the other tests) we hand-roll just enough of the DOM API that
// computeSectionState relies on: querySelector / querySelectorAll with
// class-selectors and comma-separated tag-selectors, cloneNode(true),
// remove(), and textContent.
// ------------------------------------------------------------------

class El {
  constructor(tag, className = '') {
    this.tag = tag.toLowerCase();
    this.classList = new Set(className.split(/\s+/).filter(Boolean));
    this.childNodes = []; // mix of El instances and strings
    this.parent = null;
  }

  append(child) {
    if (child instanceof El) {
      child.parent = this;
    }
    this.childNodes.push(child);
    return this;
  }

  get textContent() {
    return this.childNodes
      .map((c) => (typeof c === 'string' ? c : c.textContent))
      .join('');
  }

  _elements() {
    return this.childNodes.filter((c) => c instanceof El);
  }

  _matches(selector) {
    if (selector.startsWith('.')) {
      return this.classList.has(selector.slice(1));
    }
    return selector.split(',').map((s) => s.trim()).includes(this.tag);
  }

  querySelectorAll(selector) {
    const out = [];
    for (const child of this._elements()) {
      if (child._matches(selector)) {
        out.push(child);
      }
      out.push(...child.querySelectorAll(selector));
    }
    return out;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  cloneNode() {
    const copy = new El(this.tag, [...this.classList].join(' '));
    for (const child of this.childNodes) {
      copy.append(child instanceof El ? child.cloneNode(true) : child);
    }
    return copy;
  }

  remove() {
    if (this.parent) {
      const idx = this.parent.childNodes.indexOf(this);
      if (idx !== -1) {
        this.parent.childNodes.splice(idx, 1);
      }
      this.parent = null;
    }
  }
}

// Tiny builder helper: el(tag, className, ...children)
function el(tag, className, ...children) {
  const node = new El(tag, className);
  for (const child of children) {
    node.append(child);
  }
  return node;
}

test('empty block (no children) is unloaded', () => {
  const block = el('div', 'tag_info_block');
  assert.equal(computeSectionState(block), 'unloaded');
});

test('block with only an empty-state marker is hidden', () => {
  const block = el(
    'div',
    'tag_info_block',
    el('p', 'tag-info-empty-state', 'No clusters')
  );
  assert.equal(computeSectionState(block), 'hidden');
});

test('block with real content (ol.cloud, no marker) is loaded', () => {
  const block = el(
    'div',
    'tag_info_block',
    el('ol', 'cloud', el('li', '', 'python'))
  );
  assert.equal(computeSectionState(block), 'loaded');
});

test('WordTree shape with only structural wrappers + markers is hidden', () => {
  const block = el(
    'div',
    'tag_info_block',
    el('div', '', el('p', 'tag-info-empty-state', 'No texts')),
    el('div', '', el('p', 'tag-info-empty-state', 'No data yet'))
  );
  block._elements()[0].classList.add('wordtree');
  block._elements()[1].classList.add('tag_contexts');
  assert.equal(computeSectionState(block), 'hidden');
});

test('placeholder-message load prompt (no marker) is loaded', () => {
  const block = el(
    'div',
    'tag_info_block',
    el('div', 'placeholder-message', 'No graph loaded')
  );
  assert.equal(computeSectionState(block), 'loaded');
});
