import { afterEach, describe, expect, it, vi } from 'vitest';
import { TagsCanvas } from '../tags-canvas.js';

function setupCanvas() {
  document.body.innerHTML = `<div id="tag-canvas-viewport"><canvas id="tag-canvas" tabindex="0"></canvas>
    <div id="tag-canvas-menu" class="tag-canvas-menu" hidden>
      <svg viewBox="0 0 360 360"></svg><a class="tag-canvas-menu__center"></a>
      <div class="tag-canvas-menu__words" hidden></div></div>
    <div id="tag-canvas-status"></div><div id="tag-canvas-error" hidden></div>
    <button id="tag-canvas-zoom-in"></button><button id="tag-canvas-zoom-out"></button>
    <span id="tag-canvas-zoom-level"></span><button id="tag-canvas-reset"></button>
    <div class="tag-canvas-navigation"><button data-pan="left"></button></div>
    <input type="radio" name="tag-canvas-metric" value="count" checked>
    <input type="radio" name="tag-canvas-metric" value="temperature"></div>`;
  const canvas = document.getElementById('tag-canvas');
  const context = {
    clearRect: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    translate: vi.fn(),
    scale: vi.fn(),
    setTransform: vi.fn(),
    measureText: vi.fn(() => ({ width: 100 })),
    fillText: vi.fn(),
  };
  vi.spyOn(canvas, 'getContext').mockReturnValue(context);
  vi.spyOn(canvas, 'getBoundingClientRect').mockReturnValue({
    left: 0,
    top: 0,
    width: 900,
    height: 700,
  });
  vi.spyOn(document.getElementById('tag-canvas-viewport'), 'getBoundingClientRect').mockReturnValue(
    {
      left: 0,
      top: 0,
      width: 900,
      height: 700,
    }
  );
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
    }
  );
  vi.stubGlobal(
    'requestAnimationFrame',
    vi.fn(() => 1)
  );
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ total: 0, tags: [] }),
      })
    )
  );
  const view = new TagsCanvas(document.getElementById('tag-canvas-viewport'), canvas);
  view.width = 900;
  view.viewHeight = 700;
  return { view, canvas, context };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.body.innerHTML = '';
});

describe('tag canvas font scaling', () => {
  it.each([
    ['count', [1, 3, 5]],
    ['count', [2000, 4000, 8000]],
    ['temperature', [0.001, 0.002, 0.003]],
    ['temperature', [25, 50, 100]],
  ])('renders distinct sizes for %s values %j', (metric, values) => {
    const { view, context } = setupCanvas();
    view.metric = metric;
    view.tags = values.map((value, index) => ({ tag: `tag-${index}`, [metric]: value }));
    const fonts = [];
    context.fillText.mockImplementation(() => fonts.push(context.font));

    view.layout();
    view.draw();

    const sizes = fonts.map((font) => Number(font.split(' ')[1].replace('px', '')));
    expect(sizes).toHaveLength(3);
    expect(sizes[0]).toBe(16);
    expect(sizes[1]).toBeGreaterThan(sizes[0]);
    expect(sizes[1]).toBeLessThan(sizes[2]);
    expect(sizes[2]).toBe(40);
  });

  it('resizes and remeasures tags when switching metrics', () => {
    const { view, context } = setupCanvas();
    context.measureText.mockImplementation(() => ({
      width: parseFloat(context.font.split(' ')[1]) * 5,
    }));
    view.start();
    view.tags = [
      { tag: 'frequent', count: 10, temperature: 0.001 },
      { tag: 'hot', count: 1, temperature: 0.005 },
    ];
    view.total = 2;
    view.layout();
    const items = () => view.rows.flatMap((row) => row.items);
    expect(items().map((item) => item.size)).toEqual([40, 16]);
    const frequencyWidths = items().map((item) => item.width);

    const input = document.querySelector('input[value="temperature"]');
    input.checked = true;
    input.dispatchEvent(new Event('change'));

    expect(items().map((item) => item.size)).toEqual([16, 40]);
    expect(items().map((item) => item.width)).toEqual(frequencyWidths.reverse());
    const row = view.rows[0];
    const item = row.items[0];
    expect(view.hit(view.x + item.x + item.width / 2, view.y + row.y + row.height / 2)).toBe(
      item.tag
    );
  });

  it('updates existing sizes when a later batch extends the metric range', () => {
    const { view } = setupCanvas();
    view.tags = [
      { tag: 'first', count: 2 },
      { tag: 'second', count: 4 },
    ];
    view.layout();
    expect(view.rows.flatMap((row) => row.items).map((item) => item.size)).toEqual([16, 40]);

    view.tags.push({ tag: 'third', count: 20 });
    view.layout();

    const sizes = view.rows.flatMap((row) => row.items).map((item) => item.size);
    expect(sizes[0]).toBe(16);
    expect(sizes[1]).toBeGreaterThan(16);
    expect(sizes[1]).toBeLessThan(40);
    expect(sizes[2]).toBe(40);
  });

  it('uses equal finite sizes for equal, missing, or invalid values', () => {
    const { view } = setupCanvas();
    view.metric = 'temperature';
    view.tags = [0, undefined, -1, 'invalid', Infinity].map((temperature, index) => ({
      tag: `tag-${index}`,
      temperature,
    }));
    view.layout();
    expect(view.rows.flatMap((row) => row.items).map((item) => item.size)).toEqual([
      28, 28, 28, 28, 28,
    ]);
  });
});

