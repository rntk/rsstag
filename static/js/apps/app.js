'use strict';
import React from 'react';
import ReactDOM from 'react-dom';
import PostsStorage from '../storages/posts-storage.js';
import { PostTabs } from '../components/post-tabs.js';
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
//import PostsWordTree from '../components/posts-wordtree.js';
//import PostsWordsCloud from '../components/posts-wordscloud.js';
import TagContexts from '../components/tag-contexts.js';
import BiGramsMentionsStorage from '../storages/bigrams-mentions-storage.js';
import BiGramsMentionsChart from '../components/bigrams-mentions-chart.js';
//import TopicsTextsStorage from '../storages/topics-texts-storage.js';
//import TopicsTexts from '../components/topics-texts.js';
import TagsClustersStorage from '../storages/tags-clusters-storage.js';
import TagsClustersList from '../components/tags-clusters.js';
import OpenAIStorage from '../storages/openai-storage.js';
import { OpenAITool } from '../components/openai.js';
import TagSunburst from '../components/sunburst.js';
import TagTree, { BidirectionalTagTree } from '../components/dendrogram.js';
import SentenceTree from '../components/SentenceTree.js';
import TagContextsClassificationStorage from '../storages/tag-contexts-classification-storage.js';
import BigramsTable from '../components/bigrams-table.js';
import BiGramsGraphSimple from '../components/bi-grams-graph-simple.js';
import BiGramsGraph from '../components/bi-grams-graph.js';

function handleTextSelection() {
  document.addEventListener('mouseup', () => {
    const selectedText = window.getSelection().toString().trim();
    if (selectedText) {
      const currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set('rerank', selectedText);
      window.open(currentUrl.toString(), '_blank');
    }
  });
}

