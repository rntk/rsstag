/** @param {Document} doc @returns {number} */
function contentHeight(doc) {
  return Math.max(1, doc.documentElement.scrollHeight, doc.body.scrollHeight);
}

/**
 * Size a frame to its document. Growth is applied directly so the page's scroll
 * anchoring still works; only a possible shrink needs the collapse-and-measure
 * pass, which can clamp or shift the page scroll, so that position is restored.
 * @param {HTMLIFrameElement} frame @param {Document} doc @returns {void}
 */
export function fitFrame(frame, doc) {
  const natural = contentHeight(doc);
  if (natural > frame.clientHeight) {
    frame.style.height = `${natural}px`;
    return;
  }
  const { scrollX, scrollY } = window;
  frame.style.height = '0px';
  frame.style.height = `${contentHeight(doc)}px`;
  if (window.scrollX !== scrollX || window.scrollY !== scrollY) {
    window.scrollTo(scrollX, scrollY);
  }
}