describe('tag canvas menu', () => {
  it('shows tag links in sectors and keeps a long words list in a popup', () => {
    const { view } = setupCanvas();
    const tag = {
      tag: 'two words',
      url: '/entity/two-words',
      count: 12,
      temperature: 1.5,
      words: Array.from({ length: 100 }, (_, i) => `word ${i}`),
    };

    view.showMenu(tag, 450, 350);

    const menu = document.getElementById('tag-canvas-menu');
    expect(menu.hidden).toBe(false);
    expect(menu.querySelector('.tag-canvas-menu__center span').textContent).toBe('two words');
    expect(menu.querySelector('.tag-canvas-menu__center small').textContent).toBe('12 matches');
    expect(menu.querySelector('.tag-canvas-menu__center').getAttribute('href')).toBe(tag.url);
    const links = [...menu.querySelectorAll('svg a')];
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/tag-info/two%20words',
      '/sentences/with/tags/two%20words',
      '/sunburst/two%20words',
      '/chain/two%20words',
      '/tag-context-tree/two%20words',
      '/tag-concordance/two%20words',
      '/tag-explorer/two%20words',
      '/context-tags/two%20words',
    ]);
    expect(menu.querySelector('[role="button"]').getAttribute('aria-label')).toBe('Words');
    expect(menu.querySelector('.tag-canvas-menu__words').hidden).toBe(true);

    menu.querySelector('[role="button"]').dispatchEvent(new Event('mouseenter'));
    expect(menu.querySelectorAll('.tag-canvas-menu__words li')).toHaveLength(100);
    expect(menu.querySelector('.tag-canvas-menu__words').hidden).toBe(false);

    view.hideMenu();
    expect(menu.hidden).toBe(true);
  });

  it('closes a hover menu on window Escape and restores canvas focus only when menu had focus', () => {
    const { view, canvas } = setupCanvas();
    view.start();
    const tag = { tag: 'focused', url: '/tag/focused', count: 1 };
    const focus = vi.spyOn(canvas, 'focus');

    view.showMenu(tag, 450, 350);
    const escapeWithoutMenuFocus = new KeyboardEvent('keydown', {
      key: 'Escape',
      bubbles: true,
      cancelable: true,
    });
    window.dispatchEvent(escapeWithoutMenuFocus);
    expect(document.getElementById('tag-canvas-menu').hidden).toBe(true);
    expect(escapeWithoutMenuFocus.defaultPrevented).toBe(true);
    expect(focus).not.toHaveBeenCalled();

    view.showMenu(tag, 450, 350);
    document.querySelector('#tag-canvas-menu a').focus();
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    );
    expect(document.getElementById('tag-canvas-menu').hidden).toBe(true);
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
  });

  it('does not reopen a dismissed tag on immediate hover', () => {
    const { view, canvas } = setupCanvas();
    view.start();
    const tag = { tag: 'same', url: '/tag/same', count: 1 };
    view.showMenu(tag, 200, 200);
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }));
    view.hit = vi.fn(() => tag);
    const move = new Event('pointermove');
    Object.assign(move, { clientX: 200, clientY: 200, pointerType: 'mouse', pointerId: 2 });
    canvas.dispatchEvent(move);
    expect(document.getElementById('tag-canvas-menu').hidden).toBe(true);
    expect(view.dismissedTag).toBe(tag);
  });

  it('clamps zoom to 20%–240%, anchors at the pointer, and disables controls at limits', () => {
    const { view } = setupCanvas();
    view.x = 100;
    view.y = 80;
    view.zoomAt(2, 300, 200);
    expect(view.zoom).toBe(2);
    expect(view.x).toBe(-100);
    expect(view.y).toBe(-40);

    view.zoomAt(10, 300, 200);
    expect(view.zoom).toBe(2.4);
    expect(view.x).toBeCloseTo(-180);
    expect(view.y).toBeCloseTo(-88);
    expect(document.getElementById('tag-canvas-zoom-in').disabled).toBe(true);
    expect(document.getElementById('tag-canvas-zoom-out').disabled).toBe(false);

    view.zoomAt(0.001, 300, 200);
    expect(view.zoom).toBe(0.2);
    expect(document.getElementById('tag-canvas-zoom-in').disabled).toBe(false);
    expect(document.getElementById('tag-canvas-zoom-out').disabled).toBe(true);
  });

  it('requests more tags when zooming out reveals unfilled areas', () => {
    const { view } = setupCanvas();
    view.exhausted = false;
    view.total = 500;
    view.tags = Array.from({ length: 250 }, () => ({}));
    view.zoom = 0.3;
    view.y = -100;
    view.loadMore = vi.fn();

    view.zoomAt(0.5, 450, 350);

    expect(view.zoom).toBe(0.2);
    expect(view.loadMore).toHaveBeenCalledOnce();
  });

  it('zooms on wheel over the menu and leaves wheel scrolling available in the Words popup', () => {
    const { view } = setupCanvas();
    view.start();
    view.showMenu({ tag: 'wheel', url: '/tag/wheel', words: ['one'] }, 450, 350);
    const words = document.querySelector('.tag-canvas-menu__words');
    view.showWords({ tag: 'wheel', words: ['one'] });
    const zoomAt = vi.spyOn(view, 'zoomAt');
    const menuWheel = new WheelEvent('wheel', { deltaY: 100, bubbles: true, cancelable: true });
    document.querySelector('#tag-canvas-menu svg').dispatchEvent(menuWheel);
    expect(menuWheel.defaultPrevented).toBe(true);
    expect(zoomAt).toHaveBeenCalledWith(Math.exp(-0.1), expect.any(Number), expect.any(Number));

    const popupWheel = new WheelEvent('wheel', { deltaY: 100, bubbles: true, cancelable: true });
    words.dispatchEvent(popupWheel);
    expect(popupWheel.defaultPrevented).toBe(false);
    expect(zoomAt).toHaveBeenCalledOnce();
  });

  it('ignores canvas shortcuts when a radio or text input owns the key event', () => {
    const { view, canvas } = setupCanvas();
    const pan = vi.spyOn(view, 'pan');
    const input = document.querySelector('input[type="radio"]');
    const radioArrow = new KeyboardEvent('keydown', { key: 'ArrowDown', cancelable: true });
    Object.defineProperty(radioArrow, 'target', { value: input });
    view.handleKeyDown(radioArrow);
    expect(radioArrow.defaultPrevented).toBe(false);
    expect(pan).not.toHaveBeenCalled();

    const textInput = document.createElement('input');
    document.body.append(textInput);
    const inputZoom = new KeyboardEvent('keydown', { key: '+', cancelable: true });
    Object.defineProperty(inputZoom, 'target', { value: textInput });
    view.handleKeyDown(inputZoom);
    expect(inputZoom.defaultPrevented).toBe(false);

    const canvasArrow = new KeyboardEvent('keydown', { key: 'ArrowDown', cancelable: true });
    Object.defineProperty(canvasArrow, 'target', { value: canvas });
    view.handleKeyDown(canvasArrow);
    expect(canvasArrow.defaultPrevented).toBe(true);
    expect(pan).toHaveBeenCalledWith('down');
  });

  it('does not open a tag menu for a cancelled pointer gesture', () => {
    const { view, canvas } = setupCanvas();
    view.width = 900;
    view.viewHeight = 700;
    view.rows = [
      { y: 0, height: 60, items: [{ tag: { tag: 'tap', url: '/tag/tap' }, x: 0, width: 100 }] },
    ];
    const tag = view.rows[0].items[0].tag;
    view.hit = vi.fn(() => tag);
    view.showMenu = vi.fn();
    canvas.setPointerCapture = vi.fn();
    const down = new Event('pointerdown');
    Object.assign(down, { button: 0, pointerId: 1, clientX: 20, clientY: 20 });
    view.pointerDown(down);
    const cancel = new Event('pointercancel');
    Object.assign(cancel, { pointerId: 1, clientX: 20, clientY: 20, pointerType: 'touch' });
    view.pointerUp(cancel);
    expect(view.hit).not.toHaveBeenCalled();
    expect(view.showMenu).not.toHaveBeenCalled();
  });
});

