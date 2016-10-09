'use strict';
import 'babel-polyfill';
import React from 'react';
import ReactDOM from 'react-dom';
import PostsStorage from '../storages/posts-storage.js';
import PostsList from '../components/posts-list.js';
import MicroEvent from '../libs/microevent_mod.js';
import EventsSystem from '../libs/event_system.js';
import SettingsMenu from '../components/settings-menu.js';
import ReadAllButton from '../components/readall-button.js';
import ShowAllButton from '../components/showall-button.js';
import SettingsStorage from '../storages/settings-storage.js';
import TagsStorage from '../storages/tags-storage.js';
import TagsList from '../components/tags-list.js';
import LettersList from '../components/letters-list.js';
import SearchInput from '../components/search-input.js';
import CategoriesList from '../components/categories-list.js';


window.onload = () => {
    if (window.EVSYS === undefined) {
        window.EVSYS = new EventsSystem(MicroEvent);
    }
    ReactDOM.render(
        <SettingsMenu ES={window.EVSYS} />,
        document.getElementById('settings_menu')
    );
    const settings_storage = new SettingsStorage(window.EVSYS);
    settings_storage.start();
    let path = document.location.pathname;
    if (path === '/') {
        ;
    } else if (path === '\/group\/category') {
        ReactDOM.render(
            <CategoriesList ES={window.EVSYS} />,
            document.getElementById('cats_list')
        );
    } else if (/\/group\/(tag|hottag)\/.*/.test(path)) {
        const tags_storage = new TagsStorage(window.EVSYS);
        ReactDOM.render(
            <TagsList ES={window.EVSYS} />,
            document.getElementById('tags_page')
        );
        ReactDOM.render(
            <LettersList ES={window.EVSYS} />,
            document.getElementById('letters_list')
        );
        ReactDOM.render(
            <SearchInput ES={window.EVSYS} />,
            document.getElementById('search_tools')
        );
        tags_storage.start();

    } else if (/^\/feed*/.test(path) || /^\/category*/.test(path) || /^\/tag/.test(path) || /^\/posts\/with\/tags\/.*/.test(path)) {
        const posts_storage = new PostsStorage(window.EVSYS);
        ReactDOM.render(
            <PostsList ES={window.EVSYS} />,
            document.getElementById('posts_page')
        );
        ReactDOM.render(
            <ReadAllButton ES={window.EVSYS} />,
            document.getElementById('read_all')
        );
        ReactDOM.render(
            <ShowAllButton ES={window.EVSYS} />,
            document.getElementById('show_all')
        );
        posts_storage.start();
    }
}