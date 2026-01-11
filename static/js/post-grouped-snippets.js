// Post Grouped Snippets functionality

document.addEventListener('click', (event) => {
    // Individual toggle
    const toggleBtn = event.target.closest('.toggle-read-btn');
    if (toggleBtn) {
        const postId = toggleBtn.dataset.postId;
        const indices = toggleBtn.dataset.indices
            ? toggleBtn.dataset.indices.split(',').filter(Boolean).map(Number)
            : [];
        const currentlyRead = toggleBtn.dataset.read === '1';

        const selections = [{
            post_id: postId,
            sentence_indices: indices
        }];

        changeSnippetsStatus(selections, !currentlyRead).then(payload => {
            if (payload && payload.data === 'ok') {
                updateUIForSelections(selections, !currentlyRead);
            } else {
                alert('Failed to update status');
            }
        }).catch(err => {
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

        changeSnippetsStatus(selections, readed).then(payload => {
            if (payload && payload.data === 'ok') {
                updateUIForSelections(selections, readed);
            } else {
                alert('Failed to update status');
            }
        }).catch(err => {
            console.error(err);
            alert('Failed to update status');
        });
    }
});

function getAllDisplayedSelections() {
    const selections = [];
    const elements = document.querySelectorAll('.toggle-read-btn');
    elements.forEach(el => {
        const postId = el.dataset.postId;
        const indices = el.dataset.indices
            ? el.dataset.indices.split(',').filter(Boolean).map(Number)
            : [];
        if (postId && indices.length) {
            selections.push({
                post_id: postId,
                sentence_indices: indices
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
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            selections: selections,
            readed: readed
        })
    }).then(response => response.json());
}

function updateUIForSelections(selections, readed) {
    selections.forEach(sel => {
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
