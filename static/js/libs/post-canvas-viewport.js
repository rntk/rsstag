/**
 * Pan/zoom controller for the post canvas, modeled on the extension's
 * useCanvasTransform: the transform lives in CSS variables on the viewport so
 * sticky card labels and the floating summary can clamp against it in CSS.
 */

import { clampScale, cursorAnchoredTranslate } from './post-canvas.js';

const WHEEL_ZOOM_SENSITIVITY = 0.0015;
const MAX_WHEEL_DELTA_PX = 120;
const ANIMATION_MS = 320;
const INTERACTIVE_SELECTOR = 'button, a, input, select, textarea, [data-no-pan]';
// Movement beyond this turns a press into a pan and swallows its click.
const DRAG_CLICK_TOLERANCE_PX = 4;

/**
 * @param {{area: HTMLElement, viewport: HTMLElement, onChange?: function(number): void}} options
 * @returns {{
 *   getScale: function(): number,
 *   getTranslate: function(): {x: number, y: number},
 *   setTransform: function(number, {x: number, y: number}, {animate?: boolean}=): void,
 *   zoomAt: function({x: number, y: number}, number): void,
 *   zoomFromCenter: function(number): void,
 *   panBy: function(number, number): void,
 * }}
 */
export function createViewport({ area, viewport, onChange = () => {} }) {
  const state = { scale: 1, translate: { x: 40, y: 40 }, animationTimer: 0 };

  const apply = () => {
    viewport.style.setProperty('--canvas-translate-x', `${state.translate.x}px`);
    viewport.style.setProperty('--canvas-translate-y', `${state.translate.y}px`);
    viewport.style.setProperty('--canvas-scale', String(state.scale));
    onChange(state.scale);
  };

  const setTransform = (scale, translate, { animate = false } = {}) => {
    window.clearTimeout(state.animationTimer);
    viewport.classList.toggle('is-animating', animate);
    if (animate) {
      state.animationTimer = window.setTimeout(
        () => viewport.classList.remove('is-animating'),
        ANIMATION_MS
      );
    }
    state.scale = clampScale(scale);
    state.translate = { x: translate.x, y: translate.y };
    apply();
  };

  const zoomAt = (cursor, nextScale) => {
    const scale = clampScale(nextScale);
    if (scale === state.scale) return;
    setTransform(
      scale,
      cursorAnchoredTranslate({
        cursor,
        translate: state.translate,
        scale: state.scale,
        nextScale: scale,
      })
    );
  };

  bindWheel(area, (cursor, factor) => zoomAt(cursor, state.scale * factor));
  bindDrag(area, state, (translate) => setTransform(state.scale, translate));
  bindAreaHeight(area, viewport);
  apply();

  return {
    getScale: () => state.scale,
    getTranslate: () => ({ ...state.translate }),
    setTransform,
    zoomAt,
    zoomFromCenter: (factor) =>
      zoomAt({ x: area.clientWidth / 2, y: area.clientHeight / 2 }, state.scale * factor),
    panBy: (dx, dy) =>
      setTransform(
        state.scale,
        { x: state.translate.x + dx, y: state.translate.y + dy },
        { animate: true }
      ),
  };
}

/** @param {HTMLElement} area @param {function({x: number, y: number}, number): void} zoom */
function bindWheel(area, zoom) {
  area.addEventListener(
    'wheel',
    (event) => {
      event.preventDefault();
      const bounds = area.getBoundingClientRect();
      const lineFactor = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? bounds.height : 1;
      const delta = Math.max(
        -MAX_WHEEL_DELTA_PX,
        Math.min(MAX_WHEEL_DELTA_PX, event.deltaY * lineFactor)
      );
      zoom(
        { x: event.clientX - bounds.left, y: event.clientY - bounds.top },
        Math.exp(-delta * WHEEL_ZOOM_SENSITIVITY)
      );
    },
    { passive: false }
  );
}

/**
 * Drag the background or article text to pan; controls keep their clicks.
 *
 * @param {HTMLElement} area
 * @param {{translate: {x: number, y: number}}} state
 * @param {function({x: number, y: number}): void} move
 */
function bindDrag(area, state, move) {
  let drag = null;
  let suppressClick = false;
  area.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || event.target.closest(INTERACTIVE_SELECTOR)) return;
    drag = {
      x: event.clientX - state.translate.x,
      y: event.clientY - state.translate.y,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    };
    area.focus({ preventScroll: true });
  });
  area.addEventListener('pointermove', (event) => {
    if (!drag) return;
    if (!drag.moved) {
      const distance = Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY);
      if (distance < DRAG_CLICK_TOLERANCE_PX) return;
      drag.moved = true;
      area.setPointerCapture?.(event.pointerId);
      area.classList.add('is-dragging');
    }
    move({ x: event.clientX - drag.x, y: event.clientY - drag.y });
  });
  area.addEventListener(
    'click',
    (event) => {
      if (!suppressClick) return;
      suppressClick = false;
      event.stopPropagation();
      event.preventDefault();
    },
    true
  );
  const stop = () => {
    suppressClick = Boolean(drag?.moved);
    drag = null;
    area.classList.remove('is-dragging');
  };
  area.addEventListener('pointerup', stop);
  area.addEventListener('pointercancel', stop);
}

/** Publish the visible height for the CSS sticky-label and summary clamps. */
function bindAreaHeight(area, viewport) {
  const update = () => viewport.style.setProperty('--canvas-area-height', `${area.clientHeight}px`);
  update();
  if (typeof window.ResizeObserver !== 'undefined') {
    new window.ResizeObserver(update).observe(area);
  } else {
    window.addEventListener('resize', update);
  }
}
