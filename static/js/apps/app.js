'use strict';
import 'babel-polyfill';
import React from 'react';
import ReactDOM from 'react-dom';
import PostsStorage from '../storages/posts-storage.js';
import PostsList from '../components/posts-list.js';
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
import PostsNumbers from '../components/posts-numbers.js';
import BiGramsStorage from '../storages/bi-grams-storage.js';
import TagButton from '../components/tag-button.js';


window.onload = () => {
    if (window.EVSYS === undefined) {
        window.EVSYS = new EventsSystem();
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
    } else if (/\/group\/bi-gram\/.*/.test(path)) {
        const bi_grams_storage = new BiGramsStorage(window.EVSYS);
        ReactDOM.render(
            <TagsList ES={window.EVSYS} />,
            document.getElementById('tags_page')
        );
        bi_grams_storage.start();
    } else if ( /^\/feed*/.test(path) || /^\/category*/.test(path) ||
            /^\/tag\/.*/.test(path) || /^\/posts\/with\/tags\/.*/.test(path) || /^\/bi-gram\/.*/.test(path)) {
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
        ReactDOM.render(
            <PostsNumbers ES={window.EVSYS} />,
            document.getElementById('posts_stat')
        );
        posts_storage.start();
    } else if (/\/tag-info\/.*/.test(path)) {
        let tag = window.initial_tag;

        const similar_evsys = new EventsSystem();
        const similar_storage = new TagsStorage(similar_evsys, '/tag-similar');
        ReactDOM.render(
            <TagsList ES={similar_evsys} />,
            document.getElementById('similar_tags')
        );
        ReactDOM.render(
            <TagButton ES={similar_evsys} title="Load similar" tag={tag} />,
            document.getElementById('load_similar')
        );
        similar_storage.start();

        const siblings_evsys = new EventsSystem();
        const siblings_storage = new TagsStorage(siblings_evsys, '/tag-siblings');
        ReactDOM.render(
            <TagsList ES={siblings_evsys} />,
            document.getElementById('siblings_tags')
        );
        ReactDOM.render(
            <TagButton ES={siblings_evsys} title="Load siblings" tag={tag} />,
            document.getElementById('load_siblings')
        );
        siblings_storage.start();

        const bi_grams_evsys = new EventsSystem();
        const bi_grams_storage = new TagsStorage(bi_grams_evsys, '/tag-bi-grams');
        ReactDOM.render(
            <TagsList ES={bi_grams_evsys} />,
            document.getElementById('bi_grams')
        );
        ReactDOM.render(
            <TagButton ES={bi_grams_evsys} title="Load bi-grams" tag={tag} />,
            document.getElementById('load_bi_grams')
        );
        bi_grams_storage.start();
    }
}