import { describe, it, expect, vi, afterEach } from 'vitest';
import { fitFrame } from '../libs/post-content-frame-size.js';

/**
 * A frame whose document reports `natural` px of content while the frame is
 * at least that tall, and its real height once collapsed to 0.
 * @param {number} current @param {number} natural @param {number} collapsed
 */
function setup(current, natural, collapsed) {
  const frame = document.createElement('iframe');
  frame.style.height = `${current}px`;
  Object.defineProperty(frame, 'clientHeight', { get: () => parseFloat(frame.style.height) });
  const measure = () => (frame.style.height === '0px' ? collapsed : natural);
  const doc = {
    documentElement: {
      get scrollHeight() {
        return measure();
      },
    },
    body: { scrollHeight: 0 },
  };
  return { frame, doc };
}

/** Record every height written to the frame, letting `onSet` react to each. */
function trackHeights(frame, onSet = () => {}) {
  const heights = [];
  const style = frame.style;
  vi.spyOn(style, 'height', 'set').mockImplementation((value) => {
    heights.push(value);
    onSet(value);
    style.setProperty('height', value);
  });
  return heights;
}

describe('fitFrame', () => {
  afterEach(() => vi.restoreAllMocks());

  it('grows without collapsing the frame or touching page scroll', () => {
    const { frame, doc } = setup(100, 400, 400);
    const heights = trackHeights(frame);
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    fitFrame(frame, doc);
    expect(heights).toEqual(['400px']);
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('shrinks to content and restores a scroll position the collapse moved', () => {
    const { frame, doc } = setup(400, 400, 120);
    let y = 900;
    vi.spyOn(window, 'scrollY', 'get').mockImplementation(() => y);
    vi.spyOn(window, 'scrollX', 'get').mockReturnValue(0);
    trackHeights(frame, (value) => {
      if (value === '0px') y = 500; // the page got shorter and clamped scroll
    });
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    fitFrame(frame, doc);
    expect(frame.style.height).toBe('120px');
    expect(scrollTo).toHaveBeenCalledWith(0, 900);
  });
});
