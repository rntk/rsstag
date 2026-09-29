/** Open complete topic sentences and persist their shared read state. */
export function initConcordance(root = globalThis.document, request = globalThis.fetch) {
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
      if (element.matches('button')) element.disabled = true;
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
        if (element.matches('button')) {
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
        if (element.matches('button')) element.disabled = false;
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
