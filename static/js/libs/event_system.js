'use strict';
export default class EventsSystem {
    constructor(MicroEvent) {
        if (MicroEvent) {
            MicroEvent.mixin(this);
        } else {
            throw Error('I need MicroEvents');
        }
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
        this.CHANGE_TAG_SIBLINGS_STATE = 'change_tag_siblings_state';
    }   
};