'use strict';

/**
 * Grouping helpers for the categories page.
 *
 * The page shows the same feeds three ways -- by provider, by category, or as
 * one flat list -- and the "Available sources" block follows the same switch.
 * Keeping the reshaping here (instead of inside the component) makes each
 * grouping a plain function over plain data that can be tested on its own.
 */

export const GROUP_MODES = ['provider', 'category', 'flat'];

const ALL_CATEGORY = 'All';
const OTHER_PROVIDER = 'other';

/**
 * Provider a feed or source belongs to; feeds stored before providers were
 * recorded have none, and are grouped as "other" instead of being dropped.
 *
 * @param {{provider?: string}} entity
 * @returns {string}
 */
export function providerKey(entity) {
  return (entity && entity.provider) || OTHER_PROVIDER;
}

/**
 * @param {string} provider
 * @returns {string} the provider name as shown in a group header
 */
export function providerLabel(provider) {
  if (provider === 'x') {
    return 'X';
  }

  return provider.charAt(0).toUpperCase() + provider.slice(1);
}

/**
 * @param {string} mode
 * @returns {string} the switcher label for a grouping mode
 */
export function groupModeLabel(mode) {
  if (mode === 'flat') {
    return 'No grouping';
  }

  return mode.charAt(0).toUpperCase() + mode.slice(1);
}

function compareGroups(left, right) {
  if (left.key === OTHER_PROVIDER) {
    return 1;
  }
  if (right.key === OTHER_PROVIDER) {
    return -1;
  }

  return left.label.toLowerCase() < right.label.toLowerCase() ? -1 : 1;
}

/**
 * Category names in the order the server sent them, minus the "All" row.
 *
 * @param {object} cats
 * @returns {string[]}
 */
export function categoryNames(cats) {
  return Object.keys(cats || {}).filter((name) => name !== ALL_CATEGORY);
}

/**
 * Distinct providers behind one category's feeds.
 *
 * @param {{feeds?: Array}} cat
 * @returns {string[]}
 */
export function categoryProviders(cat) {
  const seen = {};

  ((cat && cat.feeds) || []).forEach((feed) => {
    seen[providerKey(feed)] = true;
  });

  return Object.keys(seen);
}

function addFeedToGroup(group, cat_name, cat, feed) {
  let category = group.categories.filter((entry) => entry.name === cat_name)[0];

  if (!category) {
    category = {
      name: cat_name,
      cat: cat,
      feeds: [],
      unread_count: 0,
      // Deleting by category id removes every feed in it, including the ones
      // hidden under another provider, so a split category offers no checkbox.
      deletable: categoryProviders(cat).length === 1,
    };
    group.categories.push(category);
  }
  category.feeds.push(feed);
  category.unread_count += feed.unread_count || 0;
  group.unread_count += feed.unread_count || 0;
}

/**
 * Reshape the category tree into provider > category > feeds.
 *
 * Category order inside a group follows the server's order, which already puts
 * the uncategorized bucket last.
 *
 * @param {object} cats
 * @returns {Array<{key: string, label: string, unread_count: number, categories: Array}>}
 */
export function groupTreeByProvider(cats) {
  const groups = {};

  categoryNames(cats).forEach((cat_name) => {
    const cat = cats[cat_name];
    ((cat && cat.feeds) || []).forEach((feed) => {
      const provider = providerKey(feed);
      if (!groups[provider]) {
        groups[provider] = {
          key: provider,
          label: providerLabel(provider),
          unread_count: 0,
          categories: [],
        };
      }
      addFeedToGroup(groups[provider], cat_name, cat, feed);
    });
  });

  return Object.keys(groups)
    .map((provider) => groups[provider])
    .sort(compareGroups);
}

/**
 * Every feed of the tree in one list, sorted by title.
 *
 * @param {object} cats
 * @returns {Array}
 */
export function flattenFeeds(cats) {
  const feeds = [];

  categoryNames(cats).forEach((cat_name) => {
    const cat = cats[cat_name];
    ((cat && cat.feeds) || []).forEach((feed) => {
      feeds.push(feed);
    });
  });

  return feeds.sort((left, right) =>
    (left.title || '').toLowerCase() < (right.title || '').toLowerCase() ? -1 : 1
  );
}

/**
 * Group the "Available sources" block the same way as the tree above it.
 *
 * @param {Array} sources
 * @param {string} mode one of GROUP_MODES
 * @returns {Array<{key: string, label: string, items: Array}>}
 */
export function groupSources(sources, mode) {
  const items = sources || [];

  if (mode === 'flat') {
    return items.length ? [{ key: 'all', label: '', items: items }] : [];
  }

  const groups = {};
  items.forEach((source) => {
    const key = mode === 'provider' ? providerKey(source) : source.category_title || ALL_CATEGORY;
    if (!groups[key]) {
      groups[key] = {
        key: key,
        label: mode === 'provider' ? providerLabel(key) : key,
        items: [],
      };
    }
    groups[key].items.push(source);
  });

  return Object.keys(groups)
    .map((key) => groups[key])
    .sort(compareGroups);
}
