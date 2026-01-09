// Topics List functionality

function togglePosts(index) {
    const postsElement = document.getElementById('posts_' + index);
    const button = event.target;

    if (postsElement.style.display === 'none') {
        postsElement.style.display = 'block';
        button.textContent = button.textContent.replace('[', '[-');
    } else {
        postsElement.style.display = 'none';
        button.textContent = button.textContent.replace('[-', '[');
    }
}
