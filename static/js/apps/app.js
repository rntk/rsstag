'use strict';
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
import ProgressBarStorage from '../storages/progressbar-storage.js';
import ProgressBar from '../components/progressbar.js';
import GeoTagsStorage from '../storages/geo-tags-storage.js';
import GeoMapTools from '../components/geomap-tools.js';
import RssTagYMap from '../components/rsstag-ymaps.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import TagsNetStorage from '../storages/tags-net-storage.js';
import TagsNet from '../components/tags-net.js';
import TagNetTools from '../components/tag-net-tools.js';
import GlobalStatus from '../components/global-status.js';
import TagMentionsStorage from '../storages/tag-mentions-storage.js';
import TagMentionsChart from '../components/tag-mentions-chart.js';
import WordTreeStorage from '../storages/wordtree-storage.js';
import WordTree from '../components/wordtree.js';
import PostsWordTree from '../components/posts-wordtree.js';
import TagContexts from '../components/tag-contexts.js';
import BiGramsMentionsStorage from '../storages/bigrams-mentions-storage.js';
import BiGramsMentionsChart from '../components/bigrams-mentions-chart.js';
import TopicsTextsStorage from '../storages/topics-texts-storage.js';
import TopicsTexts from '../components/topics-texts.js';

function handleScroll() {
    let $tools = document.querySelector('#global_tools');
    let $tools_bottom = document.querySelector('#global_tools_bottom');
    let scroll_position = window.scrollY;
    let t_out = 0;
    if ($tools || $tools_bottom) {
      window.addEventListener('scroll', e => {
          if (t_out) {
            clearTimeout(t_out);
          }
          if (scroll_position !== window.scrollY) {
            t_out = setTimeout(() => {
              let sc_t = window.scrollY;
              if (scroll_position > sc_t) {
                if ($tools) {
                  $tools.style.display = 'block';
                }
                if ($tools_bottom) {
                  $tools_bottom.style.display = 'block';
                }
              } else if (scroll_position < sc_t) {
                if ($tools) {
                  $tools.style.display = 'none';
                }
                if ($tools_bottom) {
                  $tools_bottom.style.display = 'none';
                }
              }
              scroll_position = window.scrollY;
            }, 150);
          }
      });
    }
}

