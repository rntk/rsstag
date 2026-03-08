// Post Grouped Snippets functionality

const tagsCache = {};

document.addEventListener('click', (event) => {
  // Show tags button
  const showTagsBtn = event.target.closest('.show-snippet-tags-btn');
  if (showTagsBtn) {
    const postId = showTagsBtn.dataset.postId;
    const snippetItem = showTagsBtn.closest('.snippet-item');
    const tagsContent = snippetItem.querySelector('.snippet-tags-content');

    if (!tagsContent.classList.contains('hide')) {
      tagsContent.classList.add('hide');
      return;
    }

    const snippetTextEl = snippetItem.querySelector('.snippet-text');
    const snippetText = snippetTextEl.textContent || snippetTextEl.innerText;

    const renderTags = (tags) => {
      tagsContent.textContent = '';
      if (!tags.length) {
        const empty = document.createElement('span');
        empty.className = 'post_tag_letter';
        empty.textContent = 'No matching tags';
        tagsContent.appendChild(empty);
      } else {
        tags.sort((a, b) => a.tag.localeCompare(b.tag));
        const grouped = {};
        tags.forEach((tag) => {
          const letter = tag.tag.charAt(0);
          if (!(letter in grouped)) grouped[letter] = [];
          grouped[letter].push(tag);
        });
        Object.keys(grouped)
          .sort()
          .forEach((letter) => {
            const block = document.createElement('div');
            block.className = 'post_tag_letter_block';
            const letterSpan = document.createElement('span');
            letterSpan.className = 'post_tag_letter';
            letterSpan.textContent = letter;
            block.appendChild(letterSpan);
            grouped[letter].forEach((tag) => {
              const a = document.createElement('a');
              a.href = tag.url;
              a.className = 'post_tag_link';
              a.textContent = ' ' + tag.tag;
              block.appendChild(a);
            });
            tagsContent.appendChild(block);
          });
      }
      tagsContent.classList.remove('hide');
    };

    if (tagsCache[postId]) {
      renderTags(tagsCache[postId]);
    } else {
      tagsContent.textContent = 'Loading...';
      tagsContent.classList.remove('hide');
      fetch(`/post-snippet-tags/${postId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: snippetText }),
      })
        .then((r) => r.json())
        .then((data) => {
          const tags = (data.data && data.data.tags) || [];
          tagsCache[postId] = tags;
          renderTags(tags);
        })
        .catch((err) => {
          console.error(err);
          tagsContent.textContent = 'Failed to load tags';
          tagsContent.classList.remove('hide');
        });
    }
    return;
  }

  // Individual toggle
  const toggleBtn = event.target.closest('.toggle-read-btn');
  if (toggleBtn) {
    const postId = toggleBtn.dataset.postId;
    const indices = toggleBtn.dataset.indices
      ? toggleBtn.dataset.indices.split(',').filter(Boolean).map(Number)
      : [];
    const currentlyRead = toggleBtn.dataset.read === '1';

    const selections = [
      {
        post_id: postId,
        sentence_indices: indices,
      },
    ];

    changeSnippetsStatus(selections, !currentlyRead)
      .then((payload) => {
        if (payload && payload.data === 'ok') {
          updateUIForSelections(selections, !currentlyRead);
        } else {
          alert('Failed to update status');
        }
      })
      .catch((err) => {
        console.error(err);
        alert('Failed to update status');
      });
    return;
  }

  // Batch tools
  const batchBtn = event.target.closest('.batch-read-btn');
  if (batchBtn) {
    const action = batchBtn.dataset.action;
    const readed = action === 'read-all';
    const selections = getAllDisplayedSelections();

    if (!selections.length) return;

    changeSnippetsStatus(selections, readed)
      .then((payload) => {
        if (payload && payload.data === 'ok') {
          updateUIForSelections(selections, readed);
        } else {
          alert('Failed to update status');
        }
      })
      .catch((err) => {
        console.error(err);
        alert('Failed to update status');
      });
  }
});

function getAllDisplayedSelections() {
  const selections = [];
  const elements = document.querySelectorAll('.toggle-read-btn');
  elements.forEach((el) => {
    const postId = el.dataset.postId;
    const indices = el.dataset.indices
      ? el.dataset.indices.split(',').filter(Boolean).map(Number)
      : [];
    if (postId && indices.length) {
      selections.push({
        post_id: postId,
        sentence_indices: indices,
      });
    }
  });
  return selections;
}

function changeSnippetsStatus(selections, readed) {
  if (!selections || !selections.length) {
    return Promise.resolve();
  }

  return fetch('/read/snippets', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      selections: selections,
      readed: readed,
    }),
  }).then((response) => response.json());
}

function updateUIForSelections(selections, readed) {
  selections.forEach((sel) => {
    const indicesStr = sel.sentence_indices.join('_');
    const snippetEl = document.getElementById(`snippet_${sel.post_id}_${indicesStr}`);
    if (snippetEl) {
      if (readed) {
        snippetEl.classList.add('read');
      } else {
        snippetEl.classList.remove('read');
      }

      const btn = snippetEl.querySelector('.toggle-read-btn');
      if (btn) {
        btn.textContent = readed ? 'Mark Unread' : 'Mark Read';
        btn.classList.toggle('snippet-tag-read', readed);
        btn.classList.toggle('snippet-tag-unread', !readed);
        // Remove inline styles if they were set by old JS, otherwise rely on CSS classes
        btn.style.background = '';
        btn.style.color = '';
        btn.title = readed ? 'Mark as unread' : 'Mark as read';
        btn.dataset.read = readed ? '1' : '0';
      }
    }
  });
}
