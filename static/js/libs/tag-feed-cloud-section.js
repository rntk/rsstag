/** Load and fold the feed cloud using the same markup as its standalone page. */
export function initTagFeedCloudSection(doc = globalThis.document, fetchData = globalThis.fetch) {
  const button = doc.getElementById('load_tag_feeds');
  const block = doc.getElementById('tag_feeds_cloud');
  const error = doc.getElementById('tag_feeds_error');
  if (!button || !block || !error) {
    return;
  }

  button.addEventListener('click', async () => {
    if (button.disabled) {
      return;
    }
    if (button.getAttribute('aria-expanded') === 'true') {
      block.replaceChildren();
      button.setAttribute('aria-expanded', 'false');
      button.classList.remove('tag-info-control--active');
      button.textContent = 'Load feeds / sources';
      return;
    }

    button.disabled = true;
    button.textContent = 'Loading feeds / sources…';
    error.textContent = '';
    try {
      const response = await fetchData(button.dataset.url, {
        credentials: 'include',
        headers: { Accept: 'text/html' },
      });
      if (!response.ok || response.redirected) {
        throw new Error('Unable to load feeds / sources');
      }
      block.innerHTML = await response.text();
      button.setAttribute('aria-expanded', 'true');
      button.classList.add('tag-info-control--active');
      button.textContent = 'Hide feeds / sources';
    } catch {
      error.textContent = 'Unable to load feeds / sources. Try again.';
      button.textContent = 'Load feeds / sources';
    } finally {
      button.disabled = false;
    }
  });
}
