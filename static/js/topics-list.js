// Topics List functionality

function togglePosts(index, event) {
    const postsElement = document.getElementById('posts_' + index);
    const button = event ? event.currentTarget : (window.event ? window.event.target : null);

    if (!postsElement) return;

    if (postsElement.style.display === 'none') {
        postsElement.style.display = 'block';
        if (button) {
            button.textContent = button.textContent.replace('[', '[-');
        }
    } else {
        postsElement.style.display = 'none';
        if (button) {
            button.textContent = button.textContent.replace('[-', '[');
        }
    }
}
