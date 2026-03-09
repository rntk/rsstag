import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}`);
  if (start === -1) {
    throw new Error(`Unable to find function ${name}`);
  }

  const bodyStart = source.indexOf('{', start);
  let depth = 0;
  let end = bodyStart;

  for (; end < source.length; end += 1) {
    const char = source[end];
    if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        break;
      }
    }
  }

  return source.slice(start, end + 1);
}

function loadSnippetFunctions() {
  const source = fs.readFileSync(new URL('../post-grouped-snippets.js', import.meta.url), 'utf8');
  const script = [
    'const CONTEXT_STEP = 1;',
    extractFunction(source, 'parseIndices'),
    extractFunction(source, 'buildSnippetSegmentMarkup'),
    extractFunction(source, 'updateExtendContextButton'),
    extractFunction(source, 'renderExpandedSnippet'),
    'module.exports = { parseIndices, updateExtendContextButton, renderExpandedSnippet };',
  ].join('\n\n');

  const context = {
    module: { exports: {} },
    exports: {},
  };

  vm.runInNewContext(script, context);
  return context.module.exports;
}

test('parseIndices normalizes comma-delimited and array values', () => {
  const { parseIndices } = loadSnippetFunctions();

  assert.deepEqual(Array.from(parseIndices('1, 2, x, 3')), [1, 2, 3]);
  assert.deepEqual(Array.from(parseIndices([4, '5', 'bad'])), [4, 5]);
  assert.deepEqual(Array.from(parseIndices('')), []);
});

test('renderExpandedSnippet updates markup, visible indices, and button state', () => {
  const { renderExpandedSnippet } = loadSnippetFunctions();
  const snippetText = { innerHTML: '' };
  const visibleLabel = { textContent: '' };
  const button = {
    disabled: false,
    textContent: '',
    title: '',
  };
  const snippetItem = {
    dataset: {
      visibleIndices: '2',
      canExtendBefore: '1',
      canExtendAfter: '1',
    },
    querySelector(selector) {
      if (selector === '.snippet-text') {
        return snippetText;
      }
      if (selector === '.snippet-visible-indices') {
        return visibleLabel;
      }
      if (selector === '.extend-snippet-context-btn') {
        return button;
      }
      return null;
    },
  };

  renderExpandedSnippet(snippetItem, {
    visible_indices: [1, 2, 3],
    before: { html: 'Before', indices: [1] },
    base: { html: 'Base', indices: [2] },
    after: { html: 'After', indices: [3] },
    can_extend_before: false,
    can_extend_after: true,
  });

  assert.match(snippetText.innerHTML, /<div class="snippet-context snippet-context-before snippet-context-new">/);
  assert.match(snippetText.innerHTML, /<div class="snippet-context snippet-context-base">/);
  assert.match(snippetText.innerHTML, /<div class="snippet-context snippet-context-after snippet-context-new">/);
  assert.equal(snippetItem.dataset.visibleIndices, '1,2,3');
  assert.equal(snippetItem.dataset.canExtendBefore, '0');
  assert.equal(snippetItem.dataset.canExtendAfter, '1');
  assert.equal(visibleLabel.textContent, '1, 2, 3');
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Extend context');
});

test('renderExpandedSnippet disables the button when no more context exists', () => {
  const { renderExpandedSnippet } = loadSnippetFunctions();
  const snippetItem = {
    dataset: {},
    querySelector(selector) {
      if (selector === '.snippet-text') {
        return { innerHTML: '' };
      }
      if (selector === '.extend-snippet-context-btn') {
        return {
          disabled: false,
          textContent: '',
          title: '',
        };
      }
      return null;
    },
  };

  const button = snippetItem.querySelector('.extend-snippet-context-btn');
  snippetItem.querySelector = (selector) => {
    if (selector === '.snippet-text') {
      return { innerHTML: '' };
    }
    if (selector === '.extend-snippet-context-btn') {
      return button;
    }
    return null;
  };

  renderExpandedSnippet(snippetItem, {
    visible_indices: [1, 2],
    before: { html: '', indices: [] },
    base: { html: 'Base', indices: [1, 2] },
    after: { html: '', indices: [] },
    can_extend_before: false,
    can_extend_after: false,
  });

  assert.equal(button.disabled, true);
  assert.equal(button.textContent, 'Full context shown');
});
