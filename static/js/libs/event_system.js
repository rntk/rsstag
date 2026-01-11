'use strict';
/*
Based on MicroEvent library from https://github.com/jeromeetienne/microevent.js
*/
export default class EventsSystem {
  constructor() {
    this.POSTS_UPDATED = 'posts_updated';
    this.CHANGE_POSTS_STATUS = 'change_post_status';
    this.CHANGE_POSTS_CONTENT_STATE = 'change_post_content_state';
    this.SHOW_POST_LINKS = 'show_post_links';
    this.POSTS_ERROR_MESSAGE = 'posts_error_message';

    this.SETTINGS_UPDATED = 'settings_updated';
    this.UPDATE_SETTINGS = 'update_settings';
    this.SETTINGS_ERROR_MESSSAGE = 'settings_error_message';

    this.CHANGE_SETTINGS_WINDOW_STATE = 'change_settings_window_state';

    this.TAGS_ERROR_MESSAGE = 'tags_error_message';
    this.TAGS_UPDATED = 'tags_updated';
    this.CHANGE_TAGS_LOAD_BUTTON_STATE = 'change_tags_load_button_state';

    this.CHANGE_PROGRESSBAR = 'change_pprogressbar';
    this.PROGRESSBAR_ANIMATION_END = 'progressbar_animation_end';

    this.START_TASK = 'start_task';
    this.END_TASK = 'end_task';

    this.MAP_UPDATED = 'map_updated';
    this.CHANGE_MAP_OBJECTS_VISIBILITY = 'change_map_objects_visibility';

    this.TAGS_NET_UPDATED = 'tags_net_updated';
    this.LOAD_TAG_NET = 'load_tag_net';
    this.NET_TAG_CHANGE = 'net_tag_change';
    this.NET_TAG_SELECTED = 'net_tag_selected';

    this.SET_CURRENT_POST = 'set_current_post';

    this.POSTS_RENDERED = 'posts_rendered';

    this.TAG_MENTIONS_UPDATED = 'tag_mentions_updated';
    this.TAG_TOPICS_UPDATED = 'tag_topics_updated';

    this.WORDTREE_TEXTS_UPDATED = 'wordtree_texts_updated';

    this.BIGRAMS_MENTIONS_UPDATED = 'bigrams_mentions_updated';

    this.TOPICS_TEXTS_UPDATED = 'topics_texts_updated';

    this.TAGS_CLUSTERS_UPDATED = 'tag_clusters_updated';

    this.SAVE_TELEGRAM_CODE = 'save_telegram_code';
    this.SAVE_TELEGRAM_PASSWORD = 'save_telegram_password';

    this.OPENAI_GET_RESPONSE = 'openai_get_response';
    this.OPENAI_GOT_RESPONSE = 'openai_got_response';

    this.LOAD_MORE_POSTS = 'load_more_posts';

    this.CONTEXT_FILTER_UPDATED = 'context_filter_updated';
    this.CONTEXT_FILTER_ADD_TAG = 'context_filter_add_tag';
    this.CONTEXT_FILTER_REMOVE_TAG = 'context_filter_remove_tag';
    this.CONTEXT_FILTER_CLEAR = 'context_filter_clear';
    this.CLUSTERS_TOPICS_UPDATED = 'clusters_topics_updated';
    this.FETCH_CLUSTERS_TOPICS_SENTENCES = 'fetch_clusters_topics_sentences';
    this.CLUSTERS_TOPICS_CHANGE_STATUS = 'clusters_topics_change_status';

    this._events = {};
  }

  bind(event, fct) {
    this._events = this._events || {};
    this._events[event] = this._events[event] || [];
    this._events[event].push(fct);
  }

  unbind(event, fct) {
    this._events = this._events || {};
    if (event in this._events === false) {
      return;
    }
    this._events[event].splice(this._events[event].indexOf(fct), 1);
  }

  trigger(event /* , args... */) {
    this._events = this._events || {};
    if (event in this._events === false) return;
    for (var i = 0; i < this._events[event].length; i++) {
      this._events[event][i].apply(undefined, Array.prototype.slice.call(arguments, 1));
    }
  }
}
