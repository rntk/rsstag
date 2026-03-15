'use strict';
import { createRoot } from 'react-dom/client';
import { renderToRoot } from '../libs/render-helper.js';
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
import TagTopicsRadar from '../components/tag-topics-radar.js';
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
import PathStorage from '../storages/path-storage.js';
import PathManager from '../components/path-manager.js';
import ContextFilterBar from '../components/context-filter-bar.js';
import ChatStorage from '../storages/chat-storage.js';
import GlobalChatPanel from '../components/global-chat.js';
import ClustersTopics from '../components/ClustersTopics.js';
import { initTopicsPage } from '../topics-list.js';
import TopicsMindmap from '../components/topics-mindmap.js';

function handleTextSelection() {
  const menu = document.createElement('div');
  menu.id = 'text-context-menu';
  menu.style.display = 'none';

  menu.innerHTML = `
    <div class="menu-title">Selected text</div>
    <div class="menu-actions">
      <button type="button" data-action="rerank">Rerank</button>
      <button type="button" data-action="chat">Chat</button>
      <button type="button" data-action="cancel">&times;</button>
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
    if (action === 'rerank' && selectedText) {
      const currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set('rerank', selectedText);
      window.open(currentUrl.toString(), '_blank');
    } else if (action === 'chat' && selectedText) {
      if (window.EVSYS) {
        window.EVSYS.trigger(window.EVSYS.CHAT_START_WITH_CONTEXT, {
          type: 'text_selection',
          text: selectedText,
          sentences: [],
          post_ids: [],
          source_url: window.location.href,
        });
      }
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

export function initSentenceClusterPage() {
  const tabsContainer = document.getElementById('sentence_cluster_tabs');
  if (!tabsContainer) {
    return;
  }

  const tabs = tabsContainer.querySelectorAll('.sentence-cluster-tab-btn');
  const contents = {
    snippets: document.getElementById('sentence_cluster_tab_snippets'),
    'groups-mind-map': document.getElementById('sentence_cluster_tab_groups_mind_map'),
  };
  const chartContainer = document.getElementById('sentence_cluster_mindmap_chart');
  let mindmapRendered = false;

  const renderMindmapIfNeeded = () => {
    if (mindmapRendered || !chartContainer || !window.sentence_cluster_mindmap_data) {
      return;
    }

    const clusterId = window.sentence_cluster_id;
    const mindmap = new TopicsMindmap();
    mindmap.render('#sentence_cluster_mindmap_chart', window.sentence_cluster_mindmap_data, {
      topicClickAction: 'toggle',
      countLabel: 'snippets',
      snippetApiBaseUrl: `/api/sentence-clusters/${encodeURIComponent(clusterId)}/topic-snippets`,
    });
    mindmapRendered = true;
  };

  const activateTab = (tabName) => {
    tabs.forEach((tab) => {
      tab.classList.toggle('active', tab.getAttribute('data-tab') === tabName);
    });

    Object.entries(contents).forEach(([name, content]) => {
      if (content) {
        content.classList.toggle('active', name === tabName);
      }
    });

    if (tabName === 'groups-mind-map') {
      renderMindmapIfNeeded();
    }
  };

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const tabName = tab.getAttribute('data-tab');
      if (tabName) {
        activateTab(tabName);
      }
    });
  });
}

export function initSnippetHoverCards() {
  const snippetCards = document.querySelectorAll('.snippet-item');
  snippetCards.forEach((card) => {
    if (!card.hasAttribute('tabindex')) {
      card.setAttribute('tabindex', '0');
    }
    card.classList.add('snippet-hover-card');
  });
}

function initPathRecommendationsPage() {
  const container = document.getElementById('path_recommendations');
  const pathData = window.path_data;
  if (!container || !pathData || !pathData.path_id) {
    return;
  }

  const pathStorage = new PathStorage(window.EVSYS);
  pathStorage.start();
  window.pathManager = new PathManager(pathStorage);
  window.pathManager.loadRecommendations(pathData.path_id, container);
}

export function resolvePageType(path) {
  if (path === '/') {
    return 'root';
  }
  if (/^\/post-compare\//.test(path)) {
    return 'post-compare';
  }
  if (/^\/post-grouped\//.test(path)) {
    return 'post-grouped';
  }
  if (/^\/s-tree\//.test(path)) {
    return 's-tree';
  }
  if (/^\/sunburst\//.test(path)) {
    return 'sunburst';
  }
  if (/^\/tree\//.test(path) || /^\/prefixes\/prefix\//.test(path)) {
    return 'tree';
  }
  if (/^\/post-graph\//.test(path)) {
    return 'post-graph';
  }
  if (path === '/group/category') {
    return 'group-category';
  }
  if (
    /\/group\/(tag|hottag|tags-categories)\/.*/.test(path) ||
    /\/group\/(rake-dyn|yake-dyn)\/.*/.test(path) ||
    /\/tags\/category\/.*/.test(path) ||
    /\/tags\/sentiment\/.*/.test(path) ||
    /\/tags\/group\/.*/.test(path) ||
    /\/topics\/[0-9]+/.test(path) ||
    /\/tfidf-tags/.test(path) ||
    /\/ba-surprise/.test(path) ||
    /\/prefixes\/all\/.*/.test(path) ||
    /\/prefixes\/words\/.*/.test(path)
  ) {
    return 'tags-group';
  }
  if (/\/group\/(bi-grams|bi-grams-dyn)\/.*/.test(path)) {
    return 'bigrams-group';
  }
  if (
    /^\/feed*/.test(path) ||
    /^\/category*/.test(path) ||
    /^\/tag\/.*/.test(path) ||
    /^\/posts\/with\/tags\/.*/.test(path) ||
    /^\/bi-gram\/.*/.test(path) ||
    /^\/entity\/.*/.test(path) ||
    /^\/posts\/.*/.test(path)
  ) {
    return 'posts-list';
  }
  if (/\/tag-info\/.*/.test(path)) {
    return 'tag-info';
  }
  if (/\/context-tags\/.*/.test(path)) {
    return 'context-tags';
  }
  if (/^\/map$/.test(path)) {
    return 'map';
  }
  if (/^\/tag-net$/.test(path)) {
    return 'tag-net';
  }
  if (path === '/clusters-topics-dyn') {
    return 'clusters-topics-dyn';
  }
  if (/^\/topics-mindmap$/.test(path)) {
    return 'topics-mindmap';
  }
  if (/^\/sentence-clusters\/[0-9]+$/.test(path)) {
    return 'sentence-cluster';
  }
  if (/^\/sentence-clusters$/.test(path)) {
    return 'sentence-clusters';
  }
  if (/^\/post-grouped-snippets\/.+/.test(path)) {
    return 'post-grouped-snippets';
  }
  if (/^\/tag-context-tree\//.test(path)) {
    return 'tag-context-tree';
  }
  if (/^\/topics-list(\/[0-9]+)?$/.test(path)) {
    return 'topics-list';
  }
  if (/^\/paths\/sentences\//.test(path)) {
    return 'path-sentences';
  }
  if (/^\/paths\/posts\//.test(path)) {
    return 'path-posts';
  }

  return 'unknown';
}

export function initApp() {
  if (window.EVSYS === undefined) {
    window.EVSYS = new EventsSystem();
  }
  handleScroll();
  handleTextSelection(); // Add this line to initialize the text selection listener
  renderToRoot('settings_menu', <SettingsMenu ES={window.EVSYS} />);
  const settings_storage = new SettingsStorage(window.EVSYS);
  settings_storage.start();

  renderToRoot('progressbar', <ProgressBar ES={window.EVSYS} />);
  const progressbar_storage = new ProgressBarStorage(window.EVSYS);
  progressbar_storage.start();

  // Initialize context filter (available on all pages with the bar)
  if (window.context_filter_data && !window.context_filter_data.filters) {
    window.context_filter_data = {
      active: Boolean(window.context_filter_data.active),
      filters: window.context_filter_data,
    };
  }
  const context_filter_bar = new ContextFilterBar('context_filter_bar', window.EVSYS);
  const context_filter_storage = new ContextFilterStorage(window.EVSYS);
  context_filter_bar.start();
  context_filter_storage.start();

  // Initialize global chat panel
  let chatDiv = document.getElementById('global_chat_panel');
  if (!chatDiv) {
    chatDiv = document.createElement('div');
    chatDiv.id = 'global_chat_panel';
    document.body.appendChild(chatDiv);
  }
  createRoot(chatDiv).render(<GlobalChatPanel ES={window.EVSYS} />);
  const chat_storage = new ChatStorage(window.EVSYS);
  chat_storage.start();

  let path = document.location.pathname;

  renderToRoot('global_status', <GlobalStatus ES={window.EVSYS} />);
  const pageType = resolvePageType(path);

  if (pageType === 'root') {
  } else if (pageType === 'post-grouped' || pageType === 'post-compare') {
    const posts_storage = new PostsStorage(window.EVSYS);
    // Mock the data structure expected by PostsStorage if necessary,
    // although PostsStorage mostly uses window.* variables in fetchPosts()
    window.posts_list = window.posts.map((p) => ({
      pos: p.post_id,
      post: p,
      showed: true,
    }));
    window.group = 'tag';
    window.group_title = window.feed_title;
    window.words = [];

    renderToRoot('read_all', <ReadAllButton ES={window.EVSYS} />);
    renderToRoot('show_all', <ShowAllButton ES={window.EVSYS} />);
    posts_storage.start();
  } else if (pageType === 's-tree') {
    // Ensure s_tree_data is available globally for the SentenceTree component
    // This might be set by a script tag in the HTML template
    renderToRoot('s_tree_page', <SentenceTree />);
  } else if (pageType === 'sunburst') {
    let sunburst = new TagSunburst(window.tag_sunburst_initial_root);
    sunburst.render('.page');
  } else if (pageType === 'tree') {
    let tree = new TagTree(window.tag_sunburst_initial_root);
    tree.render('.page');
  } else if (pageType === 'post-graph') {
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
  } else if (pageType === 'group-category') {
    renderToRoot('cats_list', <CategoriesList ES={window.EVSYS} />);
  } else if (pageType === 'tags-group') {
    const tags_storage = new TagsStorage(window.EVSYS);
    renderToRoot('tags_page', <TagsList ES={window.EVSYS} />);
    renderToRoot('letters_list', <LettersList ES={window.EVSYS} />);
    renderToRoot('search_tools', <SearchInput ES={window.EVSYS} />);
    tags_storage.start();
  } else if (pageType === 'bigrams-group') {
    const bi_grams_storage = new BiGramsStorage(window.EVSYS);
    renderToRoot('bigrams_tabs_page', <BiGramsTabs ES={window.EVSYS} />);
    renderToRoot('tags_page', <TagsList ES={window.EVSYS} is_bigram={true} />);
    renderToRoot('bigrams_table_page', <BigramsTable ES={window.EVSYS} />);
    bi_grams_storage.start();
  } else if (pageType === 'posts-list') {
    const posts_storage = new PostsStorage(window.EVSYS);
    const hash = window.location.hash;
    renderToRoot('posts_page', <PostTabs ES={window.EVSYS} words_from_hash={hash} />);
    renderToRoot('read_all', <ReadAllButton ES={window.EVSYS} />);
    renderToRoot('show_all', <ShowAllButton ES={window.EVSYS} />);
    renderToRoot('posts_stat', <PostsNumbers ES={window.EVSYS} />);
    posts_storage.start();
  } else if (pageType === 'tag-info') {
    let tag = window.initial_tag;
    tagWithContextInfoPage(tag);
    tagNoContextInfoPage(tag);
  } else if (pageType === 'context-tags') {
    let tag = window.initial_tag;
    tagWithContextInfoPage(tag);
  } else if (pageType === 'map') {
    let map_handler = new RssTagYMap('map', window.EVSYS);
    let prom = rsstag_utils.waitFor(map_handler.isReadyToStart);

    window.EVSYS.trigger(window.EVSYS.START_TASK, 'ajax');
    prom.then(() => {
      map_handler.start();
      const geo_tags_storage = new GeoTagsStorage(window.EVSYS);
      renderToRoot('map_tools', <GeoMapTools ES={window.EVSYS} />);
      geo_tags_storage.start();
      window.EVSYS.trigger(window.EVSYS.END_TASK, 'ajax');
    });
  } else if (pageType === 'tag-net') {
    let tag_hash = decodeURIComponent(document.location.hash);
    let ES = window.EVSYS;
    let tags_net = new TagsNet('tags_net', ES);
    let tags_net_storage = new TagsNetStorage(ES, tag_hash ? tag_hash.substr(1) : '');
    renderToRoot('tags_net_tools', <TagNetTools ES={ES} />);
    tags_net.start();
    tags_net_storage.start();
  } else if (pageType === 'clusters-topics-dyn') {
    renderToRoot('clusters_topics_page_container', <ClustersTopics />);
  } else if (pageType === 'topics-mindmap') {
    const mindmap = new TopicsMindmap();
    mindmap.render('#topics_mindmap_chart', window.mindmap_data);
  } else if (pageType === 'sentence-cluster') {
    initSnippetHoverCards();
    initSentenceClusterPage();
  } else if (pageType === 'post-grouped-snippets') {
    initSnippetHoverCards();
  } else if (pageType === 'tag-context-tree') {
    const mindmap = new TopicsMindmap();
    mindmap.render('#topics_mindmap_chart', window.mindmap_data);
  } else if (pageType === 'topics-list') {
    initTopicsPage();
  } else if (pageType === 'path-sentences') {
    initSnippetHoverCards();
    initPathRecommendationsPage();
  } else if (pageType === 'path-posts') {
    const posts_storage = new PostsStorage(window.EVSYS);
    posts_storage.start();
    initPathRecommendationsPage();
  }
}

window.onload = initApp;

function tagNoContextInfoPage(tag) {
  const bigrams_mentions_evsys = new EventsSystem();
  const bigrams_mentions_chart = new BiGramsMentionsChart(
    '#bigrams_mentions_chart',
    bigrams_mentions_evsys
  );
  const bigrams_mentions_storage = new BiGramsMentionsStorage(tag.tag, bigrams_mentions_evsys);
  renderToRoot('load_bigrams_mentions', <TagButton ES={bigrams_mentions_evsys} title="mentions" tag={tag} />);
  bigrams_mentions_chart.start();
  bigrams_mentions_storage.start();

  const wordtree_evsys = new EventsSystem();
  const wordtree = new WordTree('#wordtree', wordtree_evsys);
  const wordtree_storage = new WordTreeStorage(tag.tag, wordtree_evsys);
  renderToRoot('load_wordtree', <TagButton ES={wordtree_evsys} title="wordtree" tag={tag} />);
  wordtree.start();
  wordtree_storage.start();
  renderToRoot('tag_contexts', <TagContexts ES={wordtree_evsys} tag={tag} />);
  const openai_evsys = new EventsSystem();
  const openai_storage = new OpenAIStorage(tag.tag, openai_evsys);
  renderToRoot('openai_tool', <OpenAITool ES={openai_evsys} />);
  openai_storage.start();

  /*const topics_texts_evsys = new EventsSystem();
    const topics_texts_chart = new TopicsTexts("#topics_texts", topics_texts_evsys);
    const topics_texts_storage = new TopicsTextsStorage(tag.tag, topics_texts_evsys);
    topics_texts_chart.start();
    topics_texts_storage.start();*/
}

function tagWithContextInfoPage(tag) {
  // Instantiate PathManager so radar chart clicks can create paths
  const path_storage = new PathStorage(window.EVSYS);
  path_storage.start();
  window.pathManager = new PathManager(path_storage);

  const similar_w2v_evsys = new EventsSystem();
  const similar_w2v_storage = new TagsStorage(similar_w2v_evsys, '/tag-similar/w2v');
  renderToRoot('similar_w2v_tags', <TagsList ES={similar_w2v_evsys} />);
  renderToRoot('load_similar_w2v', <TagButton ES={similar_w2v_evsys} title="Word2Vec" tag={tag} />);
  similar_w2v_storage.start();

  const similar_fasttext_evsys = new EventsSystem();
  const similar_fasttext_storage = new TagsStorage(similar_fasttext_evsys, '/tag-similar/fasttext');
  renderToRoot('similar_fasttext_tags', <TagsList ES={similar_fasttext_evsys} />);
  renderToRoot('load_similar_fasttext', <TagButton ES={similar_fasttext_evsys} title="FastText" tag={tag} />);
  similar_fasttext_storage.start();

  const siblings_evsys = new EventsSystem();
  const siblings_storage = new TagsStorage(siblings_evsys, '/tag-siblings');
  renderToRoot('siblings_tags', <TagsList ES={siblings_evsys} />);
  renderToRoot('load_siblings', <TagButton ES={siblings_evsys} title="siblings" tag={tag} />);
  siblings_storage.start();

  const clusters_evsys = new EventsSystem();
  const clusters_storage = new TagsClustersStorage(clusters_evsys);
  renderToRoot('tag_clusters', <TagsClustersList ES={clusters_evsys} tag={tag.tag} />);
  renderToRoot('load_clusters', <TagButton ES={clusters_evsys} title="clusters" tag={tag} />);
  clusters_storage.start();

  const contexts_classification_evsys = new EventsSystem();
  const contexts_classification_storage = new TagContextsClassificationStorage(
    contexts_classification_evsys
  );
  renderToRoot('tag_contexts_classification', <TagsList ES={contexts_classification_evsys} />);
  renderToRoot('load_contexts_classification', <TagButton ES={contexts_classification_evsys} title="contexts" tag={tag} />);
  contexts_classification_storage.start();

  const bi_grams_evsys = new EventsSystem();
  const bi_grams_storage = new TagsStorage(bi_grams_evsys, '/tag-bi-grams');
  renderToRoot('bi_grams', <TagsList ES={bi_grams_evsys} is_bigram={true} />);
  renderToRoot('load_bi_grams', <TagButton ES={bi_grams_evsys} title="bi-grams" tag={tag} />);
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
  renderToRoot('pmi', <TagsList ES={pmi_evsys} is_bigram={true} />);
  renderToRoot('load_pmi', <TagButton ES={pmi_evsys} title="PMI" tag={tag} />);
  pmi_storage.start();

  const tag_topics_evsys = new EventsSystem();
  const tag_topics_storage = new TagsStorage(tag_topics_evsys, '/tag-topics');
  renderToRoot('tag_topics', <TagsList ES={tag_topics_evsys} />);
  renderToRoot('load_topics', <TagButton ES={tag_topics_evsys} title="topics" tag={tag} />);
  tag_topics_storage.start();

  const tag_grouped_topics_evsys = new EventsSystem();
  const tag_grouped_topics_storage = new TagsStorage(
    tag_grouped_topics_evsys,
    '/tag-grouped-topics'
  );
  renderToRoot('tag_grouped_topics', <TagsList ES={tag_grouped_topics_evsys} />);
  renderToRoot('load_grouped_topics', <TagButton ES={tag_grouped_topics_evsys} title="grouped topics" tag={tag} />);
  tag_grouped_topics_storage.start();

  const tag_llm_topics_evsys = new EventsSystem();
  const tag_llm_topics_storage = new TagsStorage(tag_llm_topics_evsys, '/tag-llm-topics');
  renderToRoot('tag_llm_topics', <TagsList ES={tag_llm_topics_evsys} />);
  renderToRoot('load_llm_topics', <TagButton ES={tag_llm_topics_evsys} title="LLM topics" tag={tag} />);
  tag_llm_topics_storage.start();

  const tag_topics_radar_evsys = new EventsSystem();
  const tag_topics_radar_storage = new TagsStorage(tag_topics_radar_evsys, '/tag-grouped-topics');
  const topics_radar = new TagTopicsRadar('#tag_topics_radar', tag_topics_radar_evsys, {
    maxTopics: 30,
    defaultLevel: 'deepest',
  });
  renderToRoot('load_topics_radar', <TagButton ES={tag_topics_radar_evsys} title="topics radar" tag={tag} />);
  topics_radar.start();
  tag_topics_radar_storage.start();

  const tag_mentions_evsys = new EventsSystem();
  const tag_mentions_chart = new TagMentionsChart('#mentions_chart', tag_mentions_evsys);
  const tag_mentions_storage = new TagMentionsStorage(tag.tag, tag_mentions_evsys);
  renderToRoot('load_mentions', <TagButton ES={tag_mentions_evsys} title="mentions" tag={tag} />);
  tag_mentions_chart.start();
  tag_mentions_storage.start();

  const tag_entities_evsys = new EventsSystem();
  const tag_entities_storage = new TagsStorage(tag_entities_evsys, '/tag-entities');
  renderToRoot('tag_entities', <TagsList ES={tag_entities_evsys} is_entities={true} />);
  renderToRoot('load_entities', <TagButton ES={tag_entities_evsys} title="entities" tag={tag} />);
  tag_entities_storage.start();

  const tag_tfidf_evsys = new EventsSystem();
  const tag_tfidf_storage = new TagsStorage(tag_tfidf_evsys, '/tag-tfidf');
  renderToRoot('tag_tfidf', <TagsList ES={tag_tfidf_evsys} is_entities={true} />);
  renderToRoot('load_tfidf', <TagButton ES={tag_tfidf_evsys} title="TFIDF" tag={tag} />);
  tag_tfidf_storage.start();

  const tag_specific_evsys = new EventsSystem();
  const tag_specific_storage = new TagsStorage(tag_specific_evsys, '/tag-specific');
  renderToRoot('tag_specific', <TagsList ES={tag_specific_evsys} />);
  renderToRoot('load_specific', <TagButton ES={tag_specific_evsys} title="specific" tag={tag} />);
  tag_specific_storage.start();

  const tag_specific1_evsys = new EventsSystem();
  const tag_specific1_storage = new TagsStorage(tag_specific1_evsys, '/tag-specific1');
  renderToRoot('tag_specific1', <TagsList ES={tag_specific1_evsys} />);
  renderToRoot('load_specific1', <TagButton ES={tag_specific1_evsys} title="specific1" tag={tag} />);
  tag_specific1_storage.start();

  const similar_words_evsys = new EventsSystem();
  const similar_words_storage = new TagsStorage(similar_words_evsys, '/tag-similar-tags');
  renderToRoot('similar_words_tags', <TagsList ES={similar_words_evsys} />);
  renderToRoot('load_similar_words', <TagButton ES={similar_words_evsys} title="Words" tag={tag} />);
  similar_words_storage.start();
}
