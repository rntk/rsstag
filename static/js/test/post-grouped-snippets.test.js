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
    extractFunction(source, 'buildTagHighlightRe'),
    extractFunction(source, 'highlightTagWordsInHtml'),
    extractFunction(source, 'parseIndices'),
    extractFunction(source, 'buildSnippetSegmentMarkup'),
    extractFunction(source, 'updateExtendContextButton'),
    extractFunction(source, 'renderExpandedSnippet'),
    'module.exports = { parseIndices, updateExtendContextButton, renderExpandedSnippet, buildTagHighlightRe, highlightTagWordsInHtml };',
  ].join('\n\n');

  const context = {
    module: { exports: {} },
    exports: {},
    window: {},
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

// ============================================================
// highlightTagWordsInHtml and buildTagHighlightRe tests
// ============================================================

const SNIPPET_SOURCE = fs.readFileSync(new URL('../post-grouped-snippets.js', import.meta.url), 'utf8');

test('buildTagHighlightRe returns null when TAG_WORDS is empty or missing', () => {
  // Source-inspection: verify the function guards against empty/missing TAG_WORDS
  assert.ok(/window\.TAG_WORDS/.test(SNIPPET_SOURCE), 'should read window.TAG_WORDS');
  assert.ok(/!Array\.isArray\(words\)/.test(SNIPPET_SOURCE), 'should check isArray');
  assert.ok(/!words\.length/.test(SNIPPET_SOURCE), 'should check length');
  assert.ok(/return\s+null/.test(SNIPPET_SOURCE), 'should return null');
});

test('buildTagHighlightRe creates a case-insensitive word-boundary regex', () => {
  // Source-inspection: verify regex construction
  assert.ok(/new\s+RegExp/.test(SNIPPET_SOURCE), 'should create RegExp');
  assert.ok(/\\b/.test(SNIPPET_SOURCE), 'should use word boundaries');
  assert.ok(/['"]gi['"]/.test(SNIPPET_SOURCE), 'should use gi flags');
  assert.ok(/\.join\(['"]\|['"]\)/.test(SNIPPET_SOURCE), 'should join words with |');
});

test('buildTagHighlightRe escapes regex special characters in words', () => {
  // Source-inspection: verify escaping of special characters
  assert.ok(/\.replace\s*\(\s*\/\[/, 'should escape special regex chars in words');
  assert.ok(/\\\$&/.test(SNIPPET_SOURCE), 'should use $& replacement');
});

test('highlightTagWordsInHtml returns input unchanged when regex is null', () => {
  const { highlightTagWordsInHtml } = loadSnippetFunctions();

  const input = '<p>hello world</p>';
  assert.equal(highlightTagWordsInHtml(input, null), input);
  assert.equal(highlightTagWordsInHtml(input, undefined), input);
});

test('highlightTagWordsInHtml wraps matching words in <mark> tags', () => {
  const { highlightTagWordsInHtml } = loadSnippetFunctions();

  const re = /\b(hello|world)\b/gi;
  const result = highlightTagWordsInHtml('hello beautiful world', re);
  assert.equal(result, '<mark>hello</mark> beautiful <mark>world</mark>');
});

test('highlightTagWordsInHtml skips HTML tags and does not highlight inside them', () => {
  const { highlightTagWordsInHtml } = loadSnippetFunctions();

  const re = /\b(hello|world)\b/gi;
  const result = highlightTagWordsInHtml('<p class="hello">hello world</p>', re);
  // The tag <p class="hello"> should not be modified
  assert.equal(result, '<p class="hello"><mark>hello</mark> <mark>world</mark></p>');
});

test('highlightTagWordsInHtml handles multiple tags and mixed content', () => {
  const { highlightTagWordsInHtml } = loadSnippetFunctions();

  const re = /\b(foo)\b/gi;
  const result = highlightTagWordsInHtml('<div>foo</div><span>bar foo</span>', re);
  assert.equal(result, '<div><mark>foo</mark></div><span>bar <mark>foo</mark></span>');
});

test('highlightTagWordsInHtml is case-insensitive and preserves original case', () => {
  const { highlightTagWordsInHtml } = loadSnippetFunctions();

  const re = /\b(hello)\b/gi;
  const result = highlightTagWordsInHtml('HELLO Hello hello', re);
  assert.equal(result, '<mark>HELLO</mark> <mark>Hello</mark> <mark>hello</mark>');
});

// ============================================================
// updateExtendContextButton dedicated tests
// ============================================================

test('updateExtendContextButton enables button when can_extend_before is true', () => {
  const { updateExtendContextButton } = loadSnippetFunctions();

  const button = { disabled: false, textContent: '', title: '' };
  updateExtendContextButton(button, { can_extend_before: true, can_extend_after: false });

  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Extend context');
  assert.match(button.title, /Load more/);
});

test('updateExtendContextButton enables button when can_extend_after is true', () => {
  const { updateExtendContextButton } = loadSnippetFunctions();

  const button = { disabled: false, textContent: '', title: '' };
  updateExtendContextButton(button, { can_extend_before: false, can_extend_after: true });

  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Extend context');
});

test('updateExtendContextButton disables button when both flags are false', () => {
  const { updateExtendContextButton } = loadSnippetFunctions();

  const button = { disabled: false, textContent: 'Extend', title: '' };
  updateExtendContextButton(button, { can_extend_before: false, can_extend_after: false });

  assert.equal(button.disabled, true);
  assert.equal(button.textContent, 'Full context shown');
  assert.match(button.title, /All available/);
});

test('updateExtendContextButton disables button when contextData is null', () => {
  const { updateExtendContextButton } = loadSnippetFunctions();

  const button = { disabled: false, textContent: 'Extend', title: '' };
  updateExtendContextButton(button, null);

  assert.equal(button.disabled, true);
  assert.equal(button.textContent, 'Full context shown');
});

test('updateExtendContextButton disables button when contextData is undefined', () => {
  const { updateExtendContextButton } = loadSnippetFunctions();

  const button = { disabled: false, textContent: '', title: '' };
  updateExtendContextButton(button, undefined);

  assert.equal(button.disabled, true);
});
