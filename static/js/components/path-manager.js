'use strict';

export default class PathManager {
  constructor(pathStorage) {
    this.storage = pathStorage;
  }

  async createAndNavigate(contentType, filterset, exclude = {}) {
    const result = await this.storage.createPath(contentType, filterset, exclude);
    if (result && result.path_id) {
      window.location.href = `/paths/${contentType}/${result.path_id}`;
    }
    return result;
  }

  static makeFilterset({ tags, topics, feeds, categories } = {}) {
    const fs = {};
    if (tags && tags.length) fs.tags = { values: tags, logic: 'and' };
    if (topics && topics.length) fs.topics = { values: topics, logic: 'and' };
    if (feeds && feeds.length) fs.feeds = { values: feeds, logic: 'or' };
    if (categories && categories.length) fs.categories = { values: categories, logic: 'or' };
    return fs;
  }
}
