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
import { BiGramsTabs } from '../components/bigrams-tabs.js';
import ContextFilterStorage from '../storages/context-filter-storage.js';
import ContextFilterBar from '../components/context-filter-bar.js';
import ClustersTopics from '../components/ClustersTopics.js';
import { initTopicsPage } from '../topics-list.js';

function handleTextSelection() {
  const menu = document.createElement('div');
  menu.id = 'rerank-context-menu';
  menu.style.display = 'none';

  menu.innerHTML = `
    <div class="menu-title">Open new page with rerank?</div>
    <div class="menu-actions">
      <button type="button" data-action="open">Open</button>
      <button type="button" data-action="cancel">Cancel</button>
    </div>
  `;

  document.body.appendChild(menu);

  let selectedText = '';

  const hideMenu = () => {
    menu.style.display = 'none';
    selectedText = '';
  };

  const showMenu = (text, rect) => {
    selectedText = text;
    const menuWidth = menu.offsetWidth || 220;
    const left = Math.min(
      rect.left + window.scrollX,
      window.scrollX + window.innerWidth - menuWidth - 8
    );
    const top = rect.bottom + window.scrollY + 6;
    menu.style.left = `${Math.max(left, 8)}px`;
    menu.style.top = `${Math.max(top, 8)}px`;
    menu.style.display = 'block';
  };

  menu.addEventListener('click', (event) => {
    const action = event.target.getAttribute('data-action');
    if (!action) {
      return;
    }
    if (action === 'open' && selectedText) {
      const currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set('rerank', selectedText);
      window.open(currentUrl.toString(), '_blank');
    }
    hideMenu();
  });

  document.addEventListener('mouseup', (event) => {
    if (menu.contains(event.target)) {
      return;
    }
    const selection = window.getSelection();
    const text = selection.toString().trim();
    if (text && selection.rangeCount > 0) {
      const rect = selection.getRangeAt(0).getBoundingClientRect();
      showMenu(text, rect);
      return;
    }
    hideMenu();
  });

  document.addEventListener('mousedown', (event) => {
    if (!menu.contains(event.target)) {
      hideMenu();
    }
  });

  document.addEventListener('scroll', () => {
    hideMenu();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      hideMenu();
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
  const settings_menu_container = document.getElementById('settings_menu');
  if (settings_menu_container) {
    ReactDOM.render(<SettingsMenu ES={window.EVSYS} />, settings_menu_container);
  }
  const settings_storage = new SettingsStorage(window.EVSYS);
  settings_storage.start();

  const progressbar_container = document.getElementById('progressbar');
  if (progressbar_container) {
    ReactDOM.render(<ProgressBar ES={window.EVSYS} />, progressbar_container);
  }
  const progressbar_storage = new ProgressBarStorage(window.EVSYS);
  progressbar_storage.start();

  // Initialize context filter (available on all pages with the bar)
  const context_filter_bar = new ContextFilterBar('context_filter_bar', window.EVSYS);
  const context_filter_storage = new ContextFilterStorage(window.EVSYS);
  context_filter_bar.start();
  context_filter_storage.start();

  let path = document.location.pathname;

  const global_status_container = document.getElementById('global_status');
  if (global_status_container) {
    ReactDOM.render(<GlobalStatus ES={window.EVSYS} />, global_status_container);
  }
  if (path === '/') {
  } else if (/^\/post-grouped\//.test(path)) {
    const posts_storage = new PostsStorage(window.EVSYS);
    // Mock the data structure expected by PostsStorage if necessary,
    // although PostsStorage mostly uses window.* variables in fetchPosts()
    window.posts_list = window.posts.map(p => ({
      pos: p.post_id,
      post: p,
      showed: true
    }));
    window.group = 'tag';
    window.group_title = window.feed_title;
    window.words = [];

    const read_all_container = document.getElementById('read_all');
    if (read_all_container) {
      ReactDOM.render(<ReadAllButton ES={window.EVSYS} />, read_all_container);
    }
    const show_all_container = document.getElementById('show_all');
    if (show_all_container) {
      ReactDOM.render(<ShowAllButton ES={window.EVSYS} />, show_all_container);
    }
    posts_storage.start();
  } else if (/^\/s-tree\//.test(path)) {
    // Ensure s_tree_data is available globally for the SentenceTree component
    // This might be set by a script tag in the HTML template
    const s_tree_page_container = document.getElementById('s_tree_page');
    if (s_tree_page_container) {
      ReactDOM.render(
        <SentenceTree />,
        s_tree_page_container // Ensure this div exists in your HTML
      );
    }
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
                  '<div class="no-data-message">No tree data available.</div>';
              }
            }
          }
        });
      });
    }
  } else if (path === '/group/category') {
    const cats_list_container = document.getElementById('cats_list');
    if (cats_list_container) {
      ReactDOM.render(<CategoriesList ES={window.EVSYS} />, cats_list_container);
    }
  } else if (
    /\/group\/(tag|hottag|tags-categories)\/.*/.test(path) ||
    /\/tags\/category\/.*/.test(path) ||
    /\/tags\/sentiment\/.*/.test(path) ||
    /\/tags\/group\/.*/.test(path) ||
    /\/topics\/[0-9]+/.test(path) ||
    /\/tfidf-tags/.test(path) ||
    /\/prefixes\/all\/.*/.test(path) ||
    /\/prefixes\/words\/.*/.test(path)
  ) {
    const tags_storage = new TagsStorage(window.EVSYS);
    const tags_page_container = document.getElementById('tags_page');
    if (tags_page_container) {
      ReactDOM.render(<TagsList ES={window.EVSYS} />, tags_page_container);
    }
    const letters_list_container = document.getElementById('letters_list');
    if (letters_list_container) {
      ReactDOM.render(<LettersList ES={window.EVSYS} />, letters_list_container);
    }
    const search_tools_container = document.getElementById('search_tools');
    if (search_tools_container) {
      ReactDOM.render(<SearchInput ES={window.EVSYS} />, search_tools_container);
    }
    tags_storage.start();
  } else if (/\/group\/(bi-grams|bi-grams-dyn)\/.*/.test(path)) {
    const bi_grams_storage = new BiGramsStorage(window.EVSYS);
    // Render the tabs controller
    ReactDOM.render(
      <BiGramsTabs ES={window.EVSYS} />,
      document.getElementById('bigrams_tabs_page')
    );
    // Render the cloud view
    ReactDOM.render(
      <TagsList ES={window.EVSYS} is_bigram={true} />,
      document.getElementById('tags_page')
    );
    // Render the table view
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
    const posts_page_container = document.getElementById('posts_page');
    if (posts_page_container) {
      ReactDOM.render(
        <PostTabs ES={window.EVSYS} words_from_hash={hash} />,
        posts_page_container
      );
    }
    const read_all_container = document.getElementById('read_all');
    if (read_all_container) {
      ReactDOM.render(<ReadAllButton ES={window.EVSYS} />, read_all_container);
    }
    const show_all_container = document.getElementById('show_all');
    if (show_all_container) {
      ReactDOM.render(<ShowAllButton ES={window.EVSYS} />, show_all_container);
    }
    const posts_stat_container = document.getElementById('posts_stat');
    if (posts_stat_container) {
      ReactDOM.render(<PostsNumbers ES={window.EVSYS} />, posts_stat_container);
    }
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
  } else if (path === '/clusters-topics-dyn') {
    const context = document.getElementById('clusters_topics_page_container');
    if (context) {
      ReactDOM.render(<ClustersTopics />, context);
    }
  } else if (/^\/topics-list(\/[0-9]+)?$/.test(path)) {
    initTopicsPage();
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

  // Add placeholder message to the graph container and make it small
  const biGramsGraphContainer = document.getElementById('bi_grams_graph');
  const loadGraphSpan = document.getElementById('load_bi_grams_graph');

  if (biGramsGraphContainer) {
    biGramsGraphContainer.innerHTML = '<div class="placeholder-message">No graph loaded</div>';
    // Make the container small initially
    biGramsGraphContainer.style.height = 'auto';
    biGramsGraphContainer.style.minHeight = '0';
  }

  try {
    // Try to use the D3.js visualization first
    bi_grams_graph = new BiGramsGraph('#bi_grams_graph', tag.tag, bi_grams_graph_evsys);
  } catch (e) {
    console.warn('D3.js visualization failed to load, falling back to simple version:', e);
    // Fall back to simple table visualization
    bi_grams_graph = new BiGramsGraphSimple('#bi_grams_graph', tag.tag, bi_grams_graph_evsys);
  }

  // Create a simple load button for the graph
  let isGraphLoaded = false;
  let isGraphVisible = false;

  const loadGraphButton = document.createElement('button');
  loadGraphButton.textContent = 'Load bi-grams graph';
  loadGraphButton.addEventListener('click', () => {
    if (!isGraphLoaded) {
      // Loading the graph for the first time
      loadGraphButton.disabled = true;
      loadGraphButton.textContent = 'Loading...';

      // Clear the placeholder and restore full size before loading the graph
      if (biGramsGraphContainer) {
        biGramsGraphContainer.innerHTML = '';
        biGramsGraphContainer.style.height = '750px';
      }

      bi_grams_graph.start();

      // After a short delay, enable the button and change to "Hide"
      setTimeout(() => {
        isGraphLoaded = true;
        isGraphVisible = true;
        loadGraphButton.disabled = false;
        loadGraphButton.textContent = 'Hide bi-grams graph';
      }, 500);
    } else {
      // Toggle visibility
      if (isGraphVisible) {
        // Hide the graph - restore placeholder and small height
        if (biGramsGraphContainer) {
          biGramsGraphContainer.innerHTML = '<div class="placeholder-message">Graph hidden</div>';
          biGramsGraphContainer.style.height = 'auto';
          biGramsGraphContainer.style.minHeight = '0';
        }
        loadGraphButton.textContent = 'Show bi-grams graph';
        isGraphVisible = false;
      } else {
        // Show the graph - restore full size and re-render
        if (biGramsGraphContainer) {
          biGramsGraphContainer.innerHTML = '';
          biGramsGraphContainer.style.height = '750px';
        }
        bi_grams_graph.start();
        loadGraphButton.textContent = 'Hide bi-grams graph';
        isGraphVisible = true;
      }
    }
  });

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

  const tag_grouped_topics_evsys = new EventsSystem();
  const tag_grouped_topics_storage = new TagsStorage(
    tag_grouped_topics_evsys,
    '/tag-grouped-topics'
  );
  ReactDOM.render(
    <TagsList ES={tag_grouped_topics_evsys} />,
    document.getElementById('tag_grouped_topics')
  );
  ReactDOM.render(
    <TagButton ES={tag_grouped_topics_evsys} title="grouped topics" tag={tag} />,
    document.getElementById('load_grouped_topics')
  );
  tag_grouped_topics_storage.start();

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