describe('tag canvas spatial loading', () => {
  it('fills the viewport in every direction at minimum zoom and stops fetching once covered', async () => {
    const { view, context } = setupCanvas();
    view.zoom = 0.2;
    view.x = 350;
    view.y = 280;
    vi.mocked(fetch).mockImplementation(async (url) => {
      const offset = Number(new URL(url, 'https://example.com').searchParams.get('offset'));
      return {
        ok: true,
        json: async () => ({
          total: 20000,
          tags: Array.from({ length: 250 }, (_, i) => ({ tag: `tag-${offset + i}`, count: 1 })),
        }),
      };
    });

    await view.loadMore();
    await vi.waitFor(() => expect(view.loading).toBe(false));

    expect(view.tags.length).toBeGreaterThan(250);
    expect(view.tags.length).toBeLessThan(view.total);
    expect(view.visibleTiles().every(({ key }) => view.tiles.get(key)?.complete)).toBe(true);
    view.draw();
    const positions = context.fillText.mock.calls.map(([, x, y]) => [x, y]);
    expect(positions.some(([x]) => x < 0)).toBe(true);
    expect(positions.some(([x]) => x > view.worldWidth)).toBe(true);
    expect(positions.some(([, y]) => y < 0)).toBe(true);
    const requests = fetch.mock.calls.length;
    view.maybeLoad();
    expect(fetch).toHaveBeenCalledTimes(requests);
  });

  it('keeps existing tags in place as zooming out reveals tags around them', () => {
    const { view } = setupCanvas();
    view.tags = Array.from({ length: 5000 }, (_, i) => ({ tag: `tag-${i}`, count: 1 }));
    view.total = view.tags.length;
    view.layout();
    const original = view.rows.flatMap((row) =>
      row.items.map((item) => ({
        tag: item.tag,
        x: item.x,
        y: row.y,
      }))
    );
    const laidOut = view.laidOut;

    view.zoomAt(0.5);

    expect(view.laidOut).toBeGreaterThan(laidOut);
    for (const position of original) {
      const row = view.rows.find((row) => row.items.some((item) => item.tag === position.tag));
      const item = row.items.find((item) => item.tag === position.tag);
      expect({ x: item.x, y: row.y }).toEqual({ x: position.x, y: position.y });
    }
    const row = view.rows.find((row) => row.y < 0 && row.items.some((item) => item.x < 0));
    const item = row.items.find((item) => item.x < 0);
    expect(
      view.hit(
        view.x + (item.x + item.width / 2) * view.zoom,
        view.y + (row.y + row.height / 2) * view.zoom
      )
    ).toBe(item.tag);
  });

  it.each(['left', 'right', 'up', 'down'])(
    'loads more tags when panning %s beyond loaded tiles',
    (direction) => {
      const { view } = setupCanvas();
      for (const tile of view.visibleTiles()) view.tiles.set(tile.key, { complete: true });
      view.total = 20000;
      view.loadMore = vi.fn();
      for (let i = 0; i < 15; i++) view.pan(direction);
      expect(view.loadMore).toHaveBeenCalled();
    }
  );

  it('stops loading when the server returns no more tags', async () => {
    const { view } = setupCanvas();
    await view.loadMore();
    view.zoomAt(0.2);
    view.pan('left');
    expect(view.exhausted).toBe(true);
    expect(fetch).toHaveBeenCalledOnce();
  });
});
