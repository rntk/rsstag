const WORD_CLASS = 'tag-context-wall__word';
const WORD_HIGHLIGHT_CLASS = 'is-word-match';

/** Normalize a context word, ignoring case and surrounding punctuation. */
function wordKey(element) {
  return element.textContent.match(/[\p{L}\p{N}_]+/u)?.[0].toLowerCase() ?? '';
}

/** Highlight every occurrence of the hovered word across all wall rows. */
function initWordHighlight(viewport) {
  const index = new Map();
  viewport.querySelectorAll(`.${WORD_CLASS}`).forEach((element) => {
    const key = wordKey(element);
    if (key) index.set(key, [...(index.get(key) ?? []), element]);
  });
  let active = [];
  function highlight(elements) {
    active.forEach((element) => element.classList.remove(WORD_HIGHLIGHT_CLASS));
    active = elements;
    active.forEach((element) => element.classList.add(WORD_HIGHLIGHT_CLASS));
  }
  viewport.addEventListener('mouseover', (event) => {
    const word = event.target.closest?.(`.${WORD_CLASS}`);
    highlight(word ? (index.get(wordKey(word)) ?? []) : []);
  });
  viewport.addEventListener('mouseleave', () => highlight([]));
}

/** Open a context wall with its matching tag centered in the scroll viewport. */
export function initContextWall(root = globalThis.document) {
  const viewport = root.querySelector('.tag-context-wall__scroll');
  const match = viewport?.querySelector('.tag-context-wall__match');
  if (!match) return;
  initWordHighlight(viewport);
  function centerTag() {
    const target = match.getBoundingClientRect();
    const bounds = viewport.getBoundingClientRect();
    const left = viewport.scrollLeft + target.left - bounds.left - viewport.clientLeft;
    viewport.scrollLeft = Math.max(
      0,
      Math.min(
        left + target.width / 2 - viewport.clientWidth / 2,
        viewport.scrollWidth - viewport.clientWidth
      )
    );
  }
  const fonts = viewport.ownerDocument.fonts;
  if (fonts?.status === 'loading') void fonts.ready.then(centerTag);
  else centerTag();
}

/**
 * Apply server-prepared strategies through the same renderer for every mode.
 * @param {Document|HTMLElement} root
 */
export function initColoring(root = globalThis.document) {
  const selector = root.querySelector('#wall-coloring-mode');
  const threshold = root.querySelector('#wall-coloring-threshold');
  const description = root.querySelector('#wall-coloring-description');
  const control = root.querySelector('.tag-context-wall__threshold');
  const wall = root.querySelector('.tag-context-wall');
  if (!selector || !threshold || !description || !control || !wall) return;
  const prefix = 'tag-context-wall__color-';
  const words = [...wall.querySelectorAll(`.${WORD_CLASS}[data-colorings]`)].map((element) => {
    try {
      return { element, results: JSON.parse(element.dataset.colorings) };
    } catch {
      return { element, results: {} };
    }
  });
  const cutoffs = new Map();
  function apply() {
    const option = selector.selectedOptions[0];
    if (!option) return;
    const scored = option.dataset.threshold !== undefined;
    control.hidden = !scored;
    const cutoff = scored ? (cutoffs.get(option.value) ?? Number(option.dataset.threshold)) : 0;
    if (scored) threshold.value = String(cutoff);
    description.textContent = option.dataset.description ?? '';
    words.forEach(({ element, results }) => {
      [...element.classList].filter((name) => name.startsWith(prefix)).forEach((name) => element.classList.remove(name));
      const result = results[option.value];
      if (result && result.score >= cutoff) element.classList.add(`${prefix}${result.color}`);
      if (scored && result) {
        const evidence = Number.isInteger(result.support)
          ? `; near the tag in ${result.support} articles`
          : '';
        const standardized = Number.isFinite(result.z_score)
          ? `; z-score: ${result.z_score.toFixed(3)}`
          : '';
        element.title = `${option.label} score: ${result.score.toFixed(3)}${standardized}${evidence}`;
      } else element.removeAttribute('title');
    });
  }
  selector.addEventListener('change', apply);
  threshold.addEventListener('input', () => {
    if (!threshold.value || !threshold.checkValidity()) return;
    cutoffs.set(selector.value, Number(threshold.value));
    apply();
  });
  apply();
}

/** Show only wall rows containing one of the words, or every row when empty. */
function filterRows(wall, words) {
  const wanted = new Set(words);
  wall.querySelectorAll('.tag-context-wall__line').forEach((line) => {
    const keys = [...line.querySelectorAll(`.${WORD_CLASS}`)].map(wordKey);
    line.classList.toggle(
      'is-filtered-out',
      wanted.size > 0 && !keys.some((key) => wanted.has(key))
    );
  });
}

/** Wire insight words to row filtering and the near-duplicate toggle. */
export function initInsights(root = globalThis.document) {
  const panel = root.querySelector('.tag-insights');
  const wall = root.querySelector('.tag-context-wall');
  if (!panel || !wall) return;
  const status = panel.querySelector('.tag-insights__filter');
  let active = null;
  function apply(chip) {
    active?.setAttribute('aria-pressed', 'false');
    active = chip;
    chip?.setAttribute('aria-pressed', 'true');
    const words = chip ? chip.dataset.filterWords.toLowerCase().split(' ').filter(Boolean) : [];
    filterRows(wall, words);
    status.hidden = !chip;
    status.querySelector('span').textContent = chip
      ? `Showing rows with “${chip.dataset.filterLabel}”.`
      : '';
  }
  panel.addEventListener('click', (event) => {
    const chip = event.target.closest('.tag-insights__term');
    if (chip) apply(chip === active ? null : chip);
    if (event.target.closest('.tag-insights__clear')) apply(null);
  });
  panel.querySelector('.tag-insights__show-duplicates')?.addEventListener('change', (event) => {
    wall.classList.toggle('show-duplicates', event.target.checked);
  });
}

