import React from 'react';
import { buildPostDocument } from '../libs/post-content-document.js';
import { fitFrame } from '../libs/post-content-frame-size.js';

/** Re-dispatch frame key presses so page shortcuts keep working.
 * @param {KeyboardEvent} event @returns {void}
 */
function forwardKey(event) {
  if (event.target.closest('input,textarea,select,[contenteditable]')) return;
  const forwarded = new window.KeyboardEvent(event.type, {
    key: event.key,
    code: event.code,
    keyCode: event.keyCode,
    ctrlKey: event.ctrlKey,
    shiftKey: event.shiftKey,
    altKey: event.altKey,
    metaKey: event.metaKey,
    bubbles: true,
    cancelable: true,
  });
  if (!document.dispatchEvent(forwarded)) event.preventDefault();
}

/**
 * @param {HTMLIFrameElement} frame @param {Document} doc @param {Function} onSelect
 * @returns {Function} cleanup
 */
function listen(frame, doc, onSelect) {
  const select = () => onSelect();
  const resize = () => fitFrame(frame, doc);
  const observer = window.ResizeObserver ? new window.ResizeObserver(resize) : null;
  observer?.observe(doc.body);
  doc.addEventListener('click', select);
  doc.addEventListener('focusin', select);
  doc.addEventListener('keydown', forwardKey);
  doc.addEventListener('keyup', forwardKey);
  // Images report here as they arrive, before the frame's own load event.
  doc.addEventListener('load', resize, true);
  window.addEventListener('resize', resize);
  resize();
  return () => {
    observer?.disconnect();
    doc.removeEventListener('click', select);
    doc.removeEventListener('focusin', select);
    doc.removeEventListener('keydown', forwardKey);
    doc.removeEventListener('keyup', forwardKey);
    doc.removeEventListener('load', resize, true);
    window.removeEventListener('resize', resize);
  };
}

/** An article document, isolated from page CSS and from every other article. */
export default class PostContentFrame extends React.Component {
  /** @param {{html: string, url: string, words: string[], onSelect: Function}} props */
  constructor(props) {
    super(props);
    this.frame = React.createRef();
    this.onLoad = this.onLoad.bind(this);
    this.cleanup = () => {};
    this.doc = null;
    this.watch = 0;
  }

  componentDidMount() {
    this.watchDocument();
  }

  componentDidUpdate() {
    if (this.watchedSource !== this.source) this.watchDocument();
  }

  componentWillUnmount() {
    window.cancelAnimationFrame(this.watch);
    this.cleanup();
  }

  /** Attach once the new srcdoc document is parsed, without waiting for images. */
  watchDocument() {
    window.cancelAnimationFrame(this.watch);
    this.watchedSource = this.source;
    const previous = this.frame.current?.contentDocument;
    const poll = () => {
      const doc = this.frame.current?.contentDocument;
      if (!doc || doc === previous || doc.URL !== 'about:srcdoc') {
        this.watch = window.requestAnimationFrame(poll);
      } else if (doc.readyState === 'loading') {
        doc.addEventListener('DOMContentLoaded', () => this.attach(doc), { once: true });
      } else {
        this.attach(doc);
      }
    };
    poll();
  }

  /** @param {Document | null | undefined} doc @returns {void} */
  attach(doc) {
    const frame = this.frame.current;
    if (!frame || !doc?.body || doc === this.doc || doc !== frame.contentDocument) return;
    window.cancelAnimationFrame(this.watch);
    this.cleanup();
    this.doc = doc;
    this.cleanup = listen(frame, doc, () => this.props.onSelect());
  }

  // Fallback for when animation frames are throttled, e.g. in a background tab.
  onLoad() {
    this.attach(this.frame.current?.contentDocument);
  }

  render() {
    const { html, url, words } = this.props;
    // Selection/read-status updates must not reload images or reset frame focus.
    const key = JSON.stringify([html, url, words]);
    if (key !== this.documentKey) {
      this.documentKey = key;
      this.source = buildPostDocument(html, url, words);
    }
    return (
      <iframe
        className="post-content-frame"
        title="Post content"
        ref={this.frame}
        srcDoc={this.source}
        sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
        onLoad={this.onLoad}
      />
    );
  }
}
