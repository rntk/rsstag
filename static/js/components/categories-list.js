'use strict';
import React from 'react';
import {
  GROUP_MODES,
  flattenFeeds,
  groupModeLabel,
  groupSources,
  groupTreeByProvider,
} from '../libs/source-grouping.js';

export default class CategoriesList extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      cats: window.initial_cats_list,
      activeCategory: null,
      activeFeed: null,
      sources: window.initial_sources_list || [],
      feedsListProviders: window.feeds_list_providers || [],
      sourcesExpanded: false,
      groupBy: 'provider',
      expandedGroups: {},
      readCategories: {},
      readFeeds: {},
      busy: {},
    };
  }

  selectCategory(cat_name) {
    this.setState({ activeCategory: cat_name });
  }

  selectFeed(feed_id) {
    this.setState({ activeFeed: feed_id });
  }

  qualityBand(score) {
    if (score >= 70) {
      return 'good';
    }
    if (score >= 45) {
      return 'mixed';
    }
    return 'poor';
  }

  renderQuality(quality) {
    if (!quality || typeof quality.score !== 'number') {
      return null;
    }

    return (
      <span
        className={'quality-badge quality-' + this.qualityBand(quality.score)}
        title={'Quality ' + quality.score + '/100 over ' + quality.posts_count + ' scored posts'}
      >
        {quality.score}
      </span>
    );
  }

  scanQuality(payload, event) {
    const button = event.currentTarget;

    button.disabled = true;
    fetch('/api/quality/scan', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    })
      .then((response) => response.json())
      .then((data) => {
        button.disabled = false;
        if (data.status !== 'success') {
          alert('Error: ' + data.message);
        } else {
          alert(data.message);
        }
      })
      .catch((err) => {
        button.disabled = false;
        alert('Error: ' + err);
      });
  }

  // A feed follows its category until it is toggled on its own.
  feedOverride(feed, cat) {
    const flag = this.state.readFeeds[feed.feed_id];

    if (flag !== undefined) {
      return flag;
    }

    return cat && cat.category_id ? this.state.readCategories[cat.category_id] : undefined;
  }

  isFeedRead(feed, cat) {
    return Boolean(this.feedOverride(feed, cat));
  }

  feedCount(feed, cat) {
    return this.isFeedRead(feed, cat) ? 0 : feed.unread_count;
  }

  // Read/unread post totals of a feed, following any pending read/unread toggle.
  feedReadStats(feed, cat) {
    const override = this.feedOverride(feed, cat);
    const total = (feed.read_posts || 0) + (feed.unread_posts || 0);

    if (override === undefined) {
      return { read: feed.read_posts || 0, unread: feed.unread_posts || 0 };
    }

    return override ? { read: total, unread: 0 } : { read: 0, unread: total };
  }

  categoryCount(cat, feeds, count) {
    if (!cat.category_id || !feeds.length) {
      return count;
    }

    return feeds.reduce((sum, feed) => sum + this.feedCount(feed, cat), 0);
  }

  categoryReadStats(cat, feeds) {
    if (!cat.category_id || !feeds.length) {
      return { read: cat.read_posts || 0, unread: cat.unread_posts || 0 };
    }

    return feeds.reduce(
      (sum, feed) => {
        const stats = this.feedReadStats(feed, cat);

        return { read: sum.read + stats.read, unread: sum.unread + stats.unread };
      },
      { read: 0, unread: 0 }
    );
  }

  renderReadStats(stats) {
    return (
      <span className="read-stats" title="unread / read posts">
        {stats.unread} unread · {stats.read} read
      </span>
    );
  }

  setFlag(field, key, value) {
    const flags = Object.assign({}, this.state[field]);

    flags[key] = value;
    this.setState({ [field]: flags });
  }

  // Sends one read/unread request for a category or a feed and reports the
  // result to onDone; busy state and error alerts are shared by both scopes.
  postReadStatus(url, payload, busyKey, onDone) {
    this.setFlag('busy', busyKey, true);
    fetch(url, {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    })
      .then((response) => response.json().then((data) => ({ ok: response.ok, data: data })))
      .then((result) => {
        this.setFlag('busy', busyKey, false);
        if (!result.ok) {
          alert('Error: ' + (result.data.error || 'Can not change read status'));
        } else {
          onDone();
        }
      })
      .catch((err) => {
        this.setFlag('busy', busyKey, false);
        alert('Error: ' + err);
      });
  }

  setCategoryRead(cat, readed, event) {
    event.stopPropagation();
    const busyKey = 'category::' + cat.category_id;

    if (this.state.busy[busyKey]) {
      return;
    }
    this.postReadStatus(
      '/read/category',
      { category_id: cat.category_id, readed: readed },
      busyKey,
      () => {
        const readFeeds = Object.assign({}, this.state.readFeeds);

        (cat.feeds || []).forEach((feed) => delete readFeeds[feed.feed_id]);
        this.setState({
          readFeeds: readFeeds,
          readCategories: Object.assign({}, this.state.readCategories, {
            [cat.category_id]: readed,
          }),
        });
      }
    );
  }

  setFeedRead(feed, readed, event) {
    event.stopPropagation();
    const busyKey = 'feed::' + feed.feed_id;

    if (this.state.busy[busyKey]) {
      return;
    }
    this.postReadStatus('/read/feed', { feed_id: feed.feed_id, readed: readed }, busyKey, () =>
      this.setFlag('readFeeds', feed.feed_id, readed)
    );
  }

  renderReadButtons(className, busyKey, onSet) {
    const busy = Boolean(this.state.busy[busyKey]);

    return [
      <button
        key="read"
        className={className + ' category-read-btn'}
        disabled={busy}
        title="Mark all posts as read"
        onClick={(event) => onSet(true, event)}
      >
        read all
      </button>,
      <button
        key="unread"
        className={className + ' category-read-btn'}
        disabled={busy}
        title="Mark all posts as unread"
        onClick={(event) => onSet(false, event)}
      >
        unread all
      </button>,
    ];
  }

  refreshFeed(feed, event) {
    event.stopPropagation();
    const postsCountValue = window.prompt(
      `How many recent posts should be loaded from "${feed.title}"?`,
      '100'
    );
    if (postsCountValue === null) {
      return;
    }

    const postsCount = Number(postsCountValue);
    if (!Number.isInteger(postsCount) || postsCount < 1 || postsCount > 10000) {
      alert('Enter a whole number between 1 and 10000.');
      return;
    }

    this.queueFeedRefresh(feed.feed_id, postsCount, event.currentTarget);
  }

  queueFeedRefresh(feedId, postsCount, button) {
    button.disabled = true;
    fetch('/api/provider/feed/download', {
      method: 'POST',
      body: JSON.stringify({ feed_id: feedId, posts_count: postsCount }),
      headers: { 'Content-Type': 'application/json' },
    })
      .then((response) => response.json())
      .then((data) => {
        button.disabled = false;
        if (data.status !== 'success') {
          alert('Error: ' + data.message);
        } else {
          alert(data.message);
        }
      })
      .catch((err) => {
        button.disabled = false;
        alert('Error: ' + err);
      });
  }

  refreshSourcesList(provider, event) {
    const button = event.currentTarget;

    button.disabled = true;
    fetch('/api/provider/feeds/refresh', {
      method: 'POST',
      body: JSON.stringify({ provider: provider }),
      headers: { 'Content-Type': 'application/json' },
    })
      .then((response) => response.json())
      .then((data) => {
        button.disabled = false;
        if (data.status !== 'success') {
          alert('Error: ' + data.message);
        } else {
          alert(data.message);
        }
      })
      .catch((err) => {
        button.disabled = false;
        alert('Error: ' + err);
      });
  }

  toggleSourcesExpanded() {
    this.setState({ sourcesExpanded: !this.state.sourcesExpanded });
  }

  setGroupBy(mode) {
    this.setState({ groupBy: mode });
  }

  // Provider groups and source groups start open so the page shows what is
  // there; the categories inside them start closed, or grouping by provider
  // would paint every feed of every category at once.
  groupExpanded(key, defaultExpanded) {
    const expanded = this.state.expandedGroups[key];

    return expanded === undefined ? defaultExpanded : expanded;
  }

  toggleGroup(key, defaultExpanded) {
    const expandedGroups = Object.assign({}, this.state.expandedGroups);

    expandedGroups[key] = !this.groupExpanded(key, defaultExpanded);
    this.setState({ expandedGroups: expandedGroups });
  }

  changeFeedsState(cat_name) {
    let state = Object.assign({}, this.state);

    if (cat_name in state.cats) {
      state.cats[cat_name].showed = !state.cats[cat_name].showed;
      this.setState(state);
    }
  }

  renderProviderRefreshButtons() {
    const providers = this.state.feedsListProviders || [];
    if (!providers.length) {
      return null;
    }

    return (
      <div className="feeds-list-refresh-controls">
        {providers.map((provider) => (
          <button
            key={provider}
            className="feed-action-link feeds-list-refresh-btn"
            onClick={this.refreshSourcesList.bind(this, provider)}
          >
            {`Refresh ${provider} sources`}
          </button>
        ))}
      </div>
    );
  }

  renderGroupSwitcher() {
    return (
      <div className="grouping-switcher" role="group" aria-label="Group sources by">
        <span className="grouping-switcher-label">Group by:</span>
        {GROUP_MODES.map((mode) => (
          <button
            key={mode}
            className={'grouping-switcher-btn' + (this.state.groupBy === mode ? ' active' : '')}
            aria-pressed={this.state.groupBy === mode}
            onClick={this.setGroupBy.bind(this, mode)}
          >
            {groupModeLabel(mode)}
          </button>
        ))}
      </div>
    );
  }

  renderAvailableSources() {
    const sources = this.state.sources || [];
    const groups = groupSources(sources, this.state.groupBy);

    return (
      <div className="available-sources">
        <div className="available-sources-header" onClick={this.toggleSourcesExpanded.bind(this)}>
          <span
            className={'show_btn ' + (this.state.sourcesExpanded ? 'not_minimized' : 'minimized')}
          ></span>
          <span className="available-sources-title">Available sources ({sources.length})</span>
        </div>
        <div
          className={
            'available-sources-body ' + (this.state.sourcesExpanded ? 'not_hidden' : 'hidden')
          }
        >
          {sources.length === 0 ? (
            <p className="available-sources-hint">
              No extra sources. Use Refresh sources list to fetch what is available.
            </p>
          ) : (
            groups.map((group) => this.renderSourcesGroup(group))
          )}
        </div>
      </div>
    );
  }

  renderSourcesGroup(group) {
    const list = (
      <ul className="available-sources-list">
        {group.items.map((source) => this.renderSourceItem(source))}
      </ul>
    );

    if (!group.label) {
      return <div key={group.key}>{list}</div>;
    }

    const groupKey = 'sources::' + group.key;
    const expanded = this.groupExpanded(groupKey, true);

    return (
      <div className="available-sources-group" key={groupKey}>
        <div
          className="available-sources-group-header"
          onClick={this.toggleGroup.bind(this, groupKey, true)}
        >
          <span className={'show_btn ' + (expanded ? 'not_minimized' : 'minimized')}></span>
          <span className="available-sources-group-title">{group.label}</span>
          <span className="category-count">{group.items.length}</span>
        </div>
        <div className={expanded ? 'not_hidden' : 'hidden'}>{list}</div>
      </div>
    );
  }

  renderSourceItem(source) {
    return (
      <li className="available-source-item" key={source.feed_id}>
        <a className="feed-title-link" href={source.url}>
          {source.title}
        </a>
        <span className="available-source-category">{source.category_title}</span>
        {this.renderQuality(source.quality)}
        {source.provider === 'telegram' ? (
          <button
            className="feed-action-link feed-refresh-btn"
            onClick={this.refreshFeed.bind(this, source)}
          >
            Refresh
          </button>
        ) : (
          ''
        )}
      </li>
    );
  }

  render() {
    return (
      <div className="categories-page-root">
        {this.renderProviderRefreshButtons()}
        {this.renderGroupSwitcher()}
        {this.renderTree()}
        {this.renderAvailableSources()}
      </div>
    );
  }

  renderTree() {
    if (this.state.groupBy === 'provider') {
      return this.renderProviderTree();
    }
    if (this.state.groupBy === 'flat') {
      return this.renderFlatFeeds();
    }

    return this.renderCategoriesTree();
  }

  renderFeedItem(feed, key, cat) {
    return (
      <li
        key={key}
        className={'feed-item' + (this.state.activeFeed === feed.feed_id ? ' active-row' : '')}
        onClick={this.selectFeed.bind(this, feed.feed_id)}
      >
        <input
          type="checkbox"
          className="feed-checkbox"
          data-type="feed"
          data-id={feed.feed_id}
          onChange={window.handleCheckboxChange}
        />
        <a className="feed-title-link" href={feed.url}>
          {feed.title}
        </a>
        {this.renderQuality(feed.quality)}
        <span className="category-count">{this.feedCount(feed, cat)}</span>
        {this.renderReadStats(this.feedReadStats(feed, cat))}
        <div className="feed-actions" aria-label={`${feed.title} views`}>
          <a className="feed-action-link" href={feed.hierarchy_url}>
            Hierarchy
          </a>
          <a className="feed-action-link" href={feed.canvas_url}>
            Canvas
          </a>
          <button
            className="feed-action-link quality-scan-btn"
            onClick={this.scanQuality.bind(this, { feed_ids: [feed.feed_id] })}
          >
            Score
          </button>
          {this.renderReadButtons(
            'feed-action-link',
            'feed::' + feed.feed_id,
            this.setFeedRead.bind(this, feed)
          )}
          {feed.provider === 'telegram' ? (
            <button
              className="feed-action-link feed-refresh-btn"
              onClick={this.refreshFeed.bind(this, feed)}
            >
              Refresh
            </button>
          ) : (
            ''
          )}
        </div>
      </li>
    );
  }

  renderCategoryNode(cat_name, cat, feeds, options) {
    const expanded = options.expanded;

    return (
      <li className="category" key={options.key}>
        <div
          className={
            'category-header' + (this.state.activeCategory === cat_name ? ' active-row' : '')
          }
          onClick={this.selectCategory.bind(this, cat_name)}
        >
          {cat_name !== 'All' ? (
            <span
              className={'show_btn ' + (expanded ? 'not_minimized' : 'minimized')}
              onClick={options.onToggle}
            ></span>
          ) : (
            <span style={{ width: '20px' }}></span>
          )}
          {cat_name !== 'All' && options.showCheckbox ? (
            <input
              type="checkbox"
              className="category-checkbox"
              data-type="category"
              data-id={cat.category_id}
              onChange={window.handleCheckboxChange}
            />
          ) : (
            ''
          )}
          <a className="category-title-link" href={cat.url}>
            {cat.title}
          </a>
          {this.renderQuality(cat.quality)}
          <span className="category-count">
            {this.categoryCount(cat, feeds, options.unread_count)}
          </span>
          {this.renderReadStats(this.categoryReadStats(cat, feeds))}
          <div className="category-actions" aria-label={`${cat.title} views`}>
            <a className="category-action-link" href={cat.hierarchy_url}>
              Hierarchy
            </a>
            <a className="category-action-link" href={cat.canvas_url}>
              Canvas
            </a>
            {cat.category_id ? (
              <button
                className="category-action-link quality-scan-btn"
                onClick={this.scanQuality.bind(this, {
                  category_ids: [cat.category_id],
                })}
              >
                Score
              </button>
            ) : (
              ''
            )}
            {cat.category_id
              ? this.renderReadButtons(
                  'category-action-link',
                  'category::' + cat.category_id,
                  this.setCategoryRead.bind(this, cat)
                )
              : ''}
          </div>
        </div>
        <ul className={'feeds ' + (expanded ? 'not_hidden' : 'hidden')}>
          {feeds.map((feed, i) => this.renderFeedItem(feed, options.key + '::' + i, cat))}
        </ul>
      </li>
    );
  }

  renderAllCategory() {
    const cats = this.state.cats || {};
    const all = cats['All'];

    if (!all) {
      return null;
    }

    return this.renderCategoryNode('All', all, [], {
      key: 'All',
      expanded: false,
      showCheckbox: false,
      unread_count: all.unread_count,
    });
  }

  renderProviderTree() {
    if (!(this.state && this.state.cats)) {
      return <p>No categories</p>;
    }

    const groups = groupTreeByProvider(this.state.cats);

    return (
      <ul>
        {this.renderAllCategory()}
        {groups.map((group) => this.renderProviderGroup(group))}
      </ul>
    );
  }

  renderProviderGroup(group) {
    const groupKey = 'provider::' + group.key;
    const expanded = this.groupExpanded(groupKey, true);
    const categories = group.categories.map((entry) =>
      this.renderCategoryNode(entry.name, entry.cat, entry.feeds, {
        key: groupKey + '::' + entry.name,
        expanded: this.groupExpanded(groupKey + '::' + entry.name, false),
        onToggle: this.toggleGroup.bind(this, groupKey + '::' + entry.name, false),
        showCheckbox: entry.deletable,
        unread_count: entry.unread_count,
      })
    );

    return (
      <li className="provider-group" key={groupKey}>
        <div
          className="provider-group-header"
          onClick={this.toggleGroup.bind(this, groupKey, true)}
        >
          <span className={'show_btn ' + (expanded ? 'not_minimized' : 'minimized')}></span>
          <span className="provider-group-title">{group.label}</span>
          <span className="category-count">{group.unread_count}</span>
        </div>
        <ul className={'provider-group-categories ' + (expanded ? 'not_hidden' : 'hidden')}>
          {categories}
        </ul>
      </li>
    );
  }

  renderFlatFeeds() {
    if (!(this.state && this.state.cats)) {
      return <p>No categories</p>;
    }

    const feeds = flattenFeeds(this.state.cats);

    return (
      <ul>
        {this.renderAllCategory()}
        <li className="category flat-feeds" key="flat">
          <ul className="feeds not_hidden">
            {feeds.map((feed, i) => this.renderFeedItem(feed, 'flat::' + i))}
          </ul>
        </li>
      </ul>
    );
  }

  renderCategoriesTree() {
    if (this.state && this.state.cats) {
      let cats = [];

      for (let cat_name in this.state.cats) {
        if (this.state.cats.hasOwnProperty(cat_name)) {
          let cat = this.state.cats[cat_name],
            feeds = [];

          if (cat.feeds) {
            feeds = cat.feeds;
          }
          cats.push(
            this.renderCategoryNode(cat_name, cat, feeds, {
              key: cat_name,
              expanded: cat.showed,
              onToggle: this.changeFeedsState.bind(this, cat_name),
              showCheckbox: true,
              unread_count: cat.unread_count,
            })
          );
        }
      }
      return <ul>{cats}</ul>;
    } else {
      return <p>No categories</p>;
    }
  }
}
