import { describe, it, expect } from 'vitest';
import { buildPostDocument } from '../libs/post-content-document.js';

/** @param {string} html @param {string[]} words @returns {Document} */
function build(html, words = []) {
  return new window.DOMParser().parseFromString(
    buildPostDocument(html, 'https://author.example/articles/post', words),
    'text/html'
  );
}

describe('isolated post document', () => {
  it('preserves author styles, layout, and relative images in a separate document', () => {
    const doc = build(
      '<style>body {color: purple} p {margin: 3em}</style><link rel="stylesheet" href="../article.css"><p style="font-weight: bold"><img src="../photo.jpg">Hello</p>'
    );
    expect(doc.querySelector('style').textContent).toContain('color: purple');
    expect(doc.querySelector('p').getAttribute('style')).toBe('font-weight: bold');
    expect(doc.querySelector('img').src).toBe('https://author.example/photo.jpg');
    expect([...doc.querySelectorAll('link')].at(-1).href).toBe(
      'https://author.example/article.css'
    );
    expect(document.querySelector('style')).toBeNull();
    expect(doc.head.firstChild.httpEquiv).toBe('Content-Security-Policy');
  });

  it('removes active HTML and prevents content from replacing the base or policy', () => {
    const doc = build(
      '<base href="https://evil.example"><meta http-equiv="refresh" content="0;url=/logout"><script>alert(1)</script><iframe srcdoc="bad"></iframe><object data="/bad"></object><p onclick="bad()"><a href="java&#10;script:alert(1)">link</a></p>'
    );
    expect(doc.querySelectorAll('script,iframe,object')).toHaveLength(0);
    expect(doc.querySelector('p').hasAttribute('onclick')).toBe(false);
    expect(doc.querySelector('a').hasAttribute('href')).toBe(false);
    expect(doc.querySelectorAll('base')).toHaveLength(1);
    expect(doc.querySelectorAll('meta')).toHaveLength(1);
    expect(doc.querySelector('meta').content).toContain("script-src 'none'");
    expect(doc.querySelector('base').href).toBe('https://author.example/articles/post');
  });

  it('highlights literal words only in text, preserving CSS and attributes', () => {
    const doc = build(
      '<style>.cat { color: red }</style><p title="cat">cat c++ &amp; cat</p><textarea>cat</textarea><svg><text>cat</text></svg>',
      ['cat', 'c++']
    );
    expect(doc.querySelectorAll('mark')).toHaveLength(3);
    expect(doc.querySelector('p').textContent).toBe('cat c++ & cat');
    expect(doc.querySelector('p').title).toBe('cat');
    expect(doc.querySelector('style').textContent).toBe('.cat { color: red }');
    expect(doc.querySelector('textarea').textContent).toBe('cat');
    expect(doc.querySelector('svg mark')).toBeNull();
  });

  it('opens external links separately and keeps footnotes inside the frame', () => {
    const doc = build('<a href="next">next</a><a href="#note">note</a><p id="note">Footnote</p>');
    const [external, local] = doc.querySelectorAll('a');
    expect(external.href).toBe('https://author.example/articles/next');
    expect(external.target).toBe('_blank');
    expect(external.rel).toBe('noopener noreferrer');
    expect(local.getAttribute('href')).toBe('about:srcdoc#note');
    expect(local.target).toBe('_self');
  });

  it('handles missing HTML and invalid source URLs', () => {
    const source = buildPostDocument(undefined, 'javascript:alert(1)');
    const doc = new window.DOMParser().parseFromString(source, 'text/html');
    expect(doc.body.textContent).toBe('');
    expect(doc.querySelector('base').href).toBe(`${window.location.origin}/`);
    const missing = new window.DOMParser().parseFromString(
      buildPostDocument('', undefined),
      'text/html'
    );
    expect(missing.querySelector('base').href).toBe(`${window.location.origin}/`);
  });
});
