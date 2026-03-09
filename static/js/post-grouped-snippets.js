// Post Grouped Snippets functionality

const tagsCache = {};
const CONTEXT_STEP = 1;

function parseIndices(value) {
  if (!value) {
    return [];
  }

  const parts = Array.isArray(value) ? value : String(value).split(',');
  return parts
    .map((item) => Number.parseInt(String(item).trim(), 10))
    .filter((item) => Number.isInteger(item));
}

function buildSnippetSegmentMarkup(segment, className) {
  if (!segment || !segment.html) {
    return '';
  }

  return `<span class="snippet-context ${className}">${segment.html}</span>`;
}

function updateExtendContextButton(button, contextData) {
  const canExtend =
    Boolean(contextData && contextData.can_extend_before) ||
    Boolean(contextData && contextData.can_extend_after);

  button.disabled = !canExtend;
  button.textContent = canExtend ? 'Extend context' : 'Full context shown';
  button.title = canExtend
    ? 'Load more adjacent sentences from this post'
    : 'All available adjacent sentences are already shown';
}

function renderExpandedSnippet(snippetItem, contextData) {
  const snippetText = snippetItem.querySelector('.snippet-text');
  if (!snippetText || !contextData || !contextData.base) {
    return;
  }

  snippetText.innerHTML = [
    buildSnippetSegmentMarkup(contextData.before, 'snippet-context-before'),
    buildSnippetSegmentMarkup(contextData.base, 'snippet-context-base'),
    buildSnippetSegmentMarkup(contextData.after, 'snippet-context-after'),
  ]
    .filter(Boolean)
    .join(' ');

  snippetItem.dataset.visibleIndices = (contextData.visible_indices || []).join(',');
  snippetItem.dataset.canExtendBefore = contextData.can_extend_before ? '1' : '0';
  snippetItem.dataset.canExtendAfter = contextData.can_extend_after ? '1' : '0';

  const visibleIndicesLabel = snippetItem.querySelector('.snippet-visible-indices');
  if (visibleIndicesLabel) {
    visibleIndicesLabel.textContent = (contextData.visible_indices || []).join(', ');
  }

  const button = snippetItem.querySelector('.extend-snippet-context-btn');
  if (button) {
    updateExtendContextButton(button, contextData);
  }
}

function loadSnippetContext(postId, baseIndices, visibleIndices) {
  return fetch(`/post-snippet-context/${postId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      base_indices: baseIndices,
      visible_indices: visibleIndices,
      step: CONTEXT_STEP,
    }),
  }).then((response) => response.json());
}

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

  const extendBtn = event.target.closest('.extend-snippet-context-btn');
  if (extendBtn) {
    const snippetItem = extendBtn.closest('.snippet-item');
    if (!snippetItem || extendBtn.disabled) {
      return;
    }

    const postId = snippetItem.dataset.postId || extendBtn.dataset.postId;
    const baseIndices = parseIndices(snippetItem.dataset.baseIndices);
    const visibleIndices = parseIndices(snippetItem.dataset.visibleIndices);
    if (!postId || !baseIndices.length) {
      return;
    }

    extendBtn.disabled = true;
    extendBtn.textContent = 'Loading...';

    loadSnippetContext(postId, baseIndices, visibleIndices.length ? visibleIndices : baseIndices)
      .then((payload) => {
        if (payload && payload.data) {
          renderExpandedSnippet(snippetItem, payload.data);
        } else {
          throw new Error('Missing snippet context payload');
        }
      })
      .catch((err) => {
        console.error(err);
        alert('Failed to load more context');
        updateExtendContextButton(extendBtn, {
          can_extend_before: snippetItem.dataset.canExtendBefore !== '0',
          can_extend_after: snippetItem.dataset.canExtendAfter !== '0',
        });
      });
    return;
  }

  // Individual toggle
  const toggleBtn = event.target.closest('.toggle-read-btn');
  if (toggleBtn) {
    const postId = toggleBtn.dataset.postId;
    const indices = parseIndices(toggleBtn.dataset.indices);
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
    const indices = parseIndices(el.dataset.indices);
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
