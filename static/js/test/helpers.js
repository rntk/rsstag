export function createEventSystem() {
  const bindings = new Map();
  const calls = [];

  return {
    bindings,
    calls,
    POSTS_UPDATED: 'posts_updated',
    CHANGE_POSTS_STATUS: 'change_posts_status',
    CHANGE_POSTS_CONTENT_STATE: 'change_posts_content_state',
    SHOW_POST_LINKS: 'show_post_links',
    SET_CURRENT_POST: 'set_current_post',
    POSTS_RENDERED: 'posts_rendered',
    LOAD_MORE_POSTS: 'load_more_posts',
    CONTEXT_FILTER_UPDATED: 'context_filter_updated',
    CONTEXT_FILTER_ADD_TAG: 'context_filter_add_tag',
    CONTEXT_FILTER_REMOVE_TAG: 'context_filter_remove_tag',
    CONTEXT_FILTER_CLEAR: 'context_filter_clear',
    START_TASK: 'start_task',
    END_TASK: 'end_task',
    trigger(event, payload) {
      calls.push({ event, payload });
      const handlers = bindings.get(event) || [];
      handlers.forEach((handler) => handler(payload));
    },
    bind(event, handler) {
      const handlers = bindings.get(event) || [];
      handlers.push(handler);
      bindings.set(event, handlers);
    },
    unbind(event, handler) {
      const handlers = bindings.get(event) || [];
      bindings.set(
        event,
        handlers.filter((current) => current !== handler)
      );
    },
  };
}

export function createPost(id, overrides = {}) {
  return {
    pos: String(id),
    category_title: 'Category',
    feed_title: 'Feed',
    showed: false,
    current: false,
    post: {
      read: false,
      date: '2026-03-08',
      url: 'http://example.com/post',
      lemmas: '',
      content: {
        title: 'Title',
        content: '<p>content</p>',
      },
      ...overrides.post,
    },
    ...overrides,
  };
}

export async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}
