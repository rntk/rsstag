// Utility for the /tag-info/<tag> page: hides analysis sections that resolve
// to "nothing to show" and collapses on-demand (not-yet-loaded) sections into
// a compact row instead of a tall bordered card.

const CONTENT_SELECTOR = 'img,svg,canvas,ol,ul,table,button,a,input,select,textarea,iframe';

/**
 * Compute the display state for a tag-info section content block.
 * @param {Element} block
 * @returns {'hidden'|'unloaded'|'loaded'}
 */
export function computeSectionState(block) {
  const hasEmptyMarker = block.querySelector('.tag-info-empty-state') !== null;

  const clone = block.cloneNode(true);
  clone.querySelectorAll('.tag-info-empty-state').forEach((el) => el.remove());
  const hasRealContent =
    clone.textContent.trim() !== '' || clone.querySelector(CONTENT_SELECTOR) !== null;

  if (hasEmptyMarker && !hasRealContent) {
    return 'hidden';
  }
  if (!hasEmptyMarker && !hasRealContent) {
    return 'unloaded';
  }
  return 'loaded';
}

/**
 * Wire up empty-state handling for all tag-info sections on the page.
 * No-op when there are no `.tag-info-page` sections.
 */
export function initTagInfoEmptySections() {
  const sections = document.querySelectorAll('.tag-info-page .tag-info-section');
  if (!sections.length) {
    return;
  }

  sections.forEach((section) => {
    const block = section.querySelector('.tag_info_block, .openai_info_block');
    if (!block) {
      return;
    }

    const update = () => {
      const state = computeSectionState(block);
      if (state === 'hidden') {
        section.hidden = true;
        section.classList.remove('tag-info-section--unloaded');
      } else {
        section.hidden = false;
        section.classList.toggle('tag-info-section--unloaded', state === 'unloaded');
      }
    };

    update();

    let scheduled = false;
    const scheduleUpdate = () => {
      if (typeof requestAnimationFrame !== 'function') {
        update();
        return;
      }
      if (scheduled) {
        return;
      }
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        update();
      });
    };

    const observer = new MutationObserver(scheduleUpdate);
    observer.observe(block, { childList: true, subtree: true, characterData: true });
  });
}
