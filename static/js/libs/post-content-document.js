/** Only passive article HTML is admitted to a same-origin, script-disabled frame. */
const BLOCKED_ELEMENTS = 'script,iframe,frame,frameset,object,embed,base,meta';
const URL_ATTRIBUTES = new Set(['href', 'src', 'action', 'formaction', 'xlink:href']);

/** @param {string} value @param {string} fallback @returns {string} */
function articleBase(value, fallback) {
  if (!value) return fallback;
  try {
    const url = new URL(value, fallback);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : fallback;
  } catch {
    return fallback;
  }
}

/** Highlight text without touching CSS, attributes, or raw-text elements.
 * @param {Document} doc @param {string[]} words @returns {void}
 */
export function highlightPostText(doc, words) {
  const terms = [...new Set(words.filter(Boolean))].sort((a, b) => b.length - a.length);
  if (!terms.length) return;
  const escaped = terms.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`(${escaped.join('|')})`, 'gi');
  const walker = doc.createTreeWalker(doc.body, 4);
  /** @type {Text[]} */
  const nodes = [];
  while (walker.nextNode()) {
    if (!walker.currentNode.parentElement.closest('style,script,textarea,title,svg,math')) {
      nodes.push(walker.currentNode);
    }
  }
  for (const node of nodes) {
    const text = node.textContent;
    const fragment = doc.createDocumentFragment();
    let start = 0;
    for (const match of text.matchAll(pattern)) {
      fragment.append(text.slice(start, match.index));
      const mark = doc.createElement('mark');
      mark.className = 'highlite_tag';
      mark.textContent = match[0];
      fragment.append(mark);
      start = match.index + match[0].length;
    }
    if (start) {
      fragment.append(text.slice(start));
      node.replaceWith(fragment);
    }
  }
}

/**
 * Keep author CSS, but remove active HTML before serialization. Sandbox and CSP
 * also enforce script blocking; sanitization alone is not the security boundary.
 * @param {string} html @param {string} url @param {string[]} words
 * @returns {string}
 */
export function buildPostDocument(html, url, words = []) {
  const doc = new window.DOMParser().parseFromString(html || '', 'text/html');
  for (const element of doc.querySelectorAll(BLOCKED_ELEMENTS)) element.remove();
  for (const element of doc.querySelectorAll('*')) {
    for (const attribute of [...element.attributes]) {
      const name = attribute.name.toLowerCase();
      const value = Array.from(attribute.value)
        .filter((character) => character.charCodeAt(0) > 32)
        .join('')
        .toLowerCase();
      if (
        name.startsWith('on') ||
        name === 'srcdoc' ||
        (URL_ATTRIBUTES.has(name) && /^(javascript|vbscript):/.test(value))
      )
        element.removeAttribute(attribute.name);
    }
  }
  const base = doc.createElement('base');
  base.href = articleBase(url, `${window.location.origin}/`);
  base.target = '_blank';
  for (const link of doc.querySelectorAll('a[href],area[href]')) {
    // Local footnotes stay inside the article; external links open separately.
    const local = link.getAttribute('href').startsWith('#');
    if (local) link.setAttribute('href', `about:srcdoc${link.getAttribute('href')}`);
    link.target = local ? '_self' : '_blank';
    link.rel = 'noopener noreferrer';
  }
  const policy = doc.createElement('meta');
  policy.httpEquiv = 'Content-Security-Policy';
  policy.content =
    "default-src 'none'; script-src 'none'; style-src 'unsafe-inline' http: https:; img-src http: https: data: blob:; font-src http: https: data:; media-src http: https: blob:; form-action 'none'; frame-src 'none'; object-src 'none'";
  const stylesheet = doc.createElement('link');
  stylesheet.rel = 'stylesheet';
  stylesheet.href = `${window.location.origin}/static/css/pages/post-content-frame.css`;
  doc.head.prepend(policy, base, stylesheet);
  highlightPostText(doc, words);
  return `<!doctype html>\n${doc.documentElement.outerHTML}`;
}
