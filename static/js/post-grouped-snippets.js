// Post Grouped Snippets functionality

function toggleRead(postId, sentenceIndices, currentlyRead) {
    const newState = !currentlyRead;
    const indicesStr = Array.isArray(sentenceIndices) ? sentenceIndices.join('_') : sentenceIndices;

    // We need to mark each sentence as read.
    // The current API /read/snippet only supports one sentence at a time (presumably)
    // Let's check on_read_snippet_post in posts.py

    const promises = (Array.isArray(sentenceIndices) ? sentenceIndices : [sentenceIndices]).map(idx => {
        const data = {
            post_id: postId,
            sentence_index: idx,
            readed: newState
        };
        return fetch('/read/snippet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        }).then(response => response.json());
    });

    Promise.all(promises)
        .then(results => {
            const allOk = results.every(result => result.data === 'ok');
            if (allOk) {
                const snippetEl = document.getElementById(`snippet_${postId}_${indicesStr}`);
                if (snippetEl) {
                    if (newState) {
                        snippetEl.classList.add('read');
                    } else {
                        snippetEl.classList.remove('read');
                    }

                    // Update btn
                    const btn = snippetEl.querySelector('.toggle-read-btn');
                    if (btn) {
                        btn.textContent = newState ? 'Mark Unread' : 'Mark Read';
                        btn.style.background = newState ? '#eee' : '#c8e6c9';
                        btn.style.color = newState ? '#666' : '#2e7d32';
                        btn.title = newState ? 'Mark as unread' : 'Mark as read';
                        btn.onclick = () => toggleRead(postId, sentenceIndices, newState);
                    }
                }
            } else {
                alert('Error updating status for some sentences');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to update snippet status');
        });
}