window.onload = () => {
    if (window.EVSYS === undefined) {
        window.EVSYS = new EventsSystem();
    }
    handleScroll();
    ReactDOM.render(
        <SettingsMenu ES={window.EVSYS} />,
        document.getElementById('settings_menu')
    );
    const settings_storage = new SettingsStorage(window.EVSYS);
    settings_storage.start();

    ReactDOM.render(
        <ProgressBar ES={window.EVSYS} />,
        document.getElementById('progressbar')
    );
    const progressbar_storage = new ProgressBarStorage(window.EVSYS);
    progressbar_storage.start();

    let path = document.location.pathname;

    ReactDOM.render(
        <GlobalStatus/>,
        document.getElementById('global_status')
    )
    if (path === '/') {
        ;
    } else if (path === '/group/category') {
        ReactDOM.render(
            <CategoriesList ES={window.EVSYS} />,
            document.getElementById('cats_list')
        );
    } else if (
        (/\/group\/(tag|hottag)\/.*/.test(path)) || (/\/tags\/sentiment\/.*/.test(path)) ||
        (/\/tags\/group\/.*/.test(path))
    ) {
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
        const posts_wordtree = new PostsWordTree("#posts_wordtree", window.EVSYS)
        posts_wordtree.start();
        posts_storage.start();
    } else if (/\/tag-info\/.*/.test(path)) {
        let tag = window.initial_tag;

        const similar_d2v_evsys = new EventsSystem();
        const similar_d2v_storage = new TagsStorage(similar_d2v_evsys, '/tag-similar/d2v');
        ReactDOM.render(
            <TagsList ES={similar_d2v_evsys} />,
            document.getElementById('similar_d2v_tags')
        );
        ReactDOM.render(
            <TagButton ES={similar_d2v_evsys} title="Load similar" tag={tag} />,
            document.getElementById('load_similar_d2v')
        );
        similar_d2v_storage.start();

        const similar_w2v_evsys = new EventsSystem();
        const similar_w2v_storage = new TagsStorage(similar_w2v_evsys, '/tag-similar/w2v');
        ReactDOM.render(
            <TagsList ES={similar_w2v_evsys} />,
            document.getElementById('similar_w2v_tags')
        );
        ReactDOM.render(
            <TagButton ES={similar_w2v_evsys} title="Load similar" tag={tag} />,
            document.getElementById('load_similar_w2v')
        );
        similar_w2v_storage.start();

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
            <TagsList ES={bi_grams_evsys} is_bigram={true} />,
            document.getElementById('bi_grams')
        );
        ReactDOM.render(
            <TagButton ES={bi_grams_evsys} title="Load bi-grams" tag={tag} />,
            document.getElementById('load_bi_grams')
        );
        bi_grams_storage.start();

        const tag_topics_evsys = new EventsSystem();
        const tag_topics_storage = new TagsStorage(tag_topics_evsys, '/tag-topics');
        ReactDOM.render(
            <TagsList ES={tag_topics_evsys} />,
            document.getElementById('tag_topics')
        );
        ReactDOM.render(
            <TagButton ES={tag_topics_evsys} title="Load topics" tag={tag} />,
            document.getElementById('load_topics')
        );
        tag_topics_storage.start();

        const tag_mentionss_evsys = new EventsSystem();
        const tag_mentions_chart = new TagMentionsChart("#mentions_chart", tag_mentionss_evsys);
        const tag_mentions_storage = new TagMentionsStorage(tag.tag, tag_mentionss_evsys);
        tag_mentions_chart.start();
        tag_mentions_storage.start();

        const bigrams_mentions_evsys = new EventsSystem();
        const bigrams_mentions_chart = new BiGramsMentionsChart("#bigrams_mentions_chart", bigrams_mentions_evsys);
        const bigrams_mentions_storage = new BiGramsMentionsStorage(tag.tag, bigrams_mentions_evsys);
        bigrams_mentions_chart.start();
        bigrams_mentions_storage.start();

        const wordtree_evsys = new EventsSystem();
        const wordtree = new WordTree("#wordtree", wordtree_evsys);
        const wordtree_storage = new WordTreeStorage(tag.tag, wordtree_evsys);
        wordtree.start();
        wordtree_storage.start();
        ReactDOM.render(
            <TagContexts ES={wordtree_evsys} tag={tag} />,
            document.getElementById('tag_contexts')
        );
        /*const topics_texts_evsys = new EventsSystem();
        const topics_texts_chart = new TopicsTexts("#topics_texts", topics_texts_evsys);
        const topics_texts_storage = new TopicsTextsStorage(tag.tag, topics_texts_evsys);
        topics_texts_chart.start();
        topics_texts_storage.start();*/

    } else if (/^\/map$/.test(path)) {
        let map_handler = new RssTagYMap('map', window.EVSYS);
        let prom = rsstag_utils.waitFor(map_handler.isReadyToStart);

        window.EVSYS.trigger(window.EVSYS.START_TASK, 'ajax');
        prom.then(() => {
            map_handler.start();
            const geo_tags_storage = new GeoTagsStorage(window.EVSYS);
            ReactDOM.render(
                <GeoMapTools ES={window.EVSYS} />,
                document.getElementById('map_tools')
            );
            geo_tags_storage.start();
            window.EVSYS.trigger(window.EVSYS.END_TASK, 'ajax');
        });
    } else if (/^\/tag-net$/.test(path)) {
        let tag_hash = decodeURIComponent(document.location.hash);
        let ES = window.EVSYS;
        let tags_net = new TagsNet('tags_net', ES);
        let tags_net_storage = new TagsNetStorage(ES, (tag_hash)? tag_hash.substr(1): '');
        ReactDOM.render(
            <TagNetTools ES={ES} />,
            document.getElementById('tags_net_tools')
        );
        tags_net.start();
        tags_net_storage.start();
    }
}