function handleScroll() {
  let $tools = document.querySelector('#global_tools');
  let $tools_bottom = document.querySelector('#global_tools_bottom');
  let scroll_position = window.scrollY;
  let t_out = 0;
  if ($tools || $tools_bottom) {
    window.addEventListener('scroll', (e) => {
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
  handleTextSelection(); // Add this line to initialize the text selection listener
  ReactDOM.render(<SettingsMenu ES={window.EVSYS} />, document.getElementById('settings_menu'));
  const settings_storage = new SettingsStorage(window.EVSYS);
  settings_storage.start();

  ReactDOM.render(<ProgressBar ES={window.EVSYS} />, document.getElementById('progressbar'));
  const progressbar_storage = new ProgressBarStorage(window.EVSYS);
  progressbar_storage.start();

  let path = document.location.pathname;

  ReactDOM.render(<GlobalStatus ES={window.EVSYS} />, document.getElementById('global_status'));
  if (path === '/') {
  } else if (/^\/s-tree\//.test(path)) {
    // Ensure s_tree_data is available globally for the SentenceTree component
    // This might be set by a script tag in the HTML template
    ReactDOM.render(
      <SentenceTree />,
      document.getElementById('s_tree_page') // Ensure this div exists in your HTML
    );
  } else if (/^\/sunburst\//.test(path)) {
    let sunburst = new TagSunburst(window.tag_sunburst_initial_root);
    sunburst.render('.page');
  } else if (/^\/tree\//.test(path) || /^\/prefixes\/prefix\//.test(path)) {
    let tree = new TagTree(window.tag_sunburst_initial_root);
    tree.render('.page');
  } else if (/^\/post-graph\//.test(path)) {
    if (window.posts_graphs) {
      const treeGraphs = {};

      window.posts_graphs.forEach((post) => {
        if (post.graph_data) {
          const sunburst = new TagSunburst(post.graph_data);
          sunburst.render('#graph_' + post.post_id);
        }
      });

      document.querySelectorAll('.tab-button').forEach((button) => {
        button.addEventListener('click', () => {
          const postId = button.getAttribute('data-post-id');
          const tabType = button.getAttribute('data-tab');

          // Update active button
          button.parentElement
            .querySelectorAll('.tab-button')
            .forEach((btn) => btn.classList.remove('active'));
          button.classList.add('active');

          // Update active content
          const container = button.closest('.post-section');
          container
            .querySelectorAll('.tab-content')
            .forEach((content) => content.classList.remove('active'));

          if (tabType === 'sunburst') {
            container.querySelector(`#sunburst_content_${postId}`).classList.add('active');
          } else if (tabType === 'tree') {
            container.querySelector(`#tree_content_${postId}`).classList.add('active');

            // Initialize tree graph if not already done
            if (!treeGraphs[postId]) {
              const postData = window.posts_graphs.find(
                (p) => String(p.post_id) === String(postId)
              );
              if (postData && postData.graph_data) {
                const selector = `#tree_graph_${postId}`;
                const containerWidth = container.querySelector(selector).clientWidth || 1152;

                if (postData.is_bidirectional) {
                  treeGraphs[postId] = new BidirectionalTagTree(postData.graph_data);
                } else {
                  treeGraphs[postId] = new TagTree(postData.graph_data);
                }
                treeGraphs[postId].render(selector, containerWidth, 800);
              } else {
                container.querySelector(`#tree_graph_${postId}`).innerHTML =
                  '<div style="padding: 20px; text-align: center; color: #666;">No tree data available.</div>';
              }
            }
          }
        });
      });
    }
  } else if (path === '/group/category') {
    ReactDOM.render(<CategoriesList ES={window.EVSYS} />, document.getElementById('cats_list'));
  } else if (
    /\/group\/(tag|hottag)\/.*/.test(path) ||
    /\/tags\/sentiment\/.*/.test(path) ||
    /\/tags\/group\/.*/.test(path) ||
    /\/topics\/[0-9]+/.test(path) ||
    /\/tfidf-tags/.test(path) ||
    /\/prefixes\/all\/.*/.test(path) ||
    /\/prefixes\/words\/.*/.test(path)
  ) {
    const tags_storage = new TagsStorage(window.EVSYS);
    ReactDOM.render(<TagsList ES={window.EVSYS} />, document.getElementById('tags_page'));
    ReactDOM.render(<LettersList ES={window.EVSYS} />, document.getElementById('letters_list'));
    ReactDOM.render(<SearchInput ES={window.EVSYS} />, document.getElementById('search_tools'));
    tags_storage.start();
  } else if (/\/group\/(bi-grams|bi-grams-dyn)\/.*/.test(path)) {
    const bi_grams_storage = new BiGramsStorage(window.EVSYS);
    ReactDOM.render(
      <TagsList ES={window.EVSYS} is_bigram={true} />,
      document.getElementById('tags_page')
    );
    // Render the bigrams table visualization
    const bigramsTableContainer = document.getElementById('bigrams_table_page');
    if (bigramsTableContainer) {
      ReactDOM.render(<BigramsTable ES={window.EVSYS} />, bigramsTableContainer);
    }
    bi_grams_storage.start();
  } else if (
    /^\/feed*/.test(path) ||
    /^\/category*/.test(path) ||
    /^\/tag\/.*/.test(path) ||
    /^\/posts\/with\/tags\/.*/.test(path) ||
    /^\/bi-gram\/.*/.test(path) ||
    /^\/entity\/.*/.test(path) ||
    /^\/posts\/.*/.test(path)
  ) {
    const posts_storage = new PostsStorage(window.EVSYS);
    const hash = window.location.hash;
    ReactDOM.render(
      <PostTabs ES={window.EVSYS} words_from_hash={hash} />,
      document.getElementById('posts_page')
    );
    ReactDOM.render(<ReadAllButton ES={window.EVSYS} />, document.getElementById('read_all'));
    ReactDOM.render(<ShowAllButton ES={window.EVSYS} />, document.getElementById('show_all'));
    ReactDOM.render(<PostsNumbers ES={window.EVSYS} />, document.getElementById('posts_stat'));
    posts_storage.start();
  } else if (/\/tag-info\/.*/.test(path)) {
    let tag = window.initial_tag;
    tagWithContextInfoPage(tag);
    tagNoContextInfoPage(tag);
  } else if (/\/context-tags\/.*/.test(path)) {
    let tag = window.initial_tag;
    tagWithContextInfoPage(tag);
  } else if (/^\/map$/.test(path)) {
    let map_handler = new RssTagYMap('map', window.EVSYS);
    let prom = rsstag_utils.waitFor(map_handler.isReadyToStart);

    window.EVSYS.trigger(window.EVSYS.START_TASK, 'ajax');
    prom.then(() => {
      map_handler.start();
      const geo_tags_storage = new GeoTagsStorage(window.EVSYS);
      ReactDOM.render(<GeoMapTools ES={window.EVSYS} />, document.getElementById('map_tools'));
      geo_tags_storage.start();
      window.EVSYS.trigger(window.EVSYS.END_TASK, 'ajax');
    });
  } else if (/^\/tag-net$/.test(path)) {
    let tag_hash = decodeURIComponent(document.location.hash);
    let ES = window.EVSYS;
    let tags_net = new TagsNet('tags_net', ES);
    let tags_net_storage = new TagsNetStorage(ES, tag_hash ? tag_hash.substr(1) : '');
    ReactDOM.render(<TagNetTools ES={ES} />, document.getElementById('tags_net_tools'));
    tags_net.start();
    tags_net_storage.start();
  }
};

function tagNoContextInfoPage(tag) {
  const bigrams_mentions_evsys = new EventsSystem();
  const bigrams_mentions_chart = new BiGramsMentionsChart(
    '#bigrams_mentions_chart',
    bigrams_mentions_evsys
  );
  const bigrams_mentions_storage = new BiGramsMentionsStorage(tag.tag, bigrams_mentions_evsys);
  ReactDOM.render(
    <TagButton ES={bigrams_mentions_evsys} title="mentions" tag={tag} />,
    document.getElementById('load_bigrams_mentions')
  );
  bigrams_mentions_chart.start();
  bigrams_mentions_storage.start();

  const wordtree_evsys = new EventsSystem();
  const wordtree = new WordTree('#wordtree', wordtree_evsys);
  const wordtree_storage = new WordTreeStorage(tag.tag, wordtree_evsys);
  ReactDOM.render(
    <TagButton ES={wordtree_evsys} title="wordtree" tag={tag} />,
    document.getElementById('load_wordtree')
  );
  wordtree.start();
  wordtree_storage.start();
  ReactDOM.render(
    <TagContexts ES={wordtree_evsys} tag={tag} />,
    document.getElementById('tag_contexts')
  );
  const openai_evsys = new EventsSystem();
  const openai_storage = new OpenAIStorage(tag.tag, openai_evsys);
  ReactDOM.render(<OpenAITool ES={openai_evsys} />, document.getElementById('openai_tool'));
  openai_storage.start();

  /*const topics_texts_evsys = new EventsSystem();
    const topics_texts_chart = new TopicsTexts("#topics_texts", topics_texts_evsys);
    const topics_texts_storage = new TopicsTextsStorage(tag.tag, topics_texts_evsys);
    topics_texts_chart.start();
    topics_texts_storage.start();*/
}

function tagWithContextInfoPage(tag) {
  const similar_w2v_evsys = new EventsSystem();
  const similar_w2v_storage = new TagsStorage(similar_w2v_evsys, '/tag-similar/w2v');
  ReactDOM.render(<TagsList ES={similar_w2v_evsys} />, document.getElementById('similar_w2v_tags'));
  ReactDOM.render(
    <TagButton ES={similar_w2v_evsys} title="Word2Vec" tag={tag} />,
    document.getElementById('load_similar_w2v')
  );
  similar_w2v_storage.start();

  const similar_fasttext_evsys = new EventsSystem();
  const similar_fasttext_storage = new TagsStorage(similar_fasttext_evsys, '/tag-similar/fasttext');
  ReactDOM.render(
    <TagsList ES={similar_fasttext_evsys} />,
    document.getElementById('similar_fasttext_tags')
  );
  ReactDOM.render(
    <TagButton ES={similar_fasttext_evsys} title="FastText" tag={tag} />,
    document.getElementById('load_similar_fasttext')
  );
  similar_fasttext_storage.start();

  const siblings_evsys = new EventsSystem();
  const siblings_storage = new TagsStorage(siblings_evsys, '/tag-siblings');
  ReactDOM.render(<TagsList ES={siblings_evsys} />, document.getElementById('siblings_tags'));
  ReactDOM.render(
    <TagButton ES={siblings_evsys} title="siblings" tag={tag} />,
    document.getElementById('load_siblings')
  );
  siblings_storage.start();

  const clusters_evsys = new EventsSystem();
  const clusters_storage = new TagsClustersStorage(clusters_evsys);
  ReactDOM.render(
    <TagsClustersList ES={clusters_evsys} tag={tag.tag} />,
    document.getElementById('tag_clusters')
  );
  ReactDOM.render(
    <TagButton ES={clusters_evsys} title="clusters" tag={tag} />,
    document.getElementById('load_clusters')
  );
  clusters_storage.start();

  const contexts_classification_evsys = new EventsSystem();
  const contexts_classification_storage = new TagContextsClassificationStorage(
    contexts_classification_evsys
  );
  ReactDOM.render(
    <TagsList ES={contexts_classification_evsys} />,
    document.getElementById('tag_contexts_classification')
  );
  ReactDOM.render(
    <TagButton ES={contexts_classification_evsys} title="contexts" tag={tag} />,
    document.getElementById('load_contexts_classification')
  );
  contexts_classification_storage.start();

  const bi_grams_evsys = new EventsSystem();
  const bi_grams_storage = new TagsStorage(bi_grams_evsys, '/tag-bi-grams');
  ReactDOM.render(
    <TagsList ES={bi_grams_evsys} is_bigram={true} />,
    document.getElementById('bi_grams')
  );
  ReactDOM.render(
    <TagButton ES={bi_grams_evsys} title="bi-grams" tag={tag} />,
    document.getElementById('load_bi_grams')
  );
  bi_grams_storage.start();

  // Bi-grams graph
  const bi_grams_graph_evsys = new EventsSystem();
  let bi_grams_graph;

  try {
    // Try to use the D3.js visualization first
    bi_grams_graph = new BiGramsGraph('#bi_grams_graph', tag.tag, bi_grams_graph_evsys);
  } catch (e) {
    console.warn('D3.js visualization failed to load, falling back to simple version:', e);
    // Fall back to simple table visualization
    bi_grams_graph = new BiGramsGraphSimple('#bi_grams_graph', tag.tag, bi_grams_graph_evsys);
  }

  // Create a simple load button for the graph
  const loadGraphButton = document.createElement('button');
  loadGraphButton.textContent = 'Load bi-grams graph';
  loadGraphButton.addEventListener('click', () => {
    loadGraphButton.disabled = true;
    loadGraphButton.textContent = 'Loading...';
    bi_grams_graph.start();
  });

  const loadGraphSpan = document.getElementById('load_bi_grams_graph');
  if (loadGraphSpan) {
    loadGraphSpan.appendChild(loadGraphButton);
  }

  const pmi_evsys = new EventsSystem();
  const pmi_storage = new TagsStorage(pmi_evsys, '/tag-pmi');
  ReactDOM.render(<TagsList ES={pmi_evsys} is_bigram={true} />, document.getElementById('pmi'));
  ReactDOM.render(
    <TagButton ES={pmi_evsys} title="PMI" tag={tag} />,
    document.getElementById('load_pmi')
  );
  pmi_storage.start();

  const tag_topics_evsys = new EventsSystem();
  const tag_topics_storage = new TagsStorage(tag_topics_evsys, '/tag-topics');
  ReactDOM.render(<TagsList ES={tag_topics_evsys} />, document.getElementById('tag_topics'));
  ReactDOM.render(
    <TagButton ES={tag_topics_evsys} title="topics" tag={tag} />,
    document.getElementById('load_topics')
  );
  tag_topics_storage.start();

  const tag_mentions_evsys = new EventsSystem();
  const tag_mentions_chart = new TagMentionsChart('#mentions_chart', tag_mentions_evsys);
  const tag_mentions_storage = new TagMentionsStorage(tag.tag, tag_mentions_evsys);
  ReactDOM.render(
    <TagButton ES={tag_mentions_evsys} title="mentions" tag={tag} />,
    document.getElementById('load_mentions')
  );
  tag_mentions_chart.start();
  tag_mentions_storage.start();

  const tag_entities_evsys = new EventsSystem();
  const tag_entities_storage = new TagsStorage(tag_entities_evsys, '/tag-entities');
  ReactDOM.render(
    <TagsList ES={tag_entities_evsys} is_entities={true} />,
    document.getElementById('tag_entities')
  );
  ReactDOM.render(
    <TagButton ES={tag_entities_evsys} title="entities" tag={tag} />,
    document.getElementById('load_entities')
  );
  tag_entities_storage.start();

  const tag_tfidf_evsys = new EventsSystem();
  const tag_tfidf_storage = new TagsStorage(tag_tfidf_evsys, '/tag-tfidf');
  ReactDOM.render(
    <TagsList ES={tag_tfidf_evsys} is_entities={true} />,
    document.getElementById('tag_tfidf')
  );
  ReactDOM.render(
    <TagButton ES={tag_tfidf_evsys} title="TFIDF" tag={tag} />,
    document.getElementById('load_tfidf')
  );
  tag_tfidf_storage.start();

  const tag_specific_evsys = new EventsSystem();
  const tag_specific_storage = new TagsStorage(tag_specific_evsys, '/tag-specific');
  ReactDOM.render(<TagsList ES={tag_specific_evsys} />, document.getElementById('tag_specific'));
  ReactDOM.render(
    <TagButton ES={tag_specific_evsys} title="specific" tag={tag} />,
    document.getElementById('load_specific')
  );
  tag_specific_storage.start();

  const tag_specific1_evsys = new EventsSystem();
  const tag_specific1_storage = new TagsStorage(tag_specific1_evsys, '/tag-specific1');
  ReactDOM.render(<TagsList ES={tag_specific1_evsys} />, document.getElementById('tag_specific1'));
  ReactDOM.render(
    <TagButton ES={tag_specific1_evsys} title="specific1" tag={tag} />,
    document.getElementById('load_specific1')
  );
  tag_specific1_storage.start();

  const similar_words_evsys = new EventsSystem();
  const similar_words_storage = new TagsStorage(similar_words_evsys, '/tag-similar-tags');
  ReactDOM.render(
    <TagsList ES={similar_words_evsys} />,
    document.getElementById('similar_words_tags')
  );
  ReactDOM.render(
    <TagButton ES={similar_words_evsys} title="Words" tag={tag} />,
    document.getElementById('load_similar_words')
  );
  similar_words_storage.start();
}