/** Open complete topic sentences and persist their shared read state. */
export function initConcordance(root = globalThis.document, request = globalThis.fetch) {
  initContextWall(root);
  initColoring(root);
  initInsights(root);
  const data = root.querySelector('#concordance-details');
  const dialog = root.querySelector('#concordance-dialog');
  if (!data || !dialog) return;
  const details = JSON.parse(data.textContent);
  const doc = dialog.ownerDocument;
  const statuses = root.querySelectorAll('.tag-concordance__status');
  const pending = new Set();

  function readButton(pid, sentence) {
    const button = doc.createElement('button');
    button.type = 'button';
    button.className = 'tag-concordance__read';
    button.dataset.postId = pid;
    button.dataset.sentenceNumber = String(sentence.number);
    button.dataset.read = sentence.read ? '1' : '0';
    button.textContent = sentence.read ? 'Mark Unread' : 'Mark Read';
    button.disabled = pending.has(JSON.stringify([pid, sentence.number]));
    return button;
  }

  function openDetail(key) {
    const detail = details.entries?.[key];
    if (!detail) return;
    const post = details.posts[detail.pid];
    statuses.forEach((status) => {
      status.textContent = '';
    });
    const link = dialog.querySelector('.tag-concordance__article');
    link.textContent = post.title;
    link.href = post.url;
    const metadata = dialog.querySelector('.tag-concordance__metadata');
    if (metadata) {
      metadata.textContent = ['source', 'provider', 'category']
        .filter((key) => post.metadata?.[key])
        .map((key) => `${key[0].toUpperCase() + key.slice(1)}: ${post.metadata[key]}`)
        .join(' · ');
    }
    const body = dialog.querySelector('.tag-concordance__sentences');
    body.replaceChildren();
    const sections = detail.topics.length
      ? detail.topics.map((topic) => {
          const numbers = new Set(post.groups[topic]);
          return {
            topic,
            sentences: post.sentences.filter((sentence) => numbers.has(sentence.number)),
          };
        })
      : [{ topic: 'Matching sentence', sentences: [post.sentences[detail.sentence_index]] }];
    sections.forEach((section) => {
      const heading = doc.createElement('h3');
      heading.textContent = section.topic;
      body.appendChild(heading);
      const list = doc.createElement('ol');
      section.sentences.forEach((sentence) => {
        const item = doc.createElement('li');
        item.className = 'tag-concordance__sentence';
        item.classList.toggle('is-read', sentence.read);
        item.classList.toggle('is-match', sentence.number === detail.number);
        item.dataset.postId = detail.pid;
        item.dataset.sentenceNumber = String(sentence.number ?? '');
        const text = doc.createElement('p');
        text.textContent = sentence.text;
        item.appendChild(text);
        if (Number.isInteger(sentence.number)) item.appendChild(readButton(detail.pid, sentence));
        list.appendChild(item);
      });
      body.appendChild(list);
    });
    if (!dialog.open) dialog.showModal();
  }

  function matchingElements(pid, number) {
    return [...root.querySelectorAll('[data-post-id][data-sentence-number]')].filter(
      (element) =>
        element.dataset.postId === pid && element.dataset.sentenceNumber === String(number)
    );
  }

  async function toggleRead(button) {
    const pid = button.dataset.postId;
    const number = Number(button.dataset.sentenceNumber);
    const key = JSON.stringify([pid, number]);
    if (!pid || !Number.isInteger(number) || pending.has(key)) return;
    const readed = button.dataset.read !== '1';
    pending.add(key);
    matchingElements(pid, number).forEach((element) => {
      if (element.matches('.tag-concordance__read')) element.disabled = true;
    });
    statuses.forEach((status) => {
      status.textContent = '';
    });
    try {
      const response = await request('/read/snippets', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          readed,
          selections: [{ post_id: pid, sentence_indices: [number] }],
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.data !== 'ok')
        throw new Error('Could not update sentence status. Please try again.');
      details.posts[pid].sentences.forEach((sentence) => {
        if (sentence.number === number) sentence.read = readed;
      });
      matchingElements(pid, number).forEach((element) => {
        if (element.matches('.tag-concordance__read')) {
          element.dataset.read = readed ? '1' : '0';
          element.textContent = readed ? 'Mark Unread' : 'Mark Read';
        } else element.classList.toggle('is-read', readed);
      });
    } catch {
      statuses.forEach((status) => {
        status.textContent = 'Could not update sentence status. Please try again.';
      });
    } finally {
      pending.delete(key);
      matchingElements(pid, number).forEach((element) => {
        if (element.matches('.tag-concordance__read')) element.disabled = false;
      });
    }
  }

  root.addEventListener('click', (event) => {
    const context = event.target.closest('[data-detail-key]');
    if (context) openDetail(context.dataset.detailKey);
    const button = event.target.closest('.tag-concordance__read');
    if (button) void toggleRead(button);
    if (event.target.closest('.tag-concordance__close')) dialog.close();
    if (event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (
        event.clientX < rect.left ||
        event.clientX > rect.right ||
        event.clientY < rect.top ||
        event.clientY > rect.bottom
      )
        dialog.close();
    }
  });
}

if (typeof document !== 'undefined') initConcordance();
